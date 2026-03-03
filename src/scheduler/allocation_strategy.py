"""Budget allocation strategies for branches."""

from src.scheduler.resource_tracker import ResourceUsage


class AllocationStrategy:
    """Strategy for allocating budget across branches."""

    def allocate(
        self,
        total_budget: dict[str, float],
        branch_scores: dict[str, float],
        branch_usage: dict[str, ResourceUsage],
    ) -> dict[str, dict[str, float]]:
        """Allocate budget across branches based on performance.

        Args:
            total_budget: Total available budget
                {"max_cost_usd": float, "max_time_hours": float, "max_iterations": int}
            branch_scores: Current scores for each branch
            branch_usage: Current resource usage for each branch

        Returns:
            Budget allocation for each branch
                {branch_id: {"max_cost_usd": float, "max_time_hours": float, "max_iterations": int}}
        """
        raise NotImplementedError


class EqualAllocationStrategy(AllocationStrategy):
    """Allocate budget equally across all branches."""

    def allocate(
        self,
        total_budget: dict[str, float],
        branch_scores: dict[str, float],
        branch_usage: dict[str, ResourceUsage],
    ) -> dict[str, dict[str, float]]:
        """Allocate budget equally.

        Args:
            total_budget: Total budget
            branch_scores: Branch scores (unused)
            branch_usage: Branch usage (unused)

        Returns:
            Equal budget allocation
        """
        num_branches = len(branch_scores)
        if num_branches == 0:
            return {}

        allocation = {}
        for branch_id in branch_scores:
            allocation[branch_id] = {
                "max_cost_usd": total_budget["max_cost_usd"] / num_branches,
                "max_time_hours": total_budget["max_time_hours"] / num_branches,
                "max_iterations": total_budget["max_iterations"] // num_branches,
            }

        return allocation


class PerformanceBasedAllocationStrategy(AllocationStrategy):
    """Allocate more budget to better-performing branches."""

    def __init__(self, min_allocation_ratio: float = 0.2) -> None:
        """Initialize strategy.

        Args:
            min_allocation_ratio: Minimum allocation ratio for any branch
        """
        self.min_allocation_ratio = min_allocation_ratio

    def allocate(
        self,
        total_budget: dict[str, float],
        branch_scores: dict[str, float],
        branch_usage: dict[str, ResourceUsage],
    ) -> dict[str, dict[str, float]]:
        """Allocate budget based on performance.

        Better-performing branches get more budget.
        Each branch gets at least min_allocation_ratio of equal share.

        Args:
            total_budget: Total budget
            branch_scores: Branch scores (higher is better)
            branch_usage: Branch usage

        Returns:
            Performance-based budget allocation
        """
        num_branches = len(branch_scores)
        if num_branches == 0:
            return {}

        # Calculate allocation weights based on scores
        total_score = sum(branch_scores.values())
        if total_score == 0:
            # No scores yet, use equal allocation
            return EqualAllocationStrategy().allocate(
                total_budget, branch_scores, branch_usage
            )

        # Calculate weights with minimum allocation
        weights = {}
        min_weight = self.min_allocation_ratio / num_branches
        remaining_weight = 1.0 - (min_weight * num_branches)

        for branch_id, score in branch_scores.items():
            score_weight = (score / total_score) * remaining_weight
            weights[branch_id] = min_weight + score_weight

        # Allocate budget based on weights
        allocation = {}
        for branch_id, weight in weights.items():
            allocation[branch_id] = {
                "max_cost_usd": total_budget["max_cost_usd"] * weight,
                "max_time_hours": total_budget["max_time_hours"] * weight,
                "max_iterations": int(total_budget["max_iterations"] * weight),
            }

        return allocation
