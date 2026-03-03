"""Unit tests for DockerCleanup."""

from unittest.mock import MagicMock

import pytest

from src.sandbox.docker_cleanup import DockerCleanup


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def cleanup(mock_client):
    return DockerCleanup(mock_client)


def _make_container(container_id: str = "abc123def456"):
    container = MagicMock()
    container.id = container_id
    return container


def test_cleanup_initialization(cleanup, mock_client):
    """Test cleanup initialization."""
    assert cleanup.client is mock_client
    assert cleanup._tracked == []


def test_track_container(cleanup):
    """Test tracking a container."""
    container = _make_container()
    cleanup.track(container)

    assert container in cleanup._tracked


def test_track_multiple_containers(cleanup):
    """Test tracking multiple containers."""
    containers = [_make_container(f"id_{i}") for i in range(3)]
    for c in containers:
        cleanup.track(c)

    assert len(cleanup._tracked) == 3


def test_remove_container_success(cleanup):
    """Test successful container removal."""
    container = _make_container()
    result = cleanup.remove_container(container)

    assert result is True
    container.stop.assert_called_once_with(timeout=5)
    container.remove.assert_called_once_with(force=True)


def test_remove_container_stop_fails(cleanup):
    """Test removal when stop raises exception."""
    container = _make_container()
    container.stop.side_effect = Exception("already stopped")

    result = cleanup.remove_container(container)

    # Should still try to remove
    assert result is True
    container.remove.assert_called_once_with(force=True)


def test_remove_container_remove_fails(cleanup):
    """Test removal when remove raises exception."""
    container = _make_container()
    container.remove.side_effect = Exception("not found")

    result = cleanup.remove_container(container)

    assert result is False


def test_cleanup_all_removes_all(cleanup):
    """Test cleanup_all removes all tracked containers."""
    containers = [_make_container(f"id_{i}") for i in range(3)]
    for c in containers:
        cleanup.track(c)

    stats = cleanup.cleanup_all()

    assert stats["removed"] == 3
    assert stats["failed"] == 0
    assert cleanup._tracked == []


def test_cleanup_all_empty(cleanup):
    """Test cleanup_all with no tracked containers."""
    stats = cleanup.cleanup_all()

    assert stats["removed"] == 0
    assert stats["failed"] == 0


def test_cleanup_all_partial_failure(cleanup):
    """Test cleanup_all with some failures."""
    good = _make_container("good")
    bad = _make_container("bad")
    bad.remove.side_effect = Exception("failed")

    cleanup.track(good)
    cleanup.track(bad)

    stats = cleanup.cleanup_all()

    assert stats["removed"] == 1
    assert stats["failed"] == 1
    assert cleanup._tracked == []


def test_managed_container_cleanup_on_success(cleanup):
    """Test managed_container cleans up after successful block."""
    container = _make_container()

    with cleanup.managed_container(container) as c:
        assert c is container

    container.remove.assert_called_once_with(force=True)


def test_managed_container_cleanup_on_exception(cleanup):
    """Test managed_container cleans up even when exception raised."""
    container = _make_container()

    with pytest.raises(ValueError):
        with cleanup.managed_container(container):
            raise ValueError("test error")

    container.remove.assert_called_once_with(force=True)


def test_managed_container_yields_container(cleanup):
    """Test managed_container yields the container."""
    container = _make_container()
    yielded = None

    with cleanup.managed_container(container) as c:
        yielded = c

    assert yielded is container
