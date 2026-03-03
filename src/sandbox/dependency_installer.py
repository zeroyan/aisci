"""Dependency installer: installs requirements.txt inside a Docker container."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DependencyInstaller:
    """Installs Python dependencies inside a Docker container.

    Runs pip install inside the container before executing experiment code,
    ensuring the correct packages are available without polluting the host.
    """

    def __init__(self, timeout_sec: int = 120) -> None:
        """Initialize installer.

        Args:
            timeout_sec: Timeout for pip install command
        """
        self.timeout_sec = timeout_sec

    def install_in_container(self, container, requirements_txt: str) -> bool:
        """Install requirements inside a running container.

        Args:
            container: docker Container object
            requirements_txt: Content of requirements.txt

        Returns:
            True if installation succeeded, False otherwise
        """
        # Write requirements to container
        write_cmd = f"echo '{requirements_txt}' > /tmp/requirements.txt"
        exit_code, output = container.exec_run(
            ["sh", "-c", write_cmd], demux=False
        )
        if exit_code != 0:
            logger.warning("Failed to write requirements.txt: %s", output)
            return False

        # Run pip install
        exit_code, output = container.exec_run(
            ["pip", "install", "-r", "/tmp/requirements.txt", "-q"],
            demux=False,
        )

        if exit_code != 0:
            logger.warning("pip install failed (exit %d): %s", exit_code, output)
            return False

        logger.debug("Dependencies installed successfully")
        return True

    def install_from_file(self, container, req_path: Path) -> bool:
        """Install requirements from a local file into a container.

        Args:
            container: docker Container object
            req_path: Path to requirements.txt on host

        Returns:
            True if installation succeeded, False otherwise
        """
        if not req_path.exists():
            logger.debug("No requirements.txt found at %s", req_path)
            return True  # nothing to install

        content = req_path.read_text(encoding="utf-8")
        return self.install_in_container(container, content)

    def parse_requirements(self, requirements_txt: str) -> list[str]:
        """Parse requirements.txt content into package list.

        Args:
            requirements_txt: Content of requirements.txt

        Returns:
            List of package specifiers
        """
        packages = []
        for line in requirements_txt.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                packages.append(line)
        return packages
