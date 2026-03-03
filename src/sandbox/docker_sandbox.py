"""Docker sandbox: container-based execution with resource limits."""

from __future__ import annotations

import logging
import tarfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from src.sandbox.base import SandboxExecutor
from src.sandbox.docker_cleanup import DockerCleanup
from src.sandbox.docker_config import DockerConfig
from src.sandbox.dependency_installer import DependencyInstaller
from src.schemas import ResourceUsage
from src.schemas.sandbox_io import SandboxRequest, SandboxResponse, SandboxStatus

logger = logging.getLogger(__name__)


class DockerSandbox(SandboxExecutor):
    """Execute experiment code inside a Docker container.

    Provides stronger isolation than SubprocessSandbox:
    - Network isolation (network_mode=none by default)
    - CPU and memory resource limits
    - Container removed after each execution
    """

    def __init__(
        self,
        config: DockerConfig | None = None,
        runs_dir: str | Path = "runs",
    ) -> None:
        """Initialize Docker sandbox.

        Args:
            config: Docker configuration (uses defaults if None)
            runs_dir: Directory for run artifacts
        """
        self.config = config or DockerConfig()
        self.runs_dir = Path(runs_dir)
        self._installer = DependencyInstaller()
        self._client = None  # lazy init

    def _get_client(self):
        """Get or create Docker client (lazy initialization)."""
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    def execute(self, request: SandboxRequest) -> SandboxResponse:
        """Execute code in a Docker container.

        Args:
            request: Sandbox execution request

        Returns:
            SandboxResponse with execution results
        """
        started_at = datetime.now(timezone.utc)

        # Prepare workspace on host
        workspace = (
            self.runs_dir
            / request.run_id
            / "iterations"
            / f"it_{request.iteration_index:04d}"
            / "workspace"
        )
        workspace.mkdir(parents=True, exist_ok=True)

        # Write code snapshot files to host workspace
        for filename, content in request.code_snapshot.files.items():
            file_path = workspace / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        try:
            client = self._get_client()
            cleanup = DockerCleanup(client)

            # Create container
            run_kwargs = self.config.to_run_kwargs()
            run_kwargs["command"] = "sleep infinity"  # keep alive for exec
            container = client.containers.run(**run_kwargs)
            cleanup.track(container)

            with cleanup.managed_container(container):
                # Copy workspace files into container
                self._copy_to_container(container, workspace, self.config.workspace_mount)

                # Install dependencies if requirements.txt present
                req_path = workspace / "requirements.txt"
                if req_path.exists():
                    self._installer.install_from_file(container, req_path)

                # Execute entrypoint with timeout
                import signal

                def timeout_handler(signum, frame):
                    raise TimeoutError(f"Execution exceeded {self.config.timeout_sec}s")

                # Set timeout alarm (Unix only)
                try:
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(self.config.timeout_sec)

                    exit_code, output = container.exec_run(
                        ["sh", "-c", request.code_snapshot.entrypoint],
                        workdir=self.config.workspace_mount,
                        demux=True,
                    )

                    signal.alarm(0)  # Cancel alarm
                except TimeoutError as e:
                    signal.alarm(0)
                    raise RuntimeError(str(e)) from e

                stdout = (output[0] or b"").decode("utf-8", errors="replace")
                stderr = (output[1] or b"").decode("utf-8", errors="replace")

                ended_at = datetime.now(timezone.utc)
                wall_time = (ended_at - started_at).total_seconds()

                status = (
                    SandboxStatus.succeeded if exit_code == 0 else SandboxStatus.failed
                )

                return SandboxResponse(
                    request_id=request.request_id,
                    status=status,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    resource_usage=ResourceUsage(wall_time_sec=wall_time),
                    started_at=started_at,
                    ended_at=ended_at,
                )

        except Exception as e:
            ended_at = datetime.now(timezone.utc)
            wall_time = (ended_at - started_at).total_seconds()
            logger.exception("Docker execution failed")
            return SandboxResponse(
                request_id=request.request_id,
                status=SandboxStatus.failed,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                resource_usage=ResourceUsage(wall_time_sec=wall_time),
                started_at=started_at,
                ended_at=ended_at,
            )

    def _copy_to_container(
        self, container, src_dir: Path, dest_dir: str
    ) -> None:
        """Copy a local directory into a running container.

        Args:
            container: docker Container object
            src_dir: Local source directory
            dest_dir: Destination path inside container
        """
        buf = BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for file_path in src_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(src_dir)
                    tar.add(file_path, arcname=str(arcname))
        buf.seek(0)
        container.put_archive(dest_dir, buf)

    def cleanup(self) -> None:
        """Close Docker client connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
