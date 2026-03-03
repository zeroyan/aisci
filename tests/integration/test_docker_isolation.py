"""Integration tests for Docker isolation (mocked Docker client)."""

from unittest.mock import MagicMock, patch

import pytest

from src.sandbox.docker_cleanup import DockerCleanup
from src.sandbox.docker_config import DockerConfig
from src.sandbox.docker_sandbox import DockerSandbox
from src.sandbox.dependency_installer import DependencyInstaller
from src.schemas.sandbox_io import CodeSnapshot, SandboxRequest, SandboxStatus


def _make_container(exit_code: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    container = MagicMock()
    container.id = "test_container_id"
    container.exec_run.return_value = (exit_code, (stdout, stderr))
    return container


def _make_client(container):
    client = MagicMock()
    client.containers.run.return_value = container
    return client


def _make_request(files: dict | None = None, entrypoint: str = "python main.py") -> SandboxRequest:
    return SandboxRequest(
        request_id="integration_req_1",
        run_id="integration_run",
        iteration_index=1,
        code_snapshot=CodeSnapshot(
            files=files or {"main.py": "print('hello')"},
            entrypoint=entrypoint,
        ),
        timeout_sec=30,
    )


@pytest.fixture
def sandbox(tmp_path):
    config = DockerConfig(network_mode="none", memory_limit="256m", cpu_quota=50000)
    return DockerSandbox(config=config, runs_dir=tmp_path)


# --- Container isolation tests ---

def test_network_isolation_configured(sandbox):
    """Test that network isolation is configured."""
    assert sandbox.config.network_mode == "none"


def test_resource_limits_configured(sandbox):
    """Test that resource limits are configured."""
    assert sandbox.config.memory_limit == "256m"
    assert sandbox.config.cpu_quota == 50000


def test_container_created_with_correct_config(sandbox):
    """Test that container is created with correct configuration."""
    container = _make_container()
    client = _make_client(container)

    with patch.object(sandbox, "_get_client", return_value=client):
        sandbox.execute(_make_request())

    call_kwargs = client.containers.run.call_args[1]
    assert call_kwargs["network_mode"] == "none"
    assert call_kwargs["mem_limit"] == "256m"
    assert call_kwargs["cpu_quota"] == 50000


def test_container_removed_after_execution(sandbox):
    """Test that container is removed after execution (no leaks)."""
    container = _make_container()
    client = _make_client(container)

    with patch.object(sandbox, "_get_client", return_value=client):
        sandbox.execute(_make_request())

    container.stop.assert_called()
    container.remove.assert_called()


def test_container_removed_on_failure(sandbox):
    """Test that container is removed even when execution fails."""
    container = _make_container(exit_code=1, stderr=b"Error")
    client = _make_client(container)

    with patch.object(sandbox, "_get_client", return_value=client):
        sandbox.execute(_make_request())

    container.remove.assert_called()


def test_container_removed_on_exception(sandbox):
    """Test that container is removed when exception occurs during exec."""
    container = MagicMock()
    container.id = "test_id"
    container.exec_run.side_effect = Exception("exec failed")
    client = _make_client(container)

    with patch.object(sandbox, "_get_client", return_value=client):
        response = sandbox.execute(_make_request())

    assert response.status == SandboxStatus.failed
    container.remove.assert_called()


# --- Dependency installer tests ---

def test_dependency_installer_parses_requirements():
    """Test that DependencyInstaller parses requirements correctly."""
    installer = DependencyInstaller()
    req_txt = "numpy==1.24.0\npandas>=2.0\n# comment\n\nscikit-learn"

    packages = installer.parse_requirements(req_txt)

    assert "numpy==1.24.0" in packages
    assert "pandas>=2.0" in packages
    assert "scikit-learn" in packages
    assert "# comment" not in packages
    assert "" not in packages


def test_dependency_installer_skips_missing_file(tmp_path):
    """Test that installer skips when requirements.txt doesn't exist."""
    installer = DependencyInstaller()
    container = MagicMock()

    result = installer.install_from_file(container, tmp_path / "nonexistent.txt")

    assert result is True
    container.exec_run.assert_not_called()


def test_dependency_installer_installs_from_file(tmp_path):
    """Test that installer installs from requirements.txt."""
    installer = DependencyInstaller()
    container = MagicMock()
    container.exec_run.return_value = (0, b"")

    req_path = tmp_path / "requirements.txt"
    req_path.write_text("numpy\npandas\n")

    result = installer.install_from_file(container, req_path)

    assert result is True
    assert container.exec_run.call_count == 2  # write + pip install


# --- Full workflow test ---

def test_full_docker_workflow(sandbox):
    """Test complete Docker execution workflow."""
    container = _make_container(
        exit_code=0,
        stdout=b"Experiment result: 0.95\n",
        stderr=b"",
    )
    client = _make_client(container)

    with patch.object(sandbox, "_get_client", return_value=client):
        request = _make_request(
            files={
                "main.py": "print('Experiment result: 0.95')",
                "requirements.txt": "numpy\n",
            }
        )
        response = sandbox.execute(request)

    assert response.status == SandboxStatus.succeeded
    assert response.exit_code == 0
    assert "Experiment result: 0.95" in response.stdout
    assert response.resource_usage.wall_time_sec >= 0

    # Container cleaned up
    container.remove.assert_called()


def test_docker_cleanup_context_manager():
    """Test DockerCleanup context manager in isolation scenario."""
    client = MagicMock()
    cleanup = DockerCleanup(client)

    container1 = MagicMock()
    container1.id = "c1"
    container2 = MagicMock()
    container2.id = "c2"

    cleanup.track(container1)
    cleanup.track(container2)

    stats = cleanup.cleanup_all()

    assert stats["removed"] == 2
    assert stats["failed"] == 0
    container1.remove.assert_called_with(force=True)
    container2.remove.assert_called_with(force=True)
