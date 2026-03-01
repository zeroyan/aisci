"""MVP sandbox: subprocess + venv execution."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.schemas import ResourceUsage
from src.schemas.sandbox_io import (
    SandboxRequest,
    SandboxResponse,
    SandboxStatus,
)
from src.sandbox.base import SandboxExecutor

logger = logging.getLogger(__name__)

STDOUT_MAX_BYTES = 100 * 1024  # 100 KB


class SubprocessSandbox(SandboxExecutor):
    """Execute experiment code via subprocess in an isolated workspace."""

    def __init__(self, runs_dir: str | Path = "runs") -> None:
        self.runs_dir = Path(runs_dir)

    def execute(self, request: SandboxRequest) -> SandboxResponse:
        started_at = datetime.now(timezone.utc)

        # Prepare workspace
        workspace = (
            self.runs_dir
            / request.run_id
            / "iterations"
            / f"it_{request.iteration_index:04d}"
            / "workspace"
        )
        workspace.mkdir(parents=True, exist_ok=True)

        # Write code snapshot files
        for filename, content in request.code_snapshot.files.items():
            file_path = workspace / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        # Write requirements.txt if present and install
        if "requirements.txt" in request.code_snapshot.files:
            self._install_requirements(workspace)

        # Execute entrypoint
        try:
            result = subprocess.run(
                request.code_snapshot.entrypoint,
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=request.timeout_sec,
                executable=sys.executable.replace("python", "bash")
                if not request.code_snapshot.entrypoint.startswith("python")
                else None,
                env=self._build_env(workspace),
            )

            ended_at = datetime.now(timezone.utc)
            wall_time = (ended_at - started_at).total_seconds()

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            # Truncate stdout/stderr and save full versions if needed
            iter_dir = workspace.parent
            if len(stdout.encode()) > STDOUT_MAX_BYTES:
                (iter_dir / "stdout_full.log").write_text(stdout, encoding="utf-8")
                stdout = stdout[: STDOUT_MAX_BYTES // 2] + "\n...[truncated]...\n"
            if len(stderr.encode()) > STDOUT_MAX_BYTES:
                (iter_dir / "stderr_full.log").write_text(stderr, encoding="utf-8")
                stderr = stderr[: STDOUT_MAX_BYTES // 2] + "\n...[truncated]...\n"

            # Parse output files (metrics.json)
            output_files = self._collect_output_files(workspace)

            status = (
                SandboxStatus.succeeded
                if result.returncode == 0
                else SandboxStatus.failed
            )

            return SandboxResponse(
                request_id=request.request_id,
                status=status,
                exit_code=result.returncode,
                stdout=stdout,
                stderr=stderr,
                output_files=output_files,
                resource_usage=ResourceUsage(wall_time_sec=wall_time),
                started_at=started_at,
                ended_at=ended_at,
            )

        except subprocess.TimeoutExpired as e:
            ended_at = datetime.now(timezone.utc)
            wall_time = (ended_at - started_at).total_seconds()
            return SandboxResponse(
                request_id=request.request_id,
                status=SandboxStatus.timeout,
                exit_code=-1,
                stdout=str(e.stdout or ""),
                stderr=str(e.stderr or ""),
                resource_usage=ResourceUsage(wall_time_sec=wall_time),
                started_at=started_at,
                ended_at=ended_at,
            )

        except MemoryError:
            ended_at = datetime.now(timezone.utc)
            wall_time = (ended_at - started_at).total_seconds()
            return SandboxResponse(
                request_id=request.request_id,
                status=SandboxStatus.oom,
                exit_code=-1,
                resource_usage=ResourceUsage(wall_time_sec=wall_time),
                started_at=started_at,
                ended_at=ended_at,
            )

    def _build_env(self, workspace: Path) -> dict[str, str]:
        """Build environment variables, inheriting the current env."""
        import os

        env = os.environ.copy()
        env["PYTHONPATH"] = str(workspace)
        return env

    def _install_requirements(self, workspace: Path) -> None:
        """Install requirements.txt into the workspace venv."""
        req_file = workspace / "requirements.txt"
        if req_file.exists():
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                logger.warning("requirements.txt install timed out")

    def _collect_output_files(self, workspace: Path) -> dict[str, str]:
        """Collect known output files (metrics.json, etc.)."""
        output_files: dict[str, str] = {}
        metrics_path = workspace / "metrics.json"
        if metrics_path.exists():
            try:
                content = metrics_path.read_text(encoding="utf-8")
                json.loads(content)  # validate JSON
                output_files["metrics.json"] = content
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read metrics.json: %s", e)
        return output_files
