"""Budget scheduler for managing branch resources."""

from src.scheduler.allocation_strategy import (
    AllocationStrategy,
    PerformanceBasedAllocationStrategy,
)
from src.scheduler.early_stop_strategy import (
    CompositeEarlyStopStrategy,
    EarlyStopStrategy,
)
from src.scheduler.resource_tracker import ResourceTracker, ResourceUsage


class BudgetScheduler:
    """Manage budget allocation and resource tracking for branches.

    Responsibilities:
    - Track resource consumption per branch
    - Dynamically allocate budget based on performance
    - Detect early stop conditions
    """

    def __init__(
        self,
        total_budget: dict[str, float],
        allocation_strategy: AllocationStrategy | None = None,
        early_stop_strategy: EarlyStopStrategy | None = None,
    ) -> None:
        """Initialize budget scheduler.

        Args:
            total_budget: Total available budget
                {"max_cost_usd": float, "max_time_hours": float, "max_iterations": int}
            allocation_strategy: Strategy for allocating budget (default: performance-based)
            early_stop_strategy: Strategy for early stopping (default: composite)
        """
        self.total_budget = total_budget
        self.resource_tracker = ResourceTracker()
        self.allocation_strategy = allocation_strategy or PerformanceBasedAllocationStrategy()
        self.early_stop_strategy = early_stop_strategy or CompositeEarlyStopStrategy()
        self.branch_scores: dict[str, float] = {}
        self.failure_counts: dict[str, int] = {}

    def record_usage(
        self,
        branch_id: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
        time_seconds: float = 0.0,
        iterations: int = 0,
    ) -> None:
        """Record resource usage for a branch.

        Args:
            branch_id: Branch identifier
            tokens: Tokens used
            cost_usd: Cost in USD
            time_seconds: Time in seconds
            iterations: Number of iterations
        """
        self.resource_tracker.record_usage(
            branch_id, tokens, cost_usd, time_seconds, iterations
        )

    def update_score(self, branch_id: str, score: float) -> None:
        """Update performance score for a branch.

        Args:
            branch_id: Branch identifier
            score: Performance score (higher is better)
        """
        self.branch_scores[branch_id] = score

    def record_failure(self, branch_id: str) -> None:
        """Record a failure for a branch.

        Args:
            branch_id: Branch identifier
        """
        self.failure_counts[branch_id] = self.failure_counts.get(branch_id, 0) + 1

    def record_success(self, branch_id: str) -> None:
        """Record a success for a branch (resets failure count).

        Args:
            branch_id: Branch identifier
        """
        self.failure_counts[branch_id] = 0

    def allocate_budget(self) -> dict[str, dict[str, float]]:
        """Allocate budget across branches based on current performance.

        Returns:
            Budget allocation for each branch
        """
        branch_usage = {
            branch_id: self.resource_tracker.get_usage(branch_id)
            for branch_id in self.branch_scores
        }

        return self.allocation_strategy.allocate(
            self.total_budget, self.branch_scores, branch_usage
        )

    def should_stop_branch(self, branch_id: str) -> tuple[bool, str]:
        """Check if a branch should stop early.

        Args:
            branch_id: Branch identifier

        Returns:
            Tuple of (should_stop, reason)
        """
        usage = self.resource_tracker.get_usage(branch_id)
        allocated_budget = self.allocate_budget().get(branch_id, self.total_budget)
        failure_count = self.failure_counts.get(branch_id, 0)

        return self.early_stop_strategy.should_stop(
            branch_id, usage, allocated_budget, failure_count
        )

    def get_usage(self, branch_id: str) -> ResourceUsage:
        """Get resource usage for a branch.

        Args:
            branch_id: Branch identifier

        Returns:
            Resource usage
        """
        return self.resource_tracker.get_usage(branch_id)

    def get_total_usage(self) -> ResourceUsage:
        """Get total resource usage across all branches.

        Returns:
            Total resource usage
        """
        return self.resource_tracker.get_total_usage()

    def get_remaining_budget(self) -> dict[str, float]:
        """Get remaining budget.

        Returns:
            Remaining budget
        """
        total_usage = self.get_total_usage()
        return {
            "max_cost_usd": self.total_budget["max_cost_usd"] - total_usage.cost_usd,
            "max_time_hours": self.total_budget["max_time_hours"]
            - (total_usage.time_seconds / 3600),
            "max_iterations": self.total_budget["max_iterations"]
            - total_usage.iterations,
        }
