"""Memory aggregator for merging branch memories into global knowledge base."""

from pathlib import Path

from src.memory.memory_serializer import MemorySerializer
from src.schemas.orchestrator import MemoryEntry


class MemoryAggregator:
    """Aggregate branch-local memories into global knowledge base."""

    def __init__(self, global_kb_path: Path) -> None:
        """Initialize memory aggregator.

        Args:
            global_kb_path: Path to global knowledge base directory
        """
        self.global_kb_path = global_kb_path
        self.global_kb_path.mkdir(parents=True, exist_ok=True)
        self.serializer = MemorySerializer()

    def aggregate_from_branches(
        self,
        branch_memory_dirs: list[Path],
        run_id: str,
    ) -> dict[str, int]:
        """Aggregate memories from multiple branches into global KB.

        Args:
            branch_memory_dirs: List of branch memory directories
            run_id: Run identifier for tracking

        Returns:
            Statistics about aggregation
        """
        all_entries: list[MemoryEntry] = []
        failures: list[MemoryEntry] = []
        successes: list[MemoryEntry] = []

        # Collect from all branches
        for branch_dir in branch_memory_dirs:
            attempts_path = branch_dir / "attempts.jsonl"
            if attempts_path.exists():
                entries = self.serializer.read_entries(attempts_path)
                all_entries.extend(entries)

                # Categorize
                for entry in entries:
                    if entry.critic_feedback.status == "success":
                        successes.append(entry)
                    elif entry.critic_feedback.status == "failed":
                        failures.append(entry)

        # Write to global KB
        if all_entries:
            global_attempts = self.global_kb_path / "attempts.jsonl"
            for entry in all_entries:
                self.serializer.write_entry(entry, global_attempts)

        if failures:
            global_failures = self.global_kb_path / "failures.jsonl"
            for entry in failures:
                self.serializer.write_entry(entry, global_failures)

        if successes:
            global_successes = self.global_kb_path / "successes.jsonl"
            for entry in successes:
                self.serializer.write_entry(entry, global_successes)

        return {
            "run_id": run_id,
            "total_entries": len(all_entries),
            "failures": len(failures),
            "successes": len(successes),
            "branches_processed": len(branch_memory_dirs),
        }

    def load_global_failures(self) -> list[MemoryEntry]:
        """Load all failures from global KB.

        Returns:
            List of failure entries
        """
        failures_path = self.global_kb_path / "failures.jsonl"
        return self.serializer.read_entries(failures_path)

    def load_global_successes(self) -> list[MemoryEntry]:
        """Load all successes from global KB.

        Returns:
            List of success entries
        """
        successes_path = self.global_kb_path / "successes.jsonl"
        return self.serializer.read_entries(successes_path)

    def get_global_statistics(self) -> dict[str, int]:
        """Get global knowledge base statistics.

        Returns:
            Statistics dictionary
        """
        attempts_path = self.global_kb_path / "attempts.jsonl"
        failures_path = self.global_kb_path / "failures.jsonl"
        successes_path = self.global_kb_path / "successes.jsonl"

        return {
            "total_attempts": len(self.serializer.read_entries(attempts_path)),
            "failures": len(self.serializer.read_entries(failures_path)),
            "successes": len(self.serializer.read_entries(successes_path)),
        }
