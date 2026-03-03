"""Branch-local memory for read-write access."""

import json
from pathlib import Path

from src.schemas.orchestrator import MemoryEntry


class BranchMemory:
    """Branch-local memory for read-write access.

    Location: runs/<run_id>/branches/<branch_id>/memory/
    - attempts.jsonl: All attempts
    - failures.jsonl: Failure cases
    - successes.jsonl: Success cases
    """

    def __init__(self, memory_dir: Path) -> None:
        """Initialize branch memory.

        Args:
            memory_dir: Path to branch memory directory
        """
        self.memory_dir = memory_dir
        self.attempts_path = memory_dir / "attempts.jsonl"
        self.failures_path = memory_dir / "failures.jsonl"
        self.successes_path = memory_dir / "successes.jsonl"

        # Ensure directory exists
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def record_attempt(self, entry: MemoryEntry) -> None:
        """Record an attempt to memory.

        Args:
            entry: Memory entry to record

        Note:
            Appends to attempts.jsonl and also to failures.jsonl
            or successes.jsonl based on status.
        """
        # Write to attempts.jsonl
        with open(self.attempts_path, "a") as f:
            f.write(json.dumps(entry.model_dump(mode="json")) + "\n")

        # Write to failures or successes based on status
        if entry.critic_feedback.status == "success":
            with open(self.successes_path, "a") as f:
                f.write(json.dumps(entry.model_dump(mode="json")) + "\n")
        elif entry.critic_feedback.status == "failed":
            with open(self.failures_path, "a") as f:
                f.write(json.dumps(entry.model_dump(mode="json")) + "\n")

    def load_attempts(self) -> list[MemoryEntry]:
        """Load all attempts from memory.

        Returns:
            List of memory entries
        """
        if not self.attempts_path.exists():
            return []

        entries = []
        with open(self.attempts_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(MemoryEntry(**data))
        return entries

    def load_failures(self) -> list[MemoryEntry]:
        """Load failure cases from memory.

        Returns:
            List of failure memory entries
        """
        if not self.failures_path.exists():
            return []

        entries = []
        with open(self.failures_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(MemoryEntry(**data))
        return entries

    def load_successes(self) -> list[MemoryEntry]:
        """Load success cases from memory.

        Returns:
            List of success memory entries
        """
        if not self.successes_path.exists():
            return []

        entries = []
        with open(self.successes_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entries.append(MemoryEntry(**data))
        return entries

    def get_entry_count(self) -> dict[str, int]:
        """Get count of entries by type.

        Returns:
            Dictionary with counts: {attempts, failures, successes}
        """
        return {
            "attempts": len(self.load_attempts()),
            "failures": len(self.load_failures()),
            "successes": len(self.load_successes()),
        }
