"""Priority manager for dynamic branch prioritization."""

from typing import Any


class PriorityManager:
    """Manage branch priorities based on intermediate results.

    Adjusts branch priorities dynamically to allocate more resources
    to promising branches and less to underperforming ones.
    """

    def __init__(self) -> None:
        """Initialize priority manager."""
        self.branch_priorities: dict[str, float] = {}

    def initialize_priorities(self, branch_ids: list[str]) -> None:
        """Initialize all branches with equal priority.

        Args:
            branch_ids: List of branch identifiers
        """
        for branch_id in branch_ids:
            self.branch_priorities[branch_id] = 1.0

    def update_priority(
        self,
        branch_id: str,
        intermediate_result: dict[str, Any],
    ) -> None:
        """Update branch priority based on intermediate result.

        Args:
            branch_id: Branch identifier
            intermediate_result: Intermediate result containing metrics

        Note:
            Priority is adjusted based on:
            - Success rate (higher is better)
            - Improvement trend (positive trend increases priority)
            - Cost efficiency (lower cost per success increases priority)
        """
        if branch_id not in self.branch_priorities:
            self.branch_priorities[branch_id] = 1.0

        # Extract metrics
        success_rate = intermediate_result.get("success_rate", 0.0)
        improvement_trend = intermediate_result.get("improvement_trend", 0.0)
        cost_efficiency = intermediate_result.get("cost_efficiency", 1.0)

        # Calculate new priority (weighted average)
        new_priority = (
            0.4 * success_rate + 0.3 * improvement_trend + 0.3 * cost_efficiency
        )

        # Clamp priority to [0.1, 2.0]
        new_priority = max(0.1, min(2.0, new_priority))

        self.branch_priorities[branch_id] = new_priority

    def get_priority(self, branch_id: str) -> float:
        """Get current priority for a branch.

        Args:
            branch_id: Branch identifier

        Returns:
            Priority value (0.1 to 2.0, default 1.0)
        """
        return self.branch_priorities.get(branch_id, 1.0)

    def get_sorted_branches(self) -> list[tuple[str, float]]:
        """Get branches sorted by priority (highest first).

        Returns:
            List of (branch_id, priority) tuples sorted by priority
        """
        return sorted(
            self.branch_priorities.items(), key=lambda x: x[1], reverse=True
        )

    def should_terminate_branch(
        self,
        branch_id: str,
        min_priority_threshold: float = 0.2,
    ) -> bool:
        """Check if branch should be terminated due to low priority.

        Args:
            branch_id: Branch identifier
            min_priority_threshold: Minimum priority to continue

        Returns:
            True if branch should be terminated, False otherwise
        """
        priority = self.get_priority(branch_id)
        return priority < min_priority_threshold
