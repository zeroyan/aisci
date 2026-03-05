"""Callback mechanisms for AI-Scientist job monitoring."""

import time
from pathlib import Path
from typing import Callable, Optional

import psutil

from src.schemas.ai_scientist import JobRecord, JobStatus


class JobCallbacks:
    """Manages callbacks for job status changes."""

    def __init__(
        self,
        adapter=None,
        job_store=None,
        poll_interval: int = 60,
        timeout: int = 86400,
        on_complete: Optional[Callable[[JobRecord], None]] = None,
        on_failed: Optional[Callable[[JobRecord], None]] = None,
        auto_start_pending: bool = True,
    ):
        """Initialize callbacks.

        Args:
            adapter: AIScientistAdapter instance (optional)
            job_store: JobStore instance (optional)
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait
            on_complete: Callback when job completes
            on_failed: Callback when job fails
            auto_start_pending: Auto-start next pending job when current completes
        """
        self.adapter = adapter
        self.job_store = job_store
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.on_complete = on_complete
        self.on_failed = on_failed
        self.auto_start_pending = auto_start_pending

    def poll_status(
        self,
        job: JobRecord | None = None,
        job_id: str | None = None,
        check_process: Callable[[int], bool] | None = None,
        interval: int | None = None,
        timeout: int | None = None,
    ) -> dict | JobStatus:
        """Poll job status until completion or timeout.

        Args:
            job: Job record to monitor (legacy interface)
            job_id: Job ID to monitor (new interface, requires adapter and job_store)
            check_process: Function to check if process is running (legacy)
            interval: Override poll interval
            timeout: Override timeout

        Returns:
            Final job status (legacy) or status dict (new)
        """
        # Use provided values or defaults
        poll_interval = interval or self.poll_interval
        max_timeout = timeout or self.timeout

        # New interface: job_id + adapter + job_store
        if job_id and self.adapter and self.job_store:
            return self._poll_by_job_id(job_id, poll_interval, max_timeout)

        # Legacy interface: job + check_process
        if job and check_process:
            return self._poll_legacy(job, check_process, poll_interval, max_timeout)

        raise ValueError("Must provide either (job_id) or (job + check_process)")

    def _poll_by_job_id(self, job_id: str, interval: int, timeout: int) -> dict:
        """Poll job status by job ID (new interface).

        Args:
            job_id: Job ID to monitor
            interval: Seconds between checks
            timeout: Maximum seconds to wait

        Returns:
            Status dict with keys: status, progress, elapsed_time, error
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout:
                return {
                    "status": "timeout",
                    "progress": None,
                    "elapsed_time": f"{int(elapsed)}s",
                    "error": f"Timeout after {timeout}s",
                }

            # Get current status
            status = self.adapter.get_status(
                job=self.job_store.load(job_id),
                job_store=self.job_store,
            )

            # Check if completed or failed
            if status["status"] in ["completed", "failed"]:
                # Trigger callbacks
                if status["status"] == "completed" and self.on_complete:
                    self.on_complete(self.job_store.load(job_id))
                elif status["status"] == "failed" and self.on_failed:
                    self.on_failed(self.job_store.load(job_id))

                # Auto-start next pending job if enabled
                if self.auto_start_pending and self.adapter:
                    self.adapter._try_start_pending_job(self.job_store)

                return status

            # Print progress
            print(f"  Status: {status['status']} | Progress: {status.get('progress', 'N/A')} | Elapsed: {status['elapsed_time']}")

            time.sleep(interval)

    def _poll_legacy(
        self,
        job: JobRecord,
        check_process: Callable[[int], bool],
        interval: int,
        timeout: int,
    ) -> JobStatus:
        """Poll job status (legacy interface).

        Args:
            job: Job record to monitor
            check_process: Function to check if process is running
            interval: Seconds between checks
            timeout: Maximum seconds to wait

        Returns:
            Final job status
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout:
                return JobStatus.FAILED

            # Check process status
            if not check_process(job.pid):
                # Process ended, determine final status
                if self._check_success(job):
                    if self.on_complete:
                        self.on_complete(job)
                    # Auto-start next pending job
                    if self.auto_start_pending and self.adapter and self.job_store:
                        self.adapter._try_start_pending_job(self.job_store)
                    return JobStatus.COMPLETED
                else:
                    if self.on_failed:
                        self.on_failed(job)
                    # Auto-start next pending job even on failure
                    if self.auto_start_pending and self.adapter and self.job_store:
                        self.adapter._try_start_pending_job(self.job_store)
                    return JobStatus.FAILED

            time.sleep(interval)

    def _check_success(self, job: JobRecord) -> bool:
        """Check if job completed successfully.

        Args:
            job: Job record to check

        Returns:
            True if successful
        """
        # Check if result directory exists
        result_dir = Path(job.log_path).parent.parent / "results"
        return result_dir.exists() and any(result_dir.iterdir())

    @staticmethod
    def check_process_running(pid: int) -> bool:
        """Check if process is running.

        Args:
            pid: Process ID

        Returns:
            True if running
        """
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False

    def watch_job(
        self,
        job: JobRecord,
        check_interval: int = 5,
        on_complete: Optional[Callable[[JobRecord], None]] = None,
        on_failed: Optional[Callable[[JobRecord], None]] = None,
    ) -> None:
        """Watch job using file system events (optional feature).

        Args:
            job: Job record to watch
            check_interval: Seconds between checks
            on_complete: Callback when job completes
            on_failed: Callback when job fails

        Note:
            This is an optional feature using watchdog library.
            Falls back to polling if watchdog is not available.
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class JobWatcher(FileSystemEventHandler):
                def __init__(self, job_record: JobRecord, callbacks: JobCallbacks):
                    self.job = job_record
                    self.callbacks = callbacks

                def on_modified(self, event):
                    if event.src_path == self.job.log_path:
                        # Log file updated, check status
                        if not self.callbacks.check_process_running(self.job.pid):
                            # Process ended
                            if self.callbacks._check_success(self.job):
                                if on_complete:
                                    on_complete(self.job)
                            else:
                                if on_failed:
                                    on_failed(self.job)

            # Setup observer
            observer = Observer()
            event_handler = JobWatcher(job, self)
            log_dir = Path(job.log_path).parent
            observer.schedule(event_handler, str(log_dir), recursive=False)
            observer.start()

            # Keep watching until job completes
            while self.check_process_running(job.pid):
                time.sleep(check_interval)

            observer.stop()
            observer.join()

        except ImportError:
            # Watchdog not available, fall back to polling
            self.poll_status(
                job=job,
                check_process=self.check_process_running,
                interval=check_interval,
            )
