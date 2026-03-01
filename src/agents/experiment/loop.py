"""Main experiment loop: plan -> codegen -> execute -> analyze -> decide."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from src.schemas import CostUsage
from src.schemas.experiment import ExperimentIteration, ExperimentRun, IterationStatus
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.schemas.sandbox_io import SandboxRequest, SandboxStatus
from src.schemas.state import RunStatus, StopReason
from src.agents.experiment.codegen import CodegenAgent
from src.agents.experiment.analyzer import AnalyzerAgent
from src.sandbox.base import SandboxExecutor
from src.storage.artifact import ArtifactStore
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_CONSECUTIVE_FAILURE_LIMIT = 3


class ExperimentLoop:
    """Orchestrates the plan->codegen->execute->analyze->decide cycle."""

    def __init__(
        self,
        llm: LLMClient,
        sandbox: SandboxExecutor,
        store: ArtifactStore,
        consecutive_failure_limit: int = DEFAULT_CONSECUTIVE_FAILURE_LIMIT,
    ) -> None:
        self.codegen = CodegenAgent(llm)
        self.analyzer = AnalyzerAgent(llm)
        self.sandbox = sandbox
        self.store = store
        self.consecutive_failure_limit = consecutive_failure_limit

    def run(
        self,
        experiment_run: ExperimentRun,
        spec: ResearchSpec,
        plan: ExperimentPlan,
    ) -> ExperimentRun:
        """Execute the full experiment loop until a stop condition is met.

        Mutates and returns *experiment_run* with updated status, cost, etc.
        """
        run_id = experiment_run.run_id
        constraints = spec.constraints
        run_start = time.monotonic()
        consecutive_failures = 0
        iterations: list[ExperimentIteration] = []

        # Transition to running
        experiment_run.transition_to(RunStatus.RUNNING)
        self.store.save_json(run_id, "run.json", experiment_run)

        logger.info("Starting experiment loop for run %s", run_id)

        while True:
            iteration_index = experiment_run.iteration_count + 1

            # --- Guard: max iterations ---
            if iteration_index > constraints.max_iterations:
                logger.info("Max iterations (%d) reached", constraints.max_iterations)
                experiment_run.stop_reason = StopReason.MAX_ITERATIONS
                experiment_run.transition_to(RunStatus.STOPPED)
                break

            # --- Guard: budget ---
            if (
                experiment_run.cost_usage.estimated_cost_usd
                >= constraints.max_budget_usd
            ):
                logger.info(
                    "Budget exhausted ($%.4f >= $%.2f)",
                    experiment_run.cost_usage.estimated_cost_usd,
                    constraints.max_budget_usd,
                )
                experiment_run.stop_reason = StopReason.BUDGET_EXHAUSTED
                experiment_run.transition_to(RunStatus.BUDGET_EXHAUSTED)
                break

            # --- Guard: runtime ---
            elapsed_hours = (time.monotonic() - run_start) / 3600
            if elapsed_hours >= constraints.max_runtime_hours:
                logger.info(
                    "Runtime limit reached (%.2fh >= %.2fh)",
                    elapsed_hours,
                    constraints.max_runtime_hours,
                )
                experiment_run.stop_reason = StopReason.TIMEOUT
                experiment_run.transition_to(RunStatus.TIMEOUT)
                break

            # --- Step 1: Codegen ---
            logger.info("Iteration %d: codegen", iteration_index)
            iteration_started = datetime.now(timezone.utc)
            try:
                code_snapshot = self.codegen.generate(spec, plan, iterations)
            except Exception as e:
                logger.error("Codegen failed: %s", e)
                consecutive_failures += 1
                if consecutive_failures >= self.consecutive_failure_limit:
                    logger.warning(
                        "Consecutive failure limit reached, requesting human"
                    )
                    experiment_run.stop_reason = StopReason.FATAL_ERROR
                    experiment_run.transition_to(RunStatus.FAILED)
                    break
                continue

            # --- Step 2: Execute ---
            logger.info("Iteration %d: execute", iteration_index)
            request = SandboxRequest(
                request_id=f"req_{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                iteration_index=iteration_index,
                code_snapshot=code_snapshot,
                timeout_sec=min(
                    int((constraints.max_runtime_hours - elapsed_hours) * 3600),
                    1800,
                ),
            )
            response = self.sandbox.execute(request)

            # --- Step 3: Build iteration record ---
            iteration_id = f"it_{iteration_index:04d}"
            artifact_dir = f"iterations/{iteration_id}"

            # Parse metrics from sandbox output
            metrics: dict[str, float] | None = None
            if response.output_files.get("metrics.json"):
                import json

                try:
                    metrics = json.loads(response.output_files["metrics.json"])
                except Exception:
                    pass

            # Determine iteration status
            if response.status == SandboxStatus.succeeded:
                iter_status = IterationStatus.succeeded
            else:
                iter_status = IterationStatus.failed

            # LLM cost for this iteration (from the codegen call)
            iter_cost = CostUsage(
                llm_calls=self.codegen.llm.accumulated_cost.llm_calls
                - (experiment_run.cost_usage.llm_calls),
                input_tokens=max(
                    0,
                    self.codegen.llm.accumulated_cost.input_tokens
                    - experiment_run.cost_usage.input_tokens,
                ),
                output_tokens=max(
                    0,
                    self.codegen.llm.accumulated_cost.output_tokens
                    - experiment_run.cost_usage.output_tokens,
                ),
                estimated_cost_usd=max(
                    0.0,
                    self.codegen.llm.accumulated_cost.estimated_cost_usd
                    - experiment_run.cost_usage.estimated_cost_usd,
                ),
            )

            iteration_ended = datetime.now(timezone.utc)
            iteration = ExperimentIteration(
                iteration_id=iteration_id,
                run_id=run_id,
                index=iteration_index,
                code_change_summary=f"Generated code with {len(code_snapshot.files)} files",
                commands=[code_snapshot.entrypoint],
                metrics=metrics,
                resource_usage=response.resource_usage,
                cost_usage=iter_cost,
                status=iter_status,
                error_summary=response.stderr[:500]
                if iter_status == IterationStatus.failed
                else None,
                artifact_dir=artifact_dir,
                started_at=iteration_started,
                ended_at=iteration_ended,
            )

            # Save iteration artifacts
            self.store.save_json(run_id, f"{artifact_dir}/iteration.json", iteration)
            if response.stdout:
                self.store.save_text(
                    run_id, f"{artifact_dir}/stdout.log", response.stdout
                )
            if response.stderr:
                self.store.save_text(
                    run_id, f"{artifact_dir}/stderr.log", response.stderr
                )

            iterations.append(iteration)
            experiment_run.iteration_count = iteration_index

            # --- Step 4: Analyze ---
            logger.info(
                "Iteration %d: analyze (status=%s)", iteration_index, iter_status
            )
            try:
                decision = self.analyzer.analyze(spec, iteration, response)
            except Exception as e:
                logger.error("Analyzer failed: %s", e)
                consecutive_failures += 1
                if consecutive_failures >= self.consecutive_failure_limit:
                    experiment_run.stop_reason = StopReason.FATAL_ERROR
                    experiment_run.transition_to(RunStatus.FAILED)
                    break
                # Update cost and continue
                experiment_run.cost_usage = self.codegen.llm.accumulated_cost
                self.store.save_json(run_id, "run.json", experiment_run)
                continue

            # Save decision
            self.store.save_json(run_id, f"{artifact_dir}/decision.json", decision)

            # Update run cost from accumulated LLM costs
            experiment_run.cost_usage = self.codegen.llm.accumulated_cost

            # --- Step 5: Decide ---
            if decision.decision == "stop":
                logger.info("Agent decided to stop: %s", decision.stop_reason)
                if decision.stop_reason == "goal_met":
                    experiment_run.stop_reason = StopReason.GOAL_MET
                    experiment_run.transition_to(RunStatus.SUCCEEDED)
                elif decision.stop_reason == "no_progress":
                    experiment_run.stop_reason = StopReason.NO_PROGRESS
                    experiment_run.transition_to(RunStatus.STOPPED)
                elif decision.stop_reason == "fatal_error":
                    experiment_run.stop_reason = StopReason.FATAL_ERROR
                    experiment_run.transition_to(RunStatus.FAILED)
                else:
                    experiment_run.stop_reason = StopReason.NO_PROGRESS
                    experiment_run.transition_to(RunStatus.STOPPED)
                break

            if decision.decision == "request_human":
                logger.info("Agent requesting human intervention")
                experiment_run.stop_reason = StopReason.FATAL_ERROR
                experiment_run.transition_to(RunStatus.FAILED)
                break

            # decision == "continue"
            if iter_status == IterationStatus.succeeded:
                consecutive_failures = 0
                # Track best iteration by metric performance
                if metrics:
                    self._update_best_iteration(experiment_run, iteration, spec)
            else:
                consecutive_failures += 1
                if consecutive_failures >= self.consecutive_failure_limit:
                    logger.warning("Consecutive failure limit reached")
                    experiment_run.stop_reason = StopReason.FATAL_ERROR
                    experiment_run.transition_to(RunStatus.FAILED)
                    break

            # Save run state
            self.store.save_json(run_id, "run.json", experiment_run)
            logger.info("Iteration %d complete, continuing...", iteration_index)

        # Final save
        experiment_run.updated_at = datetime.now(timezone.utc)
        self.store.save_json(run_id, "run.json", experiment_run)
        logger.info(
            "Experiment loop finished: status=%s, iterations=%d, cost=$%.4f",
            experiment_run.status,
            experiment_run.iteration_count,
            experiment_run.cost_usage.estimated_cost_usd,
        )
        return experiment_run

    def _update_best_iteration(
        self,
        run: ExperimentRun,
        iteration: ExperimentIteration,
        spec: ResearchSpec,
    ) -> None:
        """Update best_iteration_id based on metric comparison."""
        if not iteration.metrics:
            return

        # Simple heuristic: check first metric's target
        primary_metric = spec.metrics[0]
        metric_val = iteration.metrics.get(primary_metric.name)
        if metric_val is None:
            return

        # Always update if no best yet
        if run.best_iteration_id is None:
            run.best_iteration_id = iteration.iteration_id
            return

        # For now, always update to latest successful iteration with metrics
        # A more sophisticated comparison would load the best iteration's metrics
        run.best_iteration_id = iteration.iteration_id
