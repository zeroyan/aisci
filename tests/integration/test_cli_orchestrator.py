"""CLI regression tests for orchestrator commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli import app
from src.schemas import Baseline, Constraints, Metric, PlanStep
from src.schemas.research_spec import ExperimentPlan, ResearchSpec


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def test_run_dir(tmp_path):
    """Create test run directory with spec and plan."""
    run_id = "test_run_001"
    run_dir = tmp_path / "runs" / run_id

    # Create spec directory
    spec_dir = run_dir / "spec"
    spec_dir.mkdir(parents=True)

    # Create plan directory
    plan_dir = run_dir / "plan"
    plan_dir.mkdir(parents=True)

    # Create test spec
    spec = ResearchSpec(
        spec_id="test_spec",
        title="Test Spec",
        objective="Test objective",
        metrics=[Metric(name="accuracy", direction="maximize")],
        constraints=Constraints(
            max_budget_usd=10.0, max_runtime_hours=0.1, max_iterations=2
        ),
        status="confirmed",
    )
    spec_path = spec_dir / "research_spec.json"
    spec_path.write_text(spec.model_dump_json())

    # Create test plan
    plan = ExperimentPlan(
        plan_id="test_plan",
        spec_id="test_spec",
        title="Test Plan",
        steps=[
            PlanStep(
                step_id="step_1",
                description="Test step",
                expected_output="Test output",
            )
        ],
        baseline=Baseline(status="pending"),
        method_summary="Test method",
        evaluation_protocol="Test protocol",
    )
    plan_path = plan_dir / "experiment_plan.json"
    plan_path.write_text(plan.model_dump_json())

    return tmp_path, run_id


@patch("cli.LLMClient")
@patch("cli.ExperimentLoop")
def test_run_start_with_orchestrator(
    mock_loop_class, mock_llm_class, runner, test_run_dir, monkeypatch
):
    """Test 'run start --enable-orchestrator' command."""
    tmp_path, run_id = test_run_dir

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm_class.return_value = mock_llm

    # Mock ExperimentLoop
    mock_loop = MagicMock()
    mock_loop_class.return_value = mock_loop

    # Mock loop.run() to return a completed run
    from src.schemas.experiment import ExperimentRun
    from datetime import datetime, timezone

    mock_run = ExperimentRun(
        run_id=f"{run_id}_branch_001",
        spec_id="test_spec",
        plan_id="test_plan",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    mock_loop.run.return_value = mock_run

    # Run command
    result = runner.invoke(
        app,
        [
            "run",
            "start",
            run_id,
            "--enable-orchestrator",
            "--num-branches",
            "1",
        ],
    )

    # Verify
    assert result.exit_code == 0, f"Command failed: {result.stdout}"
    assert "Orchestration completed" in result.stdout
    assert "Status:" in result.stdout
    assert "Total cost:" in result.stdout
    assert "Total time:" in result.stdout


@patch("cli.LLMClient")
@patch("cli.ExperimentLoop")
def test_orchestrator_run_command(
    mock_loop_class, mock_llm_class, runner, test_run_dir, monkeypatch
):
    """Test 'orchestrator run' command."""
    tmp_path, run_id = test_run_dir

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Mock LLM client
    mock_llm = MagicMock()
    mock_llm_class.return_value = mock_llm

    # Mock ExperimentLoop
    mock_loop = MagicMock()
    mock_loop_class.return_value = mock_loop

    # Mock loop.run() to return a completed run
    from src.schemas.experiment import ExperimentRun
    from datetime import datetime, timezone

    mock_run = ExperimentRun(
        run_id=f"{run_id}_branch_001",
        spec_id="test_spec",
        plan_id="test_plan",
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    mock_loop.run.return_value = mock_run

    # Run command
    result = runner.invoke(
        app,
        [
            "orchestrator",
            "run",
            run_id,
            "--num-branches",
            "1",
            "--max-cost-usd",
            "5.0",
            "--max-time-seconds",
            "300",
        ],
    )

    # Verify
    assert result.exit_code == 0, f"Command failed: {result.stdout}"
    assert "Starting multi-branch orchestration" in result.stdout
    assert "Branches: 1" in result.stdout
    assert "Max cost: $5.00" in result.stdout
    assert "Max time: 300s" in result.stdout


def test_orchestrator_prevents_placeholder_regression(runner, test_run_dir, monkeypatch):
    """Verify orchestrator doesn't return 0/0/0 placeholder results.

    This test ensures we don't regress to placeholder behavior.
    """
    tmp_path, run_id = test_run_dir

    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Mock LLM client and ExperimentLoop
    with patch("cli.LLMClient") as mock_llm_class, patch(
        "cli.ExperimentLoop"
    ) as mock_loop_class:
        mock_llm = MagicMock()
        mock_llm_class.return_value = mock_llm

        mock_loop = MagicMock()
        mock_loop_class.return_value = mock_loop

        # Mock loop.run() to return a completed run
        from src.schemas.experiment import ExperimentRun
        from datetime import datetime, timezone

        mock_run = ExperimentRun(
            run_id=f"{run_id}_branch_001",
            spec_id="test_spec",
            plan_id="test_plan",
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        mock_loop.run.return_value = mock_run

        # Run command
        result = runner.invoke(
            app,
            [
                "orchestrator",
                "run",
                run_id,
                "--num-branches",
                "1",
            ],
        )

        # Verify NOT placeholder behavior
        assert result.exit_code == 0
        output = result.stdout

        # Parse output to check values
        # Should NOT see "Total time: 0.0s" (placeholder)
        assert "Total time: 0.0s" not in output, "Detected placeholder time=0"

        # Should see actual status
        assert "Status:" in output
