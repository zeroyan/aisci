"""Abstract base class for sandbox executors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.sandbox_io import SandboxRequest, SandboxResponse


class SandboxExecutor(ABC):
    """Interface for executing experiment code in an isolated environment."""

    @abstractmethod
    def execute(self, request: SandboxRequest) -> SandboxResponse:
        """Run the code described by *request* and return the result."""

    def cleanup(self) -> None:
        """Optional hook for releasing resources after a run completes."""
