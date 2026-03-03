"""Branch orchestrator for multi-branch parallel execution."""

import logging
import time
from pathlib import Path
from typing import Any

from src.llm.client import LLMClient
from src.orchestrator.branch_executor import BranchExecutor
from src.orchestrator.config import OrchestratorConfig
from src.orchestrator.variant_generator import BranchVariantGenerator
from src.orchestrator.workspace_manager import WorkspaceManager
from src.scheduler.budget_scheduler import BudgetScheduler
from src.schemas.experiment_result import ExperimentResult
from src.schemas.orchestrator import BranchConfig, BranchResult, BudgetAllocation
from src.schemas.research_spec import ExperimentPlan, ResearchSpec

logger = logging.getLogger(__name__)


class BranchOrchestrator:
    """Orchestrate multi-branch parallel experiment execution.

    Manages up to 3 parallel branches, each exploring different variants
    of the experiment plan. Coordinates global knowledge base (read-only)
    and branch-local memory (read-write).
    """

    def __init__(self, config: OrchestratorConfig, llm_client: LLMClient) -> None:
        """Initialize orchestrator.

        Args:
            config: Orchestrator configuration
            llm_client: LLM client for branch execution
        """
        self.config = config
        self.variant_generator = BranchVariantGenerator()
        self.workspace_manager = WorkspaceManager()

        # Initialize budget scheduler
        total_budget = {
            "max_cost_usd": config.budget.max_cost_usd,
            "max_time_hours": config.budget.get_max_time_seconds() / 3600,  # Convert to hours
            "max_iterations": config.orchestrator.max_iterations,
        }
        self.budget_scheduler = BudgetScheduler(total_budget)

        # Initialize branch executor
        self.executor = BranchExecutor(
            max_workers=config.orchestrator.num_branches,
            llm_client=llm_client,
            max_iterations=config.orchestrator.max_iterations,
            enable_docker=config.docker.enabled,
            docker_config=config.docker,
        )

    def run(
        self,
        spec: ResearchSpec,
        plan: ExperimentPlan,
        run_id: str,
        runs_dir: Path,
    ) -> ExperimentResult:
        """Execute multi-branch experiment.

        Args:
            spec: Research specification
            plan: Experiment plan
            run_id: Run identifier
            runs_dir: Base directory for runs

        Returns:
            Unified experiment result

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration
        num_branches = self.config.orchestrator.num_branches
        if num_branches < 1 or num_branches > 3:
            raise ValueError(f"num_branches must be 1-3, got {num_branches}")

        # Generate branch variants
        variants = self.variant_generator.generate_variants(plan, num_branches)

        # Create branch configurations
        branch_configs = self._create_branch_configs(
            run_id=run_id,
            runs_dir=runs_dir,
            variants=variants,
        )

        # Execute branches sequentially (parallel execution in future)
        logger.info(f"Executing {len(branch_configs)} branches sequentially")
        start_time = time.time()

        branch_results = self.executor.execute_branches(
            branch_configs=branch_configs,
            spec=spec,
            plan=plan,
        )

        # Aggregate results
        total_cost = sum(r.cost_usd for r in branch_results)
        total_time = time.time() - start_time
        total_iterations = sum(r.iterations for r in branch_results)

        # Determine overall status
        failed_count = sum(1 for r in branch_results if r.status == "failed")
        if failed_count == len(branch_results):
            status = "failed"  # All branches failed
        else:
            status = "success"  # At least one branch succeeded

        # Select best branch (highest iterations, or first successful)
        best_branch = max(
            (r for r in branch_results if r.status == "success"),
            key=lambda r: r.iterations,
            default=branch_results[0] if branch_results else None,
        )

        from datetime import datetime

        return ExperimentResult(
            run_id=run_id,
            engine="aisci",
            status=status,
            total_cost_usd=total_cost,
            total_time_seconds=total_time,
            iterations=total_iterations,
            created_at=datetime.now(),
            engine_version="1.0.0",
            best_code_path=best_branch.report_path if best_branch else None,
        )

    def _create_branch_configs(
        self,
        run_id: str,
        runs_dir: Path,
        variants: list[dict[str, Any]],
    ) -> list[BranchConfig]:
        """Create branch configurations.

        Args:
            run_id: Run identifier
            runs_dir: Base directory for runs
            variants: List of variant parameters

        Returns:
            List of branch configurations
        """
        configs = []

        for i, variant in enumerate(variants, 1):
            branch_id = f"branch_{i:03d}"

            # Create workspace
            workspace_path = self.workspace_manager.create_workspace(
                runs_dir=runs_dir,
                run_id=run_id,
                branch_id=branch_id,
            )

            # Calculate initial budget (divide total budget by num branches)
            total_budget = self.config.budget
            initial_budget = BudgetAllocation(
                max_cost_usd=total_budget.max_cost_usd / len(variants),
                max_time_hours=total_budget.max_time_hours / len(variants),
                max_iterations=self.config.orchestrator.max_iterations,
            )

            # Create config
            config = BranchConfig(
                branch_id=branch_id,
                variant_params=variant,
                initial_budget=initial_budget,
                workspace_path=workspace_path,
            )
            configs.append(config)

        return configs
