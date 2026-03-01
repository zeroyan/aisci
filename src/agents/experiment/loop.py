"""Main experiment loop: plan -> tool-use agent -> decide."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from src.agents.experiment.tool_agent import ToolAgent
from src.llm.client import LLMClient
from src.sandbox.base import SandboxExecutor
from src.schemas import CostUsage, ResourceUsage
from src.schemas.experiment import ExperimentIteration, ExperimentRun, IterationStatus
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.schemas.state import RunStatus, StopReason
from src.storage.artifact import ArtifactStore

logger = logging.getLogger(__name__)

DEFAULT_CONSECUTIVE_FAILURE_LIMIT = 3


class ExperimentLoop:
    """Orchestrates the plan->tool-agent->decide cycle."""

    def __init__(
        self,
        llm: LLMClient,
        sandbox: SandboxExecutor,
        store: ArtifactStore,
        consecutive_failure_limit: int = DEFAULT_CONSECUTIVE_FAILURE_LIMIT,
        max_turns_per_iteration: int = 20,
    ) -> None:
        self.llm = llm
        self.sandbox = sandbox
        self.store = store
        self.consecutive_failure_limit = consecutive_failure_limit
        self.max_turns_per_iteration = max_turns_per_iteration

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

            # --- Step 1: Tool-use agent iteration ---
            logger.info("Iteration %d: tool-use agent", iteration_index)
            iteration_started = datetime.now(timezone.utc)

            # Prepare workspace
            workspace = (
                Path(self.store.runs_dir)
                / run_id
                / "iterations"
                / f"it_{iteration_index:04d}"
                / "workspace"
            )
            workspace.mkdir(parents=True, exist_ok=True)

            # Build system prompt
            system_prompt = self._build_system_prompt(spec, plan)

            # Build initial prompt
            initial_prompt = self._build_initial_prompt(spec, plan, iterations)

            # Create ToolAgent and run
            agent = ToolAgent(
                llm_client=self.llm,
                sandbox=self.sandbox,
                system_prompt=system_prompt,
                max_turns=self.max_turns_per_iteration,
            )

            try:
                tool_record = agent.run_iteration(
                    run_id=run_id,
                    iteration_index=iteration_index,
                    workspace=workspace,
                    initial_prompt=initial_prompt,
                )
            except Exception as e:
                logger.error("ToolAgent failed: %s", e)
                consecutive_failures += 1
                if consecutive_failures >= self.consecutive_failure_limit:
                    logger.warning(
                        "Consecutive failure limit reached, requesting human"
                    )
                    experiment_run.stop_reason = StopReason.FATAL_ERROR
                    experiment_run.transition_to(RunStatus.FAILED)
                    break
                continue

            # --- Step 2: Build iteration record ---
            iteration_id = f"it_{iteration_index:04d}"
            artifact_dir = f"iterations/{iteration_id}"

            # Determine iteration status from tool_record
            if tool_record.status == "finished" and tool_record.finish_result:
                if tool_record.finish_result.success:
                    iter_status = IterationStatus.succeeded
                else:
                    iter_status = IterationStatus.failed
            else:
                iter_status = IterationStatus.failed

            # Parse metrics from workspace (if metrics.json exists)
            metrics: dict[str, float] | None = None
            metrics_file = workspace / "metrics.json"
            if metrics_file.exists():
                import json

                try:
                    metrics = json.loads(metrics_file.read_text())
                except Exception:
                    pass

            # LLM cost for this iteration
            iter_cost = CostUsage(
                llm_calls=self.llm.accumulated_cost.llm_calls
                - experiment_run.cost_usage.llm_calls,
                input_tokens=max(
                    0,
                    self.llm.accumulated_cost.input_tokens
                    - experiment_run.cost_usage.input_tokens,
                ),
                output_tokens=max(
                    0,
                    self.llm.accumulated_cost.output_tokens
                    - experiment_run.cost_usage.output_tokens,
                ),
                estimated_cost_usd=max(
                    0.0,
                    self.llm.accumulated_cost.estimated_cost_usd
                    - experiment_run.cost_usage.estimated_cost_usd,
                ),
            )

            iteration_ended = datetime.now(timezone.utc)
            iteration = ExperimentIteration(
                iteration_id=iteration_id,
                run_id=run_id,
                index=iteration_index,
                code_change_summary=f"Tool-use agent: {tool_record.total_turns} turns",
                commands=["tool-use-agent"],  # Placeholder for tool-use mode
                metrics=metrics,
                resource_usage=ResourceUsage(),  # Tool-use doesn't have single resource usage
                cost_usage=iter_cost,
                status=iter_status,
                error_summary=tool_record.finish_result.failure_reason
                if tool_record.finish_result and not tool_record.finish_result.success
                else None,
                artifact_dir=artifact_dir,
                started_at=iteration_started,
                ended_at=iteration_ended,
            )

            # Save iteration artifacts
            self.store.save_json(run_id, f"{artifact_dir}/iteration.json", iteration)
            self.store.save_json(run_id, f"{artifact_dir}/tool_record.json", tool_record)

            iterations.append(iteration)
            experiment_run.iteration_count = iteration_index

            # --- Step 3: Decide based on finish_result ---
            logger.info(
                "Iteration %d: decide (status=%s)", iteration_index, iter_status
            )

            # Update run cost from accumulated LLM costs
            experiment_run.cost_usage = self.llm.accumulated_cost

            # Check finish_result
            if tool_record.finish_result:
                if tool_record.finish_result.success:
                    logger.info("Agent finished successfully")
                    experiment_run.stop_reason = StopReason.GOAL_MET
                    experiment_run.transition_to(RunStatus.SUCCEEDED)
                    break
                else:
                    # Failed but finished
                    consecutive_failures += 1
                    if consecutive_failures >= self.consecutive_failure_limit:
                        logger.warning("Consecutive failure limit reached")
                        experiment_run.stop_reason = StopReason.FATAL_ERROR
                        experiment_run.transition_to(RunStatus.FAILED)
                        break
            else:
                # No finish_result (timeout or error)
                consecutive_failures += 1
                if consecutive_failures >= self.consecutive_failure_limit:
                    logger.warning("Consecutive failure limit reached")
                    experiment_run.stop_reason = StopReason.FATAL_ERROR
                    experiment_run.transition_to(RunStatus.FAILED)
                    break

            # Continue to next iteration
            if iter_status == IterationStatus.succeeded:
                consecutive_failures = 0
                if metrics:
                    self._update_best_iteration(experiment_run, iteration, spec)

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

    def _build_system_prompt(self, spec: ResearchSpec, plan: ExperimentPlan) -> str:
        """Build system prompt for ToolAgent."""
        return f"""You are an autonomous experiment agent. Your goal is to implement and run the experiment described below.

**Research Goal**: {spec.objective}

**Experiment Plan**:
{plan.method_summary}

**Evaluation Protocol**:
{plan.evaluation_protocol}

**Available Tools**:
- write_file(path, content): Write code/data files
- run_bash(cmd): Execute bash commands (install deps, run scripts)
- read_file(path): Read file contents
- finish(summary, artifacts, success, failure_reason): Signal completion

**Instructions**:
1. Implement the experiment step by step
2. Write all necessary code files
3. Install dependencies if needed
4. Run the experiment
5. Collect metrics and save to metrics.json
6. Call finish() with summary and results

Work autonomously. If you encounter errors, debug and fix them. Call finish() when done or if unrecoverable error occurs."""

    def _build_initial_prompt(
        self,
        spec: ResearchSpec,
        plan: ExperimentPlan,
        iterations: list[ExperimentIteration],
    ) -> str:
        """Build initial prompt for ToolAgent."""
        if not iterations:
            return f"""Start implementing the experiment plan.

**Steps to follow**:
{chr(10).join(f"{i+1}. {step.description}" for i, step in enumerate(plan.steps))}

Begin with step 1."""
        else:
            last_iter = iterations[-1]
            return f"""Previous iteration {last_iter.index} status: {last_iter.status}

{f"Error: {last_iter.error_summary}" if last_iter.error_summary else ""}

Continue the experiment. Review previous work, fix any issues, and proceed."""

