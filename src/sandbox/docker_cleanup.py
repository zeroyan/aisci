"""Docker container cleanup: context manager ensuring containers are removed."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)


class DockerCleanup:
    """Manages Docker container lifecycle and ensures cleanup.

    Usage:
        cleanup = DockerCleanup(client)
        with cleanup.managed_container(container) as c:
            # use container
        # container is removed after block exits
    """

    def __init__(self, client) -> None:
        """Initialize with a docker client.

        Args:
            client: docker.DockerClient instance
        """
        self.client = client
        self._tracked: list = []

    def track(self, container) -> None:
        """Track a container for cleanup.

        Args:
            container: docker Container object
        """
        self._tracked.append(container)

    def remove_container(self, container) -> bool:
        """Remove a single container.

        Args:
            container: docker Container object

        Returns:
            True if removed successfully, False otherwise
        """
        try:
            container.stop(timeout=5)
        except Exception:
            pass  # already stopped

        try:
            container.remove(force=True)
            logger.debug("Removed container %s", container.id[:12])
            return True
        except Exception as e:
            logger.warning("Failed to remove container %s: %s", container.id[:12], e)
            return False

    def cleanup_all(self) -> dict[str, int]:
        """Remove all tracked containers.

        Returns:
            Stats dict with 'removed' and 'failed' counts
        """
        removed = 0
        failed = 0
        for container in self._tracked:
            if self.remove_container(container):
                removed += 1
            else:
                failed += 1
        self._tracked.clear()
        return {"removed": removed, "failed": failed}

    @contextmanager
    def managed_container(self, container) -> Generator:
        """Context manager that ensures container cleanup on exit.

        Args:
            container: docker Container object

        Yields:
            The container
        """
        try:
            yield container
        finally:
            self.remove_container(container)
