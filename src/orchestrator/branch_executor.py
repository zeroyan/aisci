"""Branch executor for parallel execution."""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.agents.experiment.loop import ExperimentLoop
from src.llm.client import LLMClient
from src.orchestrator.failure_report import FailureReportGenerator
from src.sandbox.base import SandboxExecutor
from src.sandbox.docker_config import DockerConfig
from src.sandbox.docker_sandbox import DockerSandbox
from src.sandbox.subprocess_sandbox import SubprocessSandbox
from src.schemas.experiment import ExperimentRun
from src.schemas.orchestrator import BranchConfig, BranchResult
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.storage.artifact import ArtifactStore

logger = logging.getLogger(__name__)


class BranchExecutor:
    """Execute branches in parallel using multiprocessing.

    Each branch runs in a separate process for isolation.
    """

    def __init__(
        self,
        max_workers: int = 3,
        llm_client: LLMClient | None = None,
        max_iterations: int = 5,
        early_stop_threshold: int = 2,
        enable_docker: bool = False,
        docker_config: DockerConfig | None = None,
    ) -> None:
        """Initialize executor.

        Args:
            max_workers: Maximum number of parallel workers (max 3)
            llm_client: LLM client for execution (REQUIRED)
            max_iterations: Maximum experiment loop iterations
            early_stop_threshold: Early stop threshold
            enable_docker: Use DockerSandbox instead of SubprocessSandbox
            docker_config: Docker configuration (uses defaults if None)
        """
        if max_workers > 3:
            raise ValueError(f"max_workers must be <= 3, got {max_workers}")
        if llm_client is None:
            raise ValueError("llm_client is required for branch execution")

        self.max_workers = max_workers
        self.llm_client = llm_client
        self.max_iterations = max_iterations
        self.early_stop_threshold = early_stop_threshold
        self.enable_docker = enable_docker
        self.docker_config = docker_config or DockerConfig()

    def execute_branches(
        self,
        branch_configs: list[BranchConfig],
        spec: ResearchSpec,
        plan: ExperimentPlan,
    ) -> list[BranchResult]:
        """Execute branches sequentially (parallel execution in future).

        Args:
            branch_configs: List of branch configurations
            spec: Research specification
            plan: Experiment plan

        Returns:
            List of branch results

        Note:
            Currently executes sequentially. Parallel execution with
            multiprocessing.Pool will be added in future iterations.
        """
        if not branch_configs:
            return []

        # Execute sequentially for now
        results = []
        for config in branch_configs:
            result = self._execute_single_branch(config, spec, plan)
            results.append(result)

        return results

    def _execute_single_branch(
        self,
        config: BranchConfig,
        spec: ResearchSpec,
        plan: ExperimentPlan,
    ) -> BranchResult:
        """Execute a single branch using ExperimentLoop.

        Args:
            config: Branch configuration
            spec: Research specification
            plan: Experiment plan

        Returns:
            Branch result with real execution metrics
        """
        logger.info(f"Executing branch {config.branch_id}")
        start_time = time.time()

        try:
            # Create sandbox
            sandbox: SandboxExecutor
            if self.enable_docker:
                sandbox = DockerSandbox(config=self.docker_config)
            else:
                sandbox = SubprocessSandbox(workspace_path=config.workspace_path)

            # Create artifact store
            store = ArtifactStore(runs_dir=config.workspace_path.parent.parent)

            # Create experiment run
            experiment_run = ExperimentRun(
                run_id=config.branch_id,
                spec_id=spec.spec_id,
                plan_id=plan.plan_id,
                status="running",
                created_at=datetime.now(timezone.utc),
            )

            # Create and run experiment loop
            loop = ExperimentLoop(
                llm=self.llm_client,
                sandbox=sandbox,
                store=store,
                max_turns_per_iteration=20,
            )

            # Execute the loop
            final_run = loop.run(experiment_run, spec, plan)

            # Calculate metrics
            elapsed_time = time.time() - start_time
            total_cost = sum(
                iter.cost_usage.total_usd
                for iter in final_run.iterations
                if iter.cost_usage
            )

            # Determine status
            status = "success" if final_run.status == "completed" else "failed"

            # Generate report
            if status == "failed":
                report_path = config.workspace_path.parent / "failure_report.md"
                # TODO: Generate failure report from final_run
            else:
                report_path = config.workspace_path.parent / "success_report.md"
                # TODO: Generate success report from final_run

            return BranchResult(
                branch_id=config.branch_id,
                status=status,
                iterations=len(final_run.iterations),
                cost_usd=total_cost,
                time_seconds=elapsed_time,
                report_path=str(report_path),
            )

        except Exception as e:
            logger.error(f"Branch {config.branch_id} failed: {e}", exc_info=True)
            elapsed_time = time.time() - start_time

            # Generate failure report
            report_path = config.workspace_path.parent / "failure_report.md"
            report_path.write_text(f"# Branch Execution Failed\n\nError: {e}\n")

            return BranchResult(
                branch_id=config.branch_id,
                status="failed",
                iterations=0,
                cost_usd=0.0,
                time_seconds=elapsed_time,
                report_path=str(report_path),
            )


def _execute_branch_worker(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Worker function for multiprocessing.

    Args:
        config_dict: Branch configuration as dictionary

    Returns:
        Branch result as dictionary

    Note:
        This function is used by multiprocessing.Pool.
        It must be a top-level function (not a method).
    """
    # Reconstruct BranchConfig from dict
    from src.schemas.orchestrator import BranchConfig

    config = BranchConfig(**config_dict)

    # Execute branch
    executor = BranchExecutor(max_workers=1)
    result = executor._execute_single_branch(config)

    # Return result as dict
    return result.model_dump()
