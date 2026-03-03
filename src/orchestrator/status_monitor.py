"""Status monitor for real-time branch execution display."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict


class BranchStatus(str, Enum):
    """Branch execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class BranchState:
    """State of a single branch execution.

    Attributes:
        branch_id: Branch identifier
        status: Current status
        iteration: Current iteration number
        score: Latest critic score (0-100)
        started_at: Start timestamp
        updated_at: Last update timestamp
    """

    branch_id: str
    status: BranchStatus
    iteration: int = 0
    score: float = 0.0
    started_at: datetime | None = None
    updated_at: datetime | None = None


class StatusMonitor:
    """Monitor and display real-time branch execution status.

    Tracks multiple branches and provides formatted status output.
    """

    def __init__(self) -> None:
        """Initialize status monitor."""
        self._branches: Dict[str, BranchState] = {}

    def start_branch(self, branch_id: str) -> None:
        """Mark a branch as started.

        Args:
            branch_id: Branch identifier
        """
        now = datetime.now()
        self._branches[branch_id] = BranchState(
            branch_id=branch_id,
            status=BranchStatus.RUNNING,
            started_at=now,
            updated_at=now,
        )

    def update_iteration(self, branch_id: str, iteration: int, score: float) -> None:
        """Update branch iteration progress.

        Args:
            branch_id: Branch identifier
            iteration: Current iteration number
            score: Critic score (0-100)
        """
        if branch_id in self._branches:
            state = self._branches[branch_id]
            state.iteration = iteration
            state.score = score
            state.updated_at = datetime.now()

    def complete_branch(self, branch_id: str, success: bool) -> None:
        """Mark a branch as completed.

        Args:
            branch_id: Branch identifier
            success: Whether branch succeeded
        """
        if branch_id in self._branches:
            state = self._branches[branch_id]
            state.status = BranchStatus.SUCCESS if success else BranchStatus.FAILED
            state.updated_at = datetime.now()

    def get_status(self, branch_id: str) -> BranchState | None:
        """Get status of a specific branch.

        Args:
            branch_id: Branch identifier

        Returns:
            Branch state or None if not found
        """
        return self._branches.get(branch_id)

    def get_all_statuses(self) -> Dict[str, BranchState]:
        """Get status of all branches.

        Returns:
            Dictionary mapping branch_id to BranchState
        """
        return self._branches.copy()

    def format_status_line(self, branch_id: str) -> str:
        """Format a single branch status line.

        Args:
            branch_id: Branch identifier

        Returns:
            Formatted status string
        """
        state = self._branches.get(branch_id)
        if not state:
            return f"{branch_id}: unknown"

        status_icon = {
            BranchStatus.PENDING: "⏳",
            BranchStatus.RUNNING: "🔄",
            BranchStatus.SUCCESS: "✅",
            BranchStatus.FAILED: "❌",
        }.get(state.status, "❓")

        if state.status == BranchStatus.RUNNING:
            return (
                f"{status_icon} {branch_id}: "
                f"iteration {state.iteration}, score {state.score:.1f}"
            )
        else:
            return f"{status_icon} {branch_id}: {state.status.value}"

    def format_summary(self) -> str:
        """Format a summary of all branches.

        Returns:
            Multi-line formatted summary
        """
        if not self._branches:
            return "No branches tracked"

        lines = ["Branch Status Summary:", "=" * 50]
        for branch_id in sorted(self._branches.keys()):
            lines.append(self.format_status_line(branch_id))

        # Add counts
        statuses = [s.status for s in self._branches.values()]
        running = sum(1 for s in statuses if s == BranchStatus.RUNNING)
        success = sum(1 for s in statuses if s == BranchStatus.SUCCESS)
        failed = sum(1 for s in statuses if s == BranchStatus.FAILED)

        lines.append("=" * 50)
        lines.append(f"Running: {running}, Success: {success}, Failed: {failed}")

        return "\n".join(lines)
