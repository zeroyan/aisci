"""Unit tests for WorkspaceManager."""


import pytest

from src.orchestrator.workspace_manager import WorkspaceManager


@pytest.fixture
def workspace_manager():
    """Create workspace manager instance."""
    return WorkspaceManager()


def test_create_workspace(workspace_manager, tmp_path):
    """Test workspace creation."""
    workspace_path = workspace_manager.create_workspace(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_001",
    )

    # Verify workspace structure
    assert workspace_path.exists()
    assert workspace_path.is_dir()
    assert (workspace_path / "code").exists()
    assert (workspace_path / "data").exists()
    assert (workspace_path / "results").exists()

    # Verify path structure
    expected_path = tmp_path / "test_run" / "branches" / "branch_001" / "workspace"
    assert workspace_path == expected_path


def test_create_memory_dir(workspace_manager, tmp_path):
    """Test memory directory creation."""
    memory_path = workspace_manager.create_memory_dir(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_001",
    )

    # Verify memory directory
    assert memory_path.exists()
    assert memory_path.is_dir()

    # Verify path structure
    expected_path = tmp_path / "test_run" / "branches" / "branch_001" / "memory"
    assert memory_path == expected_path


def test_create_logs_dir(workspace_manager, tmp_path):
    """Test logs directory creation."""
    logs_path = workspace_manager.create_logs_dir(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_001",
    )

    # Verify logs directory
    assert logs_path.exists()
    assert logs_path.is_dir()

    # Verify path structure
    expected_path = tmp_path / "test_run" / "branches" / "branch_001" / "logs"
    assert logs_path == expected_path


def test_workspace_isolation(workspace_manager, tmp_path):
    """Test that different branches have isolated workspaces."""
    # Create workspaces for two branches
    workspace_1 = workspace_manager.create_workspace(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_001",
    )
    workspace_2 = workspace_manager.create_workspace(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_002",
    )

    # Verify isolation
    assert workspace_1 != workspace_2
    assert workspace_1.exists()
    assert workspace_2.exists()

    # Create a file in workspace_1
    test_file_1 = workspace_1 / "code" / "test.py"
    test_file_1.write_text("# Branch 1 code")

    # Verify file doesn't exist in workspace_2
    test_file_2 = workspace_2 / "code" / "test.py"
    assert not test_file_2.exists()


def test_cleanup_workspace(workspace_manager, tmp_path):
    """Test workspace cleanup."""
    # Create workspace
    workspace_path = workspace_manager.create_workspace(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_001",
    )

    # Create some files
    test_file = workspace_path / "code" / "test.py"
    test_file.write_text("# Test code")

    # Verify workspace exists
    assert workspace_path.exists()
    assert test_file.exists()

    # Cleanup
    workspace_manager.cleanup_workspace(
        runs_dir=tmp_path,
        run_id="test_run",
        branch_id="branch_001",
    )

    # Verify workspace removed
    branch_path = tmp_path / "test_run" / "branches" / "branch_001"
    assert not branch_path.exists()
    assert not workspace_path.exists()
    assert not test_file.exists()
