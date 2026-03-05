"""Unit tests for JobStore."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.integrations.ai_scientist.job_store import JobStore
from src.schemas.ai_scientist import JobRecord, JobStatus


@pytest.fixture
def temp_job_store(tmp_path):
    """Create temporary job store."""
    storage_path = tmp_path / "jobs.jsonl"
    return JobStore(storage_path, max_concurrent=2)


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


def test_job_store_initialization(temp_job_store):
    """Test JobStore initialization."""
    assert temp_job_store.max_concurrent == 2
    assert temp_job_store.storage_path.name == "jobs.jsonl"


def test_save_and_load_job(temp_job_store, sample_job):
    """Test saving and loading job."""
    # Save job
    temp_job_store.save(sample_job)

    # Load job
    loaded_job = temp_job_store.load(sample_job.job_id)

    assert loaded_job is not None
    assert loaded_job.job_id == sample_job.job_id
    assert loaded_job.run_id == sample_job.run_id
    assert loaded_job.status == sample_job.status


def test_list_all_jobs(temp_job_store, sample_job):
    """Test listing all jobs."""
    # Save multiple jobs
    job1 = sample_job
    job2 = sample_job.model_copy(update={"job_id": "test_job_002"})

    temp_job_store.save(job1)
    temp_job_store.save(job2)

    # List all
    jobs = temp_job_store.list_all()

    assert len(jobs) == 2
    assert jobs[0].job_id in ["test_job_001", "test_job_002"]


def test_concurrent_control(temp_job_store, sample_job):
    """Test concurrent job control."""
    # Initially can submit
    assert temp_job_store.can_submit() is True

    # Add 2 running jobs (max_concurrent=2)
    job1 = sample_job
    job2 = sample_job.model_copy(update={"job_id": "test_job_002"})

    temp_job_store.save(job1)
    temp_job_store.save(job2)

    # Should not be able to submit more
    assert temp_job_store.can_submit() is False

    # Complete one job
    job1_completed = job1.model_copy(update={"status": JobStatus.COMPLETED})
    temp_job_store.save(job1_completed)

    # Should be able to submit again
    assert temp_job_store.can_submit() is True


def test_update_job_status(temp_job_store, sample_job):
    """Test updating job status."""
    # Save initial job
    temp_job_store.save(sample_job)

    # Update status
    updated_job = sample_job.model_copy(
        update={
            "status": JobStatus.COMPLETED,
            "end_time": datetime.now(),
        }
    )
    temp_job_store.save(updated_job)

    # Load and verify
    loaded_job = temp_job_store.load(sample_job.job_id)
    assert loaded_job.status == JobStatus.COMPLETED
    assert loaded_job.end_time is not None


def test_load_nonexistent_job(temp_job_store):
    """Test loading non-existent job."""
    job = temp_job_store.load("nonexistent_job")
    assert job is None


def test_persistence(tmp_path, sample_job):
    """Test job persistence across instances."""
    storage_path = tmp_path / "jobs.jsonl"

    # Create first instance and save job
    store1 = JobStore(storage_path, max_concurrent=2)
    store1.save(sample_job)

    # Create second instance and load job
    store2 = JobStore(storage_path, max_concurrent=2)
    loaded_job = store2.load(sample_job.job_id)

    assert loaded_job is not None
    assert loaded_job.job_id == sample_job.job_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
