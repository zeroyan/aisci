"""Integration tests for RunService with mocked experiment loop."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.schemas import CostUsage
from src.schemas.experiment import ExperimentIteration, IterationStatus
from src.schemas.state import RunStatus
from src.service.run_service import RunService
from src.storage.artifact import ArtifactStore

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
SAMPLE_SPEC_PATH = FIXTURES_DIR / "sample_research_spec.json"
SAMPLE_PLAN_PATH = FIXTURES_DIR / "sample_experiment_plan.json"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def service(tmp_path: Path) -> RunService:
    """Return a RunService backed by a temporary ArtifactStore."""
    store = ArtifactStore(runs_dir=tmp_path)
    return RunService(store=store)


@pytest.fixture()
def store(service: RunService) -> ArtifactStore:
    """Shortcut to access the underlying store from a RunService."""
    return service.store


# ---------------------------------------------------------------------------
# 1. test_create_run_with_plan
# ---------------------------------------------------------------------------


def test_create_run_with_plan(service: RunService, store: ArtifactStore) -> None:
    """Create a run with an explicit plan and verify all artifacts are persisted."""
    run = service.create_run(spec_path=SAMPLE_SPEC_PATH, plan_path=SAMPLE_PLAN_PATH)

    # Run metadata
    assert run.run_id and run.run_id.startswith("run_")
    assert run.spec_id == "spec_sample_001"
    assert run.plan_id == "plan_sample_001"
    assert run.status == RunStatus.QUEUED

    # Persisted artifacts
    assert store.path_exists(run.run_id, "spec/research_spec.json")
    assert store.path_exists(run.run_id, "plan/experiment_plan.json")


# ---------------------------------------------------------------------------
# 2. test_create_run_without_plan_auto_generates
# ---------------------------------------------------------------------------


def test_create_run_without_plan_auto_generates(
    service: RunService, store: ArtifactStore
) -> None:
    """When no plan is provided, RunService auto-generates one."""
    run = service.create_run(spec_path=SAMPLE_SPEC_PATH)

    assert run.plan_id is not None
    assert run.plan_id.startswith("plan_auto_")

    # The auto-generated plan must be persisted and valid JSON
    assert store.path_exists(run.run_id, "plan/experiment_plan.json")
    plan_data = store.load_json(run.run_id, "plan/experiment_plan.json")
    assert plan_data["plan_id"] == run.plan_id
    assert plan_data["spec_id"] == "spec_sample_001"


# ---------------------------------------------------------------------------
# 3. test_create_run_rejects_draft_spec
# ---------------------------------------------------------------------------


def test_create_run_rejects_draft_spec(service: RunService, tmp_path: Path) -> None:
    """A spec with status='draft' must be rejected with a ValueError."""
    draft_spec = json.loads(SAMPLE_SPEC_PATH.read_text(encoding="utf-8"))
    draft_spec["status"] = "draft"

    draft_path = tmp_path / "draft_spec.json"
    draft_path.write_text(json.dumps(draft_spec), encoding="utf-8")

    with pytest.raises(ValueError, match="status='confirmed'"):
        service.create_run(spec_path=draft_path)


# ---------------------------------------------------------------------------
# 4. test_get_run
# ---------------------------------------------------------------------------


def test_get_run(service: RunService) -> None:
    """get_run should return the same run state that was created."""
    created = service.create_run(spec_path=SAMPLE_SPEC_PATH, plan_path=SAMPLE_PLAN_PATH)

    fetched = service.get_run(created.run_id)

    assert fetched.run_id == created.run_id
    assert fetched.spec_id == created.spec_id
    assert fetched.plan_id == created.plan_id
    assert fetched.status == created.status


# ---------------------------------------------------------------------------
# 5. test_control_run_stop
# ---------------------------------------------------------------------------


def test_control_run_stop(service: RunService, store: ArtifactStore) -> None:
    """Stopping a running run should set status='stopped' and stop_reason='user_stopped'."""
    run = service.create_run(spec_path=SAMPLE_SPEC_PATH, plan_path=SAMPLE_PLAN_PATH)

    # Manually transition to running so control_run(stop) is valid
    run.transition_to(RunStatus.RUNNING)
    run.updated_at = datetime.now(timezone.utc)
    store.save_json(run.run_id, "run.json", run)

    stopped = service.control_run(run.run_id, "stop")

    assert stopped.status == RunStatus.STOPPED
    assert stopped.stop_reason == "user_stopped"


# ---------------------------------------------------------------------------
# 6. test_get_run_report_after_completion
# ---------------------------------------------------------------------------


def test_get_run_report_after_completion(
    service: RunService, store: ArtifactStore
) -> None:
    """After a succeeded run with iteration data, get_run_report returns a valid report."""
    run = service.create_run(spec_path=SAMPLE_SPEC_PATH, plan_path=SAMPLE_PLAN_PATH)

    # Simulate two completed iterations
    now = datetime.now(timezone.utc)
    for idx in (1, 2):
        iter_id = f"iter_{idx}"
        iteration = ExperimentIteration(
            iteration_id=iter_id,
            run_id=run.run_id,
            index=idx,
            commands=["python train.py"],
            metrics={"r_squared": 0.85 + idx * 0.05},
            cost_usage=CostUsage(
                llm_calls=1,
                input_tokens=100,
                output_tokens=50,
                estimated_cost_usd=0.01,
            ),
            status=IterationStatus.succeeded,
            artifact_dir=f"iterations/{iter_id}",
            started_at=now,
            ended_at=now,
        )
        store.save_json(
            run.run_id,
            f"iterations/{iter_id}/iteration.json",
            iteration,
        )
        # Write a stdout log so evidence_map will reference it
        store.save_text(
            run.run_id,
            f"iterations/{iter_id}/stdout.log",
            f"Iteration {idx} output",
        )

    # Transition run to succeeded
    run.transition_to(RunStatus.RUNNING)
    run.transition_to(RunStatus.SUCCEEDED)
    run.iteration_count = 2
    run.best_iteration_id = "iter_2"
    run.updated_at = now
    store.save_json(run.run_id, "run.json", run)

    # Generate and verify the report
    report = service.get_run_report(run.run_id)

    assert report.run_id == run.run_id
    assert report.best_result is not None
    assert report.best_result.iteration_id == "iter_2"

    # evidence_map must be non-empty and all referenced paths must exist
    assert len(report.evidence_map) > 0
    for entry in report.evidence_map:
        for path in entry.evidence_paths:
            assert store.path_exists(run.run_id, path), f"Evidence path missing: {path}"
