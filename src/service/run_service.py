"""Run service: high-level API for managing experiment runs."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.schemas import BestResult, EvidenceEntry, FailedAttempt
from src.schemas.experiment import ExperimentIteration, ExperimentRun, IterationStatus
from src.schemas.report import ExperimentReport
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.schemas.state import RunStatus, StopReason, TERMINAL_STATUSES
from src.agents.experiment.loop import ExperimentLoop
from src.llm.client import LLMClient, LLMConfig
from src.sandbox.subprocess_sandbox import SubprocessSandbox
from src.storage.artifact import ArtifactStore

logger = logging.getLogger(__name__)


class RunService:
    """Service layer for CreateRun / StartRun / ControlRun / GetRun / GetRunReport."""

    def __init__(
        self,
        store: ArtifactStore | None = None,
        llm_config: LLMConfig | None = None,
        consecutive_failure_limit: int = 3,
    ) -> None:
        self.store = store or ArtifactStore()
        self.llm_config = llm_config or LLMConfig()
        self.consecutive_failure_limit = consecutive_failure_limit

    # --- CreateRun -----------------------------------------------------------

    def create_run(
        self,
        spec_path: str | Path,
        plan_path: str | Path | None = None,
    ) -> ExperimentRun:
        """Create a new experiment run from a spec (and optional plan) file."""
        spec = self._load_spec(spec_path)
        if spec.status != "confirmed":
            raise ValueError(
                f"ResearchSpec must have status='confirmed', got '{spec.status}'"
            )

        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.store.create_run_dir(run_id)

        # Save spec
        self.store.save_json(run_id, "spec/research_spec.json", spec)

        # Load or generate plan
        if plan_path:
            plan = self._load_plan(plan_path)
        else:
            plan = self._generate_minimal_plan(spec)

        self.store.save_json(run_id, "plan/experiment_plan.json", plan)

        # Create run record
        now = datetime.now(timezone.utc)
        run = ExperimentRun(
            run_id=run_id,
            spec_id=spec.spec_id,
            plan_id=plan.plan_id,
            created_at=now,
            updated_at=now,
        )
        self.store.save_json(run_id, "run.json", run)

        logger.info("Created run %s for spec %s", run_id, spec.spec_id)
        return run

    # --- StartRun ------------------------------------------------------------

    def start_run(self, run_id: str) -> ExperimentRun:
        """Load spec/plan and execute the experiment loop."""
        run = self.get_run(run_id)
        if run.status != RunStatus.QUEUED:
            raise ValueError(
                f"Run {run_id} is in status '{run.status}', expected 'queued'"
            )

        spec = ResearchSpec(**self.store.load_json(run_id, "spec/research_spec.json"))
        plan = ExperimentPlan(
            **self.store.load_json(run_id, "plan/experiment_plan.json")
        )

        llm = LLMClient(self.llm_config)
        llm.validate_provider_ready()
        sandbox = SubprocessSandbox(runs_dir=self.store.runs_dir)
        loop = ExperimentLoop(
            llm=llm,
            sandbox=sandbox,
            store=self.store,
            consecutive_failure_limit=self.consecutive_failure_limit,
        )

        run = loop.run(run, spec, plan)

        # Generate report after run completes
        if run.status in TERMINAL_STATUSES:
            self._generate_report(run_id, run, spec)

        return run

    # --- ControlRun ----------------------------------------------------------

    def control_run(self, run_id: str, action: str) -> ExperimentRun:
        """Control a running experiment: pause / resume / stop."""
        run = self.get_run(run_id)

        if action == "stop":
            if run.status in TERMINAL_STATUSES:
                logger.warning(
                    "Run %s already in terminal state %s", run_id, run.status
                )
                return run
            run.stop_reason = StopReason.USER_STOPPED
            run.transition_to(RunStatus.STOPPED)
        elif action == "pause":
            run.transition_to(RunStatus.PAUSED)
        elif action == "resume":
            run.transition_to(RunStatus.RUNNING)
        else:
            raise ValueError(f"Unknown action: {action}")

        run.updated_at = datetime.now(timezone.utc)
        self.store.save_json(run_id, "run.json", run)
        return run

    # --- GetRun --------------------------------------------------------------

    def get_run(self, run_id: str) -> ExperimentRun:
        """Load the current state of a run."""
        data = self.store.load_json(run_id, "run.json")
        return ExperimentRun(**data)

    # --- GetRunReport --------------------------------------------------------

    def get_run_report(self, run_id: str) -> ExperimentReport:
        """Load an existing report or generate one."""
        if self.store.path_exists(run_id, "report.json"):
            data = self.store.load_json(run_id, "report.json")
            return ExperimentReport(**data)

        run = self.get_run(run_id)
        if run.status not in TERMINAL_STATUSES:
            raise ValueError(
                f"Run {run_id} is still in status '{run.status}', cannot generate report"
            )

        spec = ResearchSpec(**self.store.load_json(run_id, "spec/research_spec.json"))
        return self._generate_report(run_id, run, spec)

    # --- Internal helpers ----------------------------------------------------

    def _load_spec(self, path: str | Path) -> ResearchSpec:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return ResearchSpec(**raw)

    def _load_plan(self, path: str | Path) -> ExperimentPlan:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return ExperimentPlan(**raw)

    def _generate_minimal_plan(self, spec: ResearchSpec) -> ExperimentPlan:
        """Create a minimal ExperimentPlan from a ResearchSpec."""
        from src.schemas import PlanStep

        return ExperimentPlan(
            plan_id=f"plan_auto_{uuid.uuid4().hex[:6]}",
            spec_id=spec.spec_id,
            method_summary=f"Auto-generated plan for: {spec.objective}",
            evaluation_protocol="Run experiment, evaluate metrics against targets",
            steps=[
                PlanStep(
                    step_id="step_1",
                    description=spec.objective,
                    expected_output="metrics.json with evaluation results",
                )
            ],
            created_at=datetime.now(timezone.utc),
        )

    def _generate_report(
        self,
        run_id: str,
        run: ExperimentRun,
        spec: ResearchSpec,
    ) -> ExperimentReport:
        """Build ExperimentReport by aggregating all iterations."""
        iterations = self._load_all_iterations(run_id)

        # Find best result
        best_metrics: dict[str, float] = {}
        best_iter_id = run.best_iteration_id or ""
        failed_attempts: list[FailedAttempt] = []

        for it in iterations:
            if it.status == IterationStatus.succeeded and it.metrics:
                if it.iteration_id == best_iter_id:
                    best_metrics = it.metrics
                elif not best_metrics and not best_iter_id:
                    best_metrics = it.metrics
                    best_iter_id = it.iteration_id
            elif it.status == IterationStatus.failed:
                failed_attempts.append(
                    FailedAttempt(
                        iteration_id=it.iteration_id,
                        reason=it.error_summary or "Unknown error",
                    )
                )

        # If we have a best_iter_id from the run but didn't find its metrics, load them
        if best_iter_id and not best_metrics:
            for it in iterations:
                if it.iteration_id == best_iter_id and it.metrics:
                    best_metrics = it.metrics
                    break

        if not best_metrics:
            best_metrics = {"no_metrics": 0.0}
            if iterations:
                best_iter_id = iterations[-1].iteration_id
            else:
                best_iter_id = "none"

        # Build evidence map
        evidence_entries: list[EvidenceEntry] = []
        for it in iterations:
            paths = [f"iterations/{it.iteration_id}/iteration.json"]
            if self.store.path_exists(
                run_id, f"iterations/{it.iteration_id}/stdout.log"
            ):
                paths.append(f"iterations/{it.iteration_id}/stdout.log")
            evidence_entries.append(
                EvidenceEntry(
                    claim=f"Iteration {it.index}: status={it.status}, metrics={it.metrics}",
                    evidence_paths=paths,
                )
            )

        if not evidence_entries:
            evidence_entries.append(
                EvidenceEntry(
                    claim="No iterations completed",
                    evidence_paths=["run.json"],
                )
            )

        # Build summary
        summary_parts = [
            f"Experiment run {run_id} completed with status: {run.status}.",
            f"Total iterations: {run.iteration_count}.",
            f"Total cost: ${run.cost_usage.estimated_cost_usd:.4f}.",
        ]
        if run.stop_reason:
            summary_parts.append(f"Stop reason: {run.stop_reason}.")

        report = ExperimentReport(
            report_id=f"report_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            summary=" ".join(summary_parts),
            best_result=BestResult(iteration_id=best_iter_id, metrics=best_metrics),
            key_findings=[
                f"Best iteration: {best_iter_id} with metrics {best_metrics}",
                f"Failed attempts: {len(failed_attempts)}",
            ],
            failed_attempts=failed_attempts,
            evidence_map=evidence_entries,
            next_actions=[],
            generated_at=datetime.now(timezone.utc),
        )

        self.store.save_json(run_id, "report.json", report)
        logger.info("Generated report for run %s", run_id)
        return report

    def _load_all_iterations(self, run_id: str) -> list[ExperimentIteration]:
        """Load all iteration records for a run, sorted by index."""
        iterations: list[ExperimentIteration] = []
        iter_base = self.store.run_path(run_id) / "iterations"
        if not iter_base.exists():
            return iterations

        for iter_dir in sorted(iter_base.iterdir()):
            iter_file = iter_dir / "iteration.json"
            if iter_file.exists():
                data = json.loads(iter_file.read_text(encoding="utf-8"))
                iterations.append(ExperimentIteration(**data))

        return sorted(iterations, key=lambda x: x.index)
