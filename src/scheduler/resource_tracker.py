"""Resource consumption tracker for branches."""

from dataclasses import dataclass


@dataclass
class ResourceUsage:
    """Track resource usage for a branch."""

    tokens_used: int = 0
    cost_usd: float = 0.0
    time_seconds: float = 0.0
    iterations: int = 0

    def add(self, other: "ResourceUsage") -> None:
        """Add another resource usage to this one.

        Args:
            other: Resource usage to add
        """
        self.tokens_used += other.tokens_used
        self.cost_usd += other.cost_usd
        self.time_seconds += other.time_seconds
        self.iterations += other.iterations

    def exceeds_budget(
        self,
        max_cost_usd: float,
        max_time_hours: float,
        max_iterations: int,
    ) -> tuple[bool, str]:
        """Check if usage exceeds budget.

        Args:
            max_cost_usd: Maximum cost budget
            max_time_hours: Maximum time budget
            max_iterations: Maximum iterations budget

        Returns:
            Tuple of (exceeds, reason)
        """
        if self.cost_usd > max_cost_usd:
            return True, f"Cost ${self.cost_usd:.2f} exceeds budget ${max_cost_usd:.2f}"

        if self.time_seconds > max_time_hours * 3600:
            return True, f"Time {self.time_seconds/3600:.2f}h exceeds budget {max_time_hours}h"

        if self.iterations > max_iterations:
            return True, f"Iterations {self.iterations} exceeds budget {max_iterations}"

        return False, ""


class ResourceTracker:
    """Track resource consumption for multiple branches."""

    def __init__(self) -> None:
        """Initialize resource tracker."""
        self.branch_usage: dict[str, ResourceUsage] = {}

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
        if branch_id not in self.branch_usage:
            self.branch_usage[branch_id] = ResourceUsage()

        usage = ResourceUsage(tokens, cost_usd, time_seconds, iterations)
        self.branch_usage[branch_id].add(usage)

    def get_usage(self, branch_id: str) -> ResourceUsage:
        """Get resource usage for a branch.

        Args:
            branch_id: Branch identifier

        Returns:
            Resource usage for the branch
        """
        return self.branch_usage.get(branch_id, ResourceUsage())

    def get_total_usage(self) -> ResourceUsage:
        """Get total resource usage across all branches.

        Returns:
            Total resource usage
        """
        total = ResourceUsage()
        for usage in self.branch_usage.values():
            total.add(usage)
        return total

    def get_branch_ids(self) -> list[str]:
        """Get all tracked branch IDs.

        Returns:
            List of branch IDs
        """
        return list(self.branch_usage.keys())
