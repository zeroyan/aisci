"""Early stopping strategies for branches."""

from src.scheduler.resource_tracker import ResourceUsage


class EarlyStopStrategy:
    """Strategy for determining when to stop a branch early."""

    def should_stop(
        self,
        branch_id: str,
        usage: ResourceUsage,
        budget: dict[str, float],
        failure_count: int,
    ) -> tuple[bool, str]:
        """Check if branch should stop early.

        Args:
            branch_id: Branch identifier
            usage: Current resource usage
            budget: Allocated budget
            failure_count: Number of consecutive failures

        Returns:
            Tuple of (should_stop, reason)
        """
        raise NotImplementedError


class CompositeEarlyStopStrategy(EarlyStopStrategy):
    """Composite strategy that checks multiple conditions."""

    def __init__(self, max_consecutive_failures: int = 2) -> None:
        """Initialize strategy.

        Args:
            max_consecutive_failures: Maximum consecutive failures before stopping
        """
        self.max_consecutive_failures = max_consecutive_failures

    def should_stop(
        self,
        branch_id: str,
        usage: ResourceUsage,
        budget: dict[str, float],
        failure_count: int,
    ) -> tuple[bool, str]:
        """Check multiple early stop conditions.

        Stops if:
        - Consecutive failures exceed threshold
        - Budget exceeded
        - Timeout

        Args:
            branch_id: Branch identifier
            usage: Current resource usage
            budget: Allocated budget
            failure_count: Consecutive failure count

        Returns:
            Tuple of (should_stop, reason)
        """
        # Check consecutive failures
        if failure_count >= self.max_consecutive_failures:
            return (
                True,
                f"Branch {branch_id}: {failure_count} consecutive failures",
            )

        # Check budget exceeded
        exceeds, reason = usage.exceeds_budget(
            budget["max_cost_usd"],
            budget["max_time_hours"],
            budget["max_iterations"],
        )
        if exceeds:
            return True, f"Branch {branch_id}: {reason}"

        return False, ""

    def reset_failure_count(self) -> None:
        """Reset failure count (called on success)."""
        # This is handled externally by the scheduler
        pass
