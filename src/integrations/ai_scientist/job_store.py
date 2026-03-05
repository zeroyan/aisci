"""Job store for AI-Scientist async tasks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.schemas.ai_scientist import JobRecord, JobStatus


class JobStore:
    """Manages job records in JSONL format with concurrent control."""

    def __init__(self, storage_path: Path, max_concurrent: int = 2):
        """Initialize job store.

        Args:
            storage_path: Path to jobs.jsonl file
            max_concurrent: Maximum concurrent running jobs
        """
        self.storage_path = storage_path
        self.max_concurrent = max_concurrent
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.storage_path.exists():
            self.storage_path.touch()

    def save(self, job: JobRecord) -> None:
        """Save or update a job record."""
        jobs = self.list_all()

        # Update existing or append new
        updated = False
        for i, existing in enumerate(jobs):
            if existing.job_id == job.job_id:
                jobs[i] = job
                updated = True
                break

        if not updated:
            jobs.append(job)

        # Write all jobs back
        with self.storage_path.open("w") as f:
            for j in jobs:
                f.write(j.model_dump_json() + "\n")

    def load(self, job_id: str) -> Optional[JobRecord]:
        """Load a job record by ID."""
        for job in self.list_all():
            if job.job_id == job_id:
                return job
        return None

    def list_all(self) -> list[JobRecord]:
        """List all job records."""
        if not self.storage_path.exists() or self.storage_path.stat().st_size == 0:
            return []

        jobs = []
        with self.storage_path.open("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    jobs.append(JobRecord.model_validate_json(line))
        return jobs

    def can_submit(self) -> bool:
        """Check if a new job can be submitted."""
        running_count = sum(
            1 for job in self.list_all()
            if job.status == JobStatus.RUNNING
        )
        return running_count < self.max_concurrent

    def submit_or_queue(self, job: JobRecord) -> JobStatus:
        """Submit job or queue it if at capacity.

        Returns:
            JobStatus.RUNNING if submitted, JobStatus.PENDING if queued
        """
        if self.can_submit():
            job.status = JobStatus.RUNNING
        else:
            job.status = JobStatus.PENDING

        self.save(job)
        return job.status
