"""Unit tests for DockerSandbox (mocked Docker client)."""

from unittest.mock import MagicMock, patch

import pytest

from src.sandbox.docker_config import DockerConfig
from src.sandbox.docker_sandbox import DockerSandbox
from src.schemas.sandbox_io import CodeSnapshot, SandboxRequest, SandboxStatus


def _make_request(run_id: str = "run_001", iteration: int = 1) -> SandboxRequest:
    return SandboxRequest(
        request_id=f"req_{run_id}_{iteration}",
        run_id=run_id,
        iteration_index=iteration,
        code_snapshot=CodeSnapshot(
            files={"main.py": "print('hello')"},
            entrypoint="python main.py",
        ),
        timeout_sec=30,
    )


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    client = MagicMock()
    container = MagicMock()
    container.id = "abc123def456"
    container.exec_run.return_value = (0, (b"hello\n", b""))
    client.containers.run.return_value = container
    return client, container


@pytest.fixture
def sandbox(tmp_path):
    """Create DockerSandbox with test config."""
    config = DockerConfig(timeout_sec=30)
    return DockerSandbox(config=config, runs_dir=tmp_path)


def test_sandbox_initialization(sandbox):
    """Test DockerSandbox initialization."""
    assert sandbox.config is not None
    assert sandbox.runs_dir is not None
    assert sandbox._client is None  # lazy init


def test_sandbox_default_config(tmp_path):
    """Test DockerSandbox with default config."""
    sandbox = DockerSandbox(runs_dir=tmp_path)
    assert sandbox.config.image == "python:3.11-slim"
    assert sandbox.config.network_mode == "none"


def test_execute_success(sandbox, mock_docker_client, tmp_path):
    """Test successful execution."""
    client, container = mock_docker_client
    container.exec_run.return_value = (0, (b"hello\n", b""))

    with patch.object(sandbox, "_get_client", return_value=client):
        request = _make_request()
        response = sandbox.execute(request)

    assert response.status == SandboxStatus.succeeded
    assert response.exit_code == 0
    assert "hello" in response.stdout


def test_execute_failure(sandbox, mock_docker_client):
    """Test failed execution."""
    client, container = mock_docker_client
    container.exec_run.return_value = (1, (b"", b"Error occurred"))

    with patch.object(sandbox, "_get_client", return_value=client):
        request = _make_request()
        response = sandbox.execute(request)

    assert response.status == SandboxStatus.failed
    assert response.exit_code == 1


def test_execute_creates_workspace(sandbox, mock_docker_client, tmp_path):
    """Test that workspace is created during execution."""
    client, container = mock_docker_client
    container.exec_run.return_value = (0, (b"", b""))

    with patch.object(sandbox, "_get_client", return_value=client):
        request = _make_request(run_id="run_test", iteration=1)
        sandbox.execute(request)

    workspace = tmp_path / "run_test" / "iterations" / "it_0001" / "workspace"
    assert workspace.exists()


def test_execute_writes_code_files(sandbox, mock_docker_client, tmp_path):
    """Test that code files are written to workspace."""
    client, container = mock_docker_client
    container.exec_run.return_value = (0, (b"", b""))

    with patch.object(sandbox, "_get_client", return_value=client):
        request = SandboxRequest(
            request_id="req_test_1",
            run_id="run_test",
            iteration_index=1,
            code_snapshot=CodeSnapshot(
                files={"main.py": "print('test')", "utils.py": "def helper(): pass"},
                entrypoint="python main.py",
            ),
            timeout_sec=30,
        )
        sandbox.execute(request)

    workspace = tmp_path / "run_test" / "iterations" / "it_0001" / "workspace"
    assert (workspace / "main.py").exists()
    assert (workspace / "utils.py").exists()


def test_execute_docker_error_returns_failed(sandbox, mock_docker_client):
    """Test that Docker errors return failed response."""
    client, container = mock_docker_client
    client.containers.run.side_effect = Exception("Docker not available")

    with patch.object(sandbox, "_get_client", return_value=client):
        request = _make_request()
        response = sandbox.execute(request)

    assert response.status == SandboxStatus.failed
    assert response.exit_code == -1
    assert "Docker not available" in response.stderr


def test_execute_container_is_cleaned_up(sandbox, mock_docker_client):
    """Test that container is removed after execution."""
    client, container = mock_docker_client
    container.exec_run.return_value = (0, (b"", b""))

    with patch.object(sandbox, "_get_client", return_value=client):
        request = _make_request()
        sandbox.execute(request)

    # Container should be stopped and removed
    container.stop.assert_called()
    container.remove.assert_called()


def test_cleanup_closes_client(sandbox, mock_docker_client):
    """Test that cleanup closes the Docker client."""
    client, _ = mock_docker_client
    sandbox._client = client

    sandbox.cleanup()

    client.close.assert_called_once()
    assert sandbox._client is None


def test_cleanup_no_client(sandbox):
    """Test cleanup when no client initialized."""
    # Should not raise
    sandbox.cleanup()
    assert sandbox._client is None


def test_lazy_client_initialization(sandbox):
    """Test that client is lazily initialized."""
    assert sandbox._client is None

    with patch("docker.from_env") as mock_from_env:
        mock_from_env.return_value = MagicMock()
        client = sandbox._get_client()

    assert client is not None
    assert sandbox._client is not None
    mock_from_env.assert_called_once()


def test_get_client_reuses_existing(sandbox):
    """Test that _get_client reuses existing client."""
    mock_client = MagicMock()
    sandbox._client = mock_client

    with patch("docker.from_env") as mock_from_env:
        client = sandbox._get_client()

    assert client is mock_client
    mock_from_env.assert_not_called()
