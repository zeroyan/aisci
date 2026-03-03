"""Memory serializer for writing entries to JSONL."""

import json
from pathlib import Path

from src.schemas.orchestrator import MemoryEntry


class MemorySerializer:
    """Serialize memory entries to JSONL format."""

    def write_entry(self, entry: MemoryEntry, file_path: Path) -> None:
        """Write a single memory entry to JSONL file.

        Args:
            entry: Memory entry to write
            file_path: Path to JSONL file

        Note:
            Appends to file if it exists, creates if it doesn't.
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize entry to JSON
        entry_json = json.dumps(entry.model_dump(mode="json"))

        # Append to file
        with open(file_path, "a") as f:
            f.write(entry_json + "\n")

    def read_entries(self, file_path: Path) -> list[MemoryEntry]:
        """Read all memory entries from JSONL file.

        Args:
            file_path: Path to JSONL file

        Returns:
            List of memory entries
        """
        if not file_path.exists():
            return []

        entries = []
        with open(file_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(MemoryEntry(**data))

        return entries

    def write_entries(self, entries: list[MemoryEntry], file_path: Path) -> None:
        """Write multiple memory entries to JSONL file.

        Args:
            entries: List of memory entries
            file_path: Path to JSONL file

        Note:
            Overwrites file if it exists.
        """
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            for entry in entries:
                entry_json = json.dumps(entry.model_dump(mode="json"))
                f.write(entry_json + "\n")
