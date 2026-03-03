"""Docker sandbox configuration: image, resource limits, network isolation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DockerConfig:
    """Configuration for Docker container execution.

    Attributes:
        image: Docker image to use
        cpu_quota: CPU quota in microseconds per period (100000 = 1 CPU)
        memory_limit: Memory limit string (e.g. "512m", "1g")
        network_mode: Network mode ("none" for isolation)
        read_only_root: Whether root filesystem is read-only
        timeout_sec: Container execution timeout in seconds
        extra_env: Additional environment variables
        workspace_mount: Path inside container for workspace
    """

    image: str = "python:3.11-slim"
    cpu_quota: int = 100000          # 1 CPU
    memory_limit: str = "512m"
    network_mode: str = "none"       # no network by default
    read_only_root: bool = False
    timeout_sec: int = 300
    extra_env: dict[str, str] = field(default_factory=dict)
    workspace_mount: str = "/workspace"

    def to_run_kwargs(self) -> dict:
        """Convert config to docker-py run() keyword arguments."""
        return {
            "image": self.image,
            "cpu_quota": self.cpu_quota,
            "mem_limit": self.memory_limit,
            "network_mode": self.network_mode,
            "read_only": self.read_only_root,
            "environment": self.extra_env,
            "working_dir": self.workspace_mount,
            "detach": True,
            "remove": False,  # cleanup handled separately
        }
