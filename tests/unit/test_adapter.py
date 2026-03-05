"""Unit tests for AIScientistAdapter."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.integrations.ai_scientist.adapter import AIScientistAdapter
from src.integrations.ai_scientist.job_store import JobStore
from src.schemas.ai_scientist import JobRecord, JobStatus
from src.schemas.research_spec import ResearchSpec, Metric
from src.schemas import Constraints


@pytest.fixture
def temp_runtime_path(tmp_path):
    """Create temporary runtime path."""
    runtime_path = tmp_path / "ai-scientist-runtime"
    runtime_path.mkdir()

    # Create launch script
    launch_script = runtime_path / "launch_scientist.py"
    launch_script.write_text("#!/usr/bin/env python\nprint('AI-Scientist')")

    # Create venv
    venv_dir = runtime_path / ".venv" / "bin"
    venv_dir.mkdir(parents=True)
    (venv_dir / "python").write_text("#!/bin/bash\necho 'python'")

    return runtime_path


@pytest.fixture
def sample_spec():
    """Create sample research spec."""
    return ResearchSpec(
        spec_id="test_spec_001",
        title="Test Research",
        objective="Test the AI-Scientist integration",
        metrics=[
            Metric(
                name="accuracy",
                description="Model accuracy",
                direction="maximize",
                target=0.9,
            ),
        ],
        constraints=Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=1.0,
            max_iterations=10,
            compute="cpu",
        ),
        status="confirmed",
    )


@pytest.fixture
def temp_job_store(tmp_path):
    """Create temporary job store."""
    storage_path = tmp_path / "jobs.jsonl"
    return JobStore(storage_path, max_concurrent=2)


def test_adapter_initialization(temp_runtime_path):
    """Test AIScientistAdapter initialization."""
    adapter = AIScientistAdapter(temp_runtime_path)
    assert adapter.runtime_path == temp_runtime_path
    assert adapter.launch_script == temp_runtime_path / "launch_scientist.py"


def test_is_installed(temp_runtime_path):
    """Test checking if AI-Scientist is installed."""
    adapter = AIScientistAdapter(temp_runtime_path)
    assert adapter.is_installed() is True

    # Test with non-existent path
    adapter2 = AIScientistAdapter(Path("/nonexistent"))
    assert adapter2.is_installed() is False


@patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test_key"})
@patch("subprocess.Popen")
def test_submit_job(mock_popen, temp_runtime_path, sample_spec, temp_job_store, tmp_path):
    """Test submitting a job."""
    # Setup mock process
    mock_process = Mock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process

    # Create runs directory
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    adapter = AIScientistAdapter(temp_runtime_path)

    job_id = adapter.submit_job(
        run_id="test_run",
        spec=sample_spec,
        model="deepseek-chat",
        num_ideas=2,
        writeup="md",
        job_store=temp_job_store,
    )

    assert job_id is not None
    assert len(job_id) > 0

    # Verify job was saved
    job = temp_job_store.load(job_id)
    assert job is not None
    assert job.status == JobStatus.RUNNING
    assert job.pid == 12345


@patch.dict("os.environ", {}, clear=True)
def test_submit_job_no_api_key(temp_runtime_path, sample_spec, temp_job_store):
    """Test submitting job without API key."""
    adapter = AIScientistAdapter(temp_runtime_path)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        adapter.submit_job(
            run_id="test_run",
            spec=sample_spec,
            model="deepseek-chat",
            num_ideas=2,
            writeup="md",
            job_store=temp_job_store,
        )


def test_get_status_running(temp_runtime_path, temp_job_store):
    """Test getting status of running job."""
    adapter = AIScientistAdapter(temp_runtime_path)

    # Create a running job
    job = JobRecord(
        job_id="test_job",
        run_id="test_run",
        pid=99999,  # Non-existent PID
        status=JobStatus.RUNNING,
        log_path="/tmp/test.log",
        start_time=datetime.now(),
        template_name="test_template",
        num_ideas=2,
        model="deepseek-chat",
        writeup="md",
    )
    temp_job_store.save(job)

    with patch("psutil.Process") as mock_process:
        mock_process.return_value.is_running.return_value = True

        status = adapter.get_status(job, temp_job_store)

        assert status["status"] == "running"
        assert "progress" in status
        assert "elapsed_time" in status


def test_get_status_completed(temp_runtime_path, temp_job_store, tmp_path):
    """Test getting status of completed job."""
    adapter = AIScientistAdapter(temp_runtime_path)

    # Create result directory
    result_dir = tmp_path / "runs" / "test_run" / "external" / "results" / "test_job"
    result_dir.mkdir(parents=True)
    (result_dir / "result.txt").write_text("test")

    # Create a job that just finished
    job = JobRecord(
        job_id="test_job",
        run_id="test_run",
        pid=99999,
        status=JobStatus.RUNNING,
        log_path="/tmp/test.log",
        start_time=datetime.now(),
        template_name="test_template",
        num_ideas=2,
        model="deepseek-chat",
        writeup="md",
    )
    temp_job_store.save(job)

    with patch("psutil.Process") as mock_process:
        mock_process.side_effect = Exception("Process not found")

        status = adapter.get_status(job, temp_job_store)

        # Should be marked as completed
        updated_job = temp_job_store.load("test_job")
        assert updated_job.status == JobStatus.COMPLETED


@patch("psutil.Process")
def test_cancel_job(mock_process_class, temp_runtime_path, temp_job_store):
    """Test cancelling a job."""
    adapter = AIScientistAdapter(temp_runtime_path)

    # Create mock process
    mock_process = Mock()
    mock_process.is_running.return_value = True
    mock_process_class.return_value = mock_process

    # Create a running job
    job = JobRecord(
        job_id="test_job",
        run_id="test_run",
        pid=12345,
        status=JobStatus.RUNNING,
        log_path="/tmp/test.log",
        start_time=datetime.now(),
        template_name="test_template",
        num_ideas=2,
        model="deepseek-chat",
        writeup="md",
    )
    temp_job_store.save(job)

    # Cancel job
    adapter.cancel_job(job, temp_job_store, force=False)

    # Verify process was terminated
    mock_process.terminate.assert_called_once()

    # Verify job status updated
    updated_job = temp_job_store.load("test_job")
    assert updated_job.status == JobStatus.FAILED
    assert "Cancelled" in updated_job.error


@patch("psutil.Process")
def test_cancel_job_force(mock_process_class, temp_runtime_path, temp_job_store):
    """Test force cancelling a job."""
    adapter = AIScientistAdapter(temp_runtime_path)

    # Create mock process
    mock_process = Mock()
    mock_process.is_running.return_value = True
    mock_process_class.return_value = mock_process

    # Create a running job
    job = JobRecord(
        job_id="test_job",
        run_id="test_run",
        pid=12345,
        status=JobStatus.RUNNING,
        log_path="/tmp/test.log",
        start_time=datetime.now(),
        template_name="test_template",
        num_ideas=2,
        model="deepseek-chat",
        writeup="md",
    )
    temp_job_store.save(job)

    # Force cancel job
    adapter.cancel_job(job, temp_job_store, force=True)

    # Verify process was killed
    mock_process.kill.assert_called_once()


def test_estimate_progress(temp_runtime_path, tmp_path):
    """Test estimating job progress from log."""
    adapter = AIScientistAdapter(temp_runtime_path)

    # Create log file
    log_path = tmp_path / "test.log"
    log_path.write_text("""
Processing idea: idea_1
Processing idea: idea_2
Checking novelty of idea 1
Checking novelty of idea 2
""")

    job = JobRecord(
        job_id="test_job",
        run_id="test_run",
        pid=12345,
        status=JobStatus.RUNNING,
        log_path=str(log_path),
        start_time=datetime.now(),
        template_name="test_template",
        num_ideas=3,
        model="deepseek-chat",
        writeup="md",
    )

    progress = adapter._estimate_progress(job)
    assert "2/3" in progress or "ideas" in progress


@patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test_key"})
@patch("subprocess.Popen")
def test_submit_job_with_custom_template(
    mock_popen, temp_runtime_path, sample_spec, temp_job_store
):
    """Test submitting job with custom template name."""
    mock_process = Mock()
    mock_process.pid = 12345
    mock_popen.return_value = mock_process

    adapter = AIScientistAdapter(temp_runtime_path)

    job_id = adapter.submit_job(
        run_id="test_run",
        spec=sample_spec,
        model="deepseek-chat",
        num_ideas=2,
        writeup="md",
        job_store=temp_job_store,
        template_name="custom_template",
    )

    # Verify custom template was used
    job = temp_job_store.load(job_id)
    assert job.template_name == "custom_template"


def test_concurrent_limit(temp_runtime_path, sample_spec, temp_job_store):
    """Test concurrent job limit."""
    adapter = AIScientistAdapter(temp_runtime_path)

    # Fill up concurrent slots
    for i in range(2):
        job = JobRecord(
            job_id=f"job_{i}",
            run_id="test_run",
            pid=12345 + i,
            status=JobStatus.RUNNING,
            log_path=f"/tmp/test_{i}.log",
            start_time=datetime.now(),
            template_name="test_template",
            num_ideas=2,
            model="deepseek-chat",
            writeup="md",
        )
        temp_job_store.save(job)

    # Should not be able to submit more
    assert temp_job_store.can_submit() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
