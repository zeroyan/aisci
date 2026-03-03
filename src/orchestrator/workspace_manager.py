"""Workspace manager for branch isolation."""

import shutil
from pathlib import Path


class WorkspaceManager:
    """Manage branch workspaces for isolation.

    Each branch gets an independent workspace:
    runs/<run_id>/branches/<branch_id>/workspace/
    """

    def create_workspace(
        self,
        runs_dir: Path,
        run_id: str,
        branch_id: str,
    ) -> Path:
        """Create workspace for a branch.

        Args:
            runs_dir: Base directory for runs
            run_id: Run identifier
            branch_id: Branch identifier

        Returns:
            Path to created workspace

        Raises:
            OSError: If workspace creation fails
        """
        workspace_path = runs_dir / run_id / "branches" / branch_id / "workspace"
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (workspace_path / "code").mkdir(exist_ok=True)
        (workspace_path / "data").mkdir(exist_ok=True)
        (workspace_path / "results").mkdir(exist_ok=True)

        return workspace_path

    def create_memory_dir(
        self,
        runs_dir: Path,
        run_id: str,
        branch_id: str,
    ) -> Path:
        """Create memory directory for a branch.

        Args:
            runs_dir: Base directory for runs
            run_id: Run identifier
            branch_id: Branch identifier

        Returns:
            Path to created memory directory
        """
        memory_path = runs_dir / run_id / "branches" / branch_id / "memory"
        memory_path.mkdir(parents=True, exist_ok=True)
        return memory_path

    def create_logs_dir(
        self,
        runs_dir: Path,
        run_id: str,
        branch_id: str,
    ) -> Path:
        """Create logs directory for a branch.

        Args:
            runs_dir: Base directory for runs
            run_id: Run identifier
            branch_id: Branch identifier

        Returns:
            Path to created logs directory
        """
        logs_path = runs_dir / run_id / "branches" / branch_id / "logs"
        logs_path.mkdir(parents=True, exist_ok=True)
        return logs_path

    def cleanup_workspace(
        self,
        runs_dir: Path,
        run_id: str,
        branch_id: str,
    ) -> None:
        """Clean up workspace for a branch.

        Args:
            runs_dir: Base directory for runs
            run_id: Run identifier
            branch_id: Branch identifier

        Note:
            This removes the entire branch directory including
            workspace, memory, and logs. Use with caution.
        """
        branch_path = runs_dir / run_id / "branches" / branch_id
        if branch_path.exists():
            shutil.rmtree(branch_path)
