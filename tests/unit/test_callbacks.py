"""Unit tests for JobCallbacks."""

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.integrations.ai_scientist.callbacks import JobCallbacks
from src.schemas.ai_scientist import JobRecord, JobStatus


@pytest.fixture
def sample_job():
    """Create sample job record."""
    return JobRecord(
        job_id="test_job_001",
        run_id="test_run_001",
        pid=12345,
        status=JobStatus.RUNNING,
        log_path="/tmp/test.log",
        start_time=datetime.now(),
        template_name="test_template",
        num_ideas=2,
        model="deepseek-chat",
        writeup="md",
    )


@pytest.fixture
def mock_adapter():
    """Create mock adapter."""
    adapter = Mock()
    adapter._try_start_pending_job = Mock()
    return adapter


@pytest.fixture
def mock_job_store():
    """Create mock job store."""
    job_store = Mock()
    job_store.load = Mock()
    job_store.save = Mock()
    return job_store


def test_callbacks_initialization():
    """Test JobCallbacks initialization."""
    callbacks = JobCallbacks(
        poll_interval=30,
        timeout=3600,
    )

    assert callbacks.poll_interval == 30
    assert callbacks.timeout == 3600
    assert callbacks.on_complete is None
    assert callbacks.on_failed is None
    assert callbacks.auto_start_pending is True


def test_callbacks_with_handlers():
    """Test JobCallbacks with custom handlers."""
    on_complete = Mock()
    on_failed = Mock()

    callbacks = JobCallbacks(
        on_complete=on_complete,
        on_failed=on_failed,
        auto_start_pending=False,
    )

    assert callbacks.on_complete == on_complete
    assert callbacks.on_failed == on_failed
    assert callbacks.auto_start_pending is False


def test_check_process_running():
    """Test checking if process is running."""
    with patch("psutil.Process") as mock_process:
        mock_proc = Mock()
        mock_proc.is_running.return_value = True
        mock_process.return_value = mock_proc

        result = JobCallbacks.check_process_running(12345)
        assert result is True


def test_check_process_not_running():
    """Test checking non-existent process."""
    import psutil

    with patch("psutil.Process") as mock_process:
        mock_process.side_effect = psutil.NoSuchProcess(12345)

        result = JobCallbacks.check_process_running(12345)
        assert result is False


def test_poll_status_by_job_id(mock_adapter, mock_job_store, sample_job):
    """Test polling status by job ID."""
    # Setup mocks
    mock_job_store.load.return_value = sample_job
    mock_adapter.get_status.return_value = {
        "status": "completed",
        "progress": "2/2 ideas",
        "elapsed_time": "60s",
        "log_path": "/tmp/test.log",
        "error": None,
    }

    callbacks = JobCallbacks(
        adapter=mock_adapter,
        job_store=mock_job_store,
        poll_interval=1,
        timeout=10,
    )

    result = callbacks.poll_status(job_id="test_job_001", interval=1, timeout=10)

    assert result["status"] == "completed"
    mock_adapter.get_status.assert_called()


def test_poll_status_timeout(mock_adapter, mock_job_store, sample_job):
    """Test polling status with timeout."""
    # Setup mocks - always return running
    mock_job_store.load.return_value = sample_job
    mock_adapter.get_status.return_value = {
        "status": "running",
        "progress": "1/2 ideas",
        "elapsed_time": "30s",
        "log_path": "/tmp/test.log",
        "error": None,
    }

    callbacks = JobCallbacks(
        adapter=mock_adapter,
        job_store=mock_job_store,
        poll_interval=1,
        timeout=2,  # Short timeout
    )

    result = callbacks.poll_status(job_id="test_job_001", interval=1, timeout=2)

    assert result["status"] == "timeout"
    assert "error" in result


def test_poll_status_with_complete_callback(mock_adapter, mock_job_store, sample_job):
    """Test polling with completion callback."""
    on_complete = Mock()

    mock_job_store.load.return_value = sample_job
    mock_adapter.get_status.return_value = {
        "status": "completed",
        "progress": "2/2 ideas",
        "elapsed_time": "60s",
        "log_path": "/tmp/test.log",
        "error": None,
    }

    callbacks = JobCallbacks(
        adapter=mock_adapter,
        job_store=mock_job_store,
        on_complete=on_complete,
        poll_interval=1,
        timeout=10,
    )

    result = callbacks.poll_status(job_id="test_job_001", interval=1, timeout=10)

    assert result["status"] == "completed"
    on_complete.assert_called_once()


def test_poll_status_with_failed_callback(mock_adapter, mock_job_store, sample_job):
    """Test polling with failure callback."""
    on_failed = Mock()

    mock_job_store.load.return_value = sample_job
    mock_adapter.get_status.return_value = {
        "status": "failed",
        "progress": "1/2 ideas",
        "elapsed_time": "30s",
        "log_path": "/tmp/test.log",
        "error": "Process crashed",
    }

    callbacks = JobCallbacks(
        adapter=mock_adapter,
        job_store=mock_job_store,
        on_failed=on_failed,
        poll_interval=1,
        timeout=10,
    )

    result = callbacks.poll_status(job_id="test_job_001", interval=1, timeout=10)

    assert result["status"] == "failed"
    on_failed.assert_called_once()


def test_auto_start_pending_on_complete(mock_adapter, mock_job_store, sample_job):
    """Test auto-starting pending job on completion."""
    mock_job_store.load.return_value = sample_job
    mock_adapter.get_status.return_value = {
        "status": "completed",
        "progress": "2/2 ideas",
        "elapsed_time": "60s",
        "log_path": "/tmp/test.log",
        "error": None,
    }

    callbacks = JobCallbacks(
        adapter=mock_adapter,
        job_store=mock_job_store,
        auto_start_pending=True,
        poll_interval=1,
        timeout=10,
    )

    result = callbacks.poll_status(job_id="test_job_001", interval=1, timeout=10)

    assert result["status"] == "completed"
    # Should try to start next pending job
    mock_adapter._try_start_pending_job.assert_called_once_with(mock_job_store)


def test_no_auto_start_when_disabled(mock_adapter, mock_job_store, sample_job):
    """Test no auto-start when disabled."""
    mock_job_store.load.return_value = sample_job
    mock_adapter.get_status.return_value = {
        "status": "completed",
        "progress": "2/2 ideas",
        "elapsed_time": "60s",
        "log_path": "/tmp/test.log",
        "error": None,
    }

    callbacks = JobCallbacks(
        adapter=mock_adapter,
        job_store=mock_job_store,
        auto_start_pending=False,
        poll_interval=1,
        timeout=10,
    )

    result = callbacks.poll_status(job_id="test_job_001", interval=1, timeout=10)

    assert result["status"] == "completed"
    # Should NOT try to start next pending job
    mock_adapter._try_start_pending_job.assert_not_called()


def test_poll_status_legacy_interface(sample_job, tmp_path):
    """Test legacy polling interface with job + check_process."""
    # Create result directory
    result_dir = tmp_path / "results"
    result_dir.mkdir()
    (result_dir / "result.txt").write_text("test")

    # Mock check_process to return False (process ended)
    def check_process(pid):
        return False

    # Update job log path to use tmp_path
    job = sample_job.model_copy(update={"log_path": str(tmp_path / "test.log")})

    callbacks = JobCallbacks(poll_interval=1, timeout=10)

    # Mock _check_success to return True
    with patch.object(callbacks, "_check_success", return_value=True):
        status = callbacks.poll_status(
            job=job,
            check_process=check_process,
            interval=1,
            timeout=10,
        )

    assert status == JobStatus.COMPLETED


def test_poll_status_legacy_failed(sample_job, tmp_path):
    """Test legacy polling with failed job."""
    # No result directory

    def check_process(pid):
        return False

    job = sample_job.model_copy(update={"log_path": str(tmp_path / "test.log")})

    callbacks = JobCallbacks(poll_interval=1, timeout=10)

    # Mock _check_success to return False
    with patch.object(callbacks, "_check_success", return_value=False):
        status = callbacks.poll_status(
            job=job,
            check_process=check_process,
            interval=1,
            timeout=10,
        )

    assert status == JobStatus.FAILED


def test_check_success(sample_job, tmp_path):
    """Test checking job success."""
    callbacks = JobCallbacks()

    # Create result directory
    result_dir = tmp_path / "results"
    result_dir.mkdir()
    (result_dir / "result.txt").write_text("test")

    # Update job log path
    job = sample_job.model_copy(
        update={"log_path": str(tmp_path / "logs" / "test.log")}
    )

    # Create log directory
    (tmp_path / "logs").mkdir()

    # Mock result directory check
    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "iterdir", return_value=[Path("result.txt")]):
            result = callbacks._check_success(job)
            # Result depends on actual directory structure


def test_watch_job_fallback_to_polling(sample_job):
    """Test watch_job falls back to polling when watchdog unavailable."""
    callbacks = JobCallbacks(poll_interval=1, timeout=5)

    # Mock poll_status
    with patch.object(callbacks, "poll_status") as mock_poll:
        # Mock watchdog import to fail
        with patch("builtins.__import__", side_effect=ImportError):
            callbacks.watch_job(
                job=sample_job,
                check_interval=1,
            )

        # Should fall back to polling
        mock_poll.assert_called_once()


def test_poll_status_invalid_params():
    """Test poll_status with invalid parameters."""
    callbacks = JobCallbacks()

    with pytest.raises(ValueError, match="Must provide either"):
        callbacks.poll_status()


def test_callbacks_with_custom_timeout():
    """Test callbacks with custom timeout values."""
    callbacks = JobCallbacks(
        poll_interval=15,
        timeout=7200,
    )

    assert callbacks.poll_interval == 15
    assert callbacks.timeout == 7200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
