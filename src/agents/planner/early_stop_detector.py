"""Early stopping detector for PEC loop."""


class EarlyStopDetector:
    """Detect when to stop PEC loop early.

    Stops when:
    - Consecutive no-improvement threshold reached (default: 2)
    - Maximum iterations reached
    """

    def __init__(self, no_improvement_threshold: int = 2) -> None:
        """Initialize early stop detector.

        Args:
            no_improvement_threshold: Number of consecutive no-improvement
                iterations before stopping
        """
        self.no_improvement_threshold = no_improvement_threshold
        self.consecutive_no_improvement = 0
        self.best_score = 0.0

    def should_stop(self, current_score: float, max_iterations: int, current_iteration: int) -> tuple[bool, str]:
        """Check if should stop early.

        Args:
            current_score: Score from current iteration
            max_iterations: Maximum allowed iterations
            current_iteration: Current iteration number

        Returns:
            Tuple of (should_stop, reason)
        """
        # Check max iterations
        if current_iteration >= max_iterations:
            return True, f"Reached maximum iterations ({max_iterations})"

        # Check for improvement
        if current_score > self.best_score:
            self.best_score = current_score
            self.consecutive_no_improvement = 0
            return False, ""
        else:
            self.consecutive_no_improvement += 1

        # Check consecutive no-improvement
        if self.consecutive_no_improvement >= self.no_improvement_threshold:
            return (
                True,
                f"No improvement for {self.consecutive_no_improvement} consecutive iterations",
            )

        return False, ""

    def reset(self) -> None:
        """Reset detector state."""
        self.consecutive_no_improvement = 0
        self.best_score = 0.0
