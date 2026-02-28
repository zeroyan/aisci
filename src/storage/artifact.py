"""Artifact storage: manages runs/<run_id>/ directory and JSON persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ArtifactStore:
    """File-system artifact store for experiment runs."""

    def __init__(self, runs_dir: str | Path = "runs") -> None:
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def run_path(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def create_run_dir(self, run_id: str) -> Path:
        """Create the run directory structure and return the root path."""
        run_dir = self.run_path(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "spec").mkdir(exist_ok=True)
        (run_dir / "plan").mkdir(exist_ok=True)
        (run_dir / "iterations").mkdir(exist_ok=True)
        return run_dir

    def save_json(self, run_id: str, rel_path: str, data: BaseModel | dict) -> Path:
        """Serialize data to JSON and write to runs/<run_id>/<rel_path>."""
        full_path = self.run_path(run_id) / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, BaseModel):
            payload = data.model_dump(mode="json")
        else:
            payload = data

        full_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug("Saved JSON: %s", full_path)
        return full_path

    def load_json(self, run_id: str, rel_path: str) -> dict:
        """Load JSON from runs/<run_id>/<rel_path>."""
        full_path = self.run_path(run_id) / rel_path
        return json.loads(full_path.read_text(encoding="utf-8"))

    def save_text(self, run_id: str, rel_path: str, content: str) -> Path:
        """Write plain text to runs/<run_id>/<rel_path>."""
        full_path = self.run_path(run_id) / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return full_path

    def load_text(self, run_id: str, rel_path: str) -> str:
        """Read plain text from runs/<run_id>/<rel_path>."""
        full_path = self.run_path(run_id) / rel_path
        return full_path.read_text(encoding="utf-8")

    def list_artifacts(self, run_id: str) -> list[str]:
        """List all files under runs/<run_id>/ as relative paths."""
        run_dir = self.run_path(run_id)
        if not run_dir.exists():
            return []
        return [str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()]

    def path_exists(self, run_id: str, rel_path: str) -> bool:
        """Check if a file exists under runs/<run_id>/<rel_path>."""
        return (self.run_path(run_id) / rel_path).exists()
