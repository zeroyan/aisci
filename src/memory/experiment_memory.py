"""Experiment memory for recording and retrieving execution history."""

from pathlib import Path

from src.memory.embedding_cache import EmbeddingCache
from src.memory.memory_serializer import MemorySerializer
from src.memory.similarity_search import SimilaritySearch
from src.schemas.orchestrator import MemoryEntry


class ExperimentMemory:
    """Manage experiment execution history.

    Responsibilities:
    - Record all attempts (successes and failures)
    - Retrieve similar past attempts
    - Support cross-run knowledge sharing
    """

    def __init__(
        self,
        memory_dir: Path,
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Initialize experiment memory.

        Args:
            memory_dir: Directory to store memory files
            embedding_model: Name of embedding model
        """
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.serializer = MemorySerializer()
        self.cache = EmbeddingCache(memory_dir / "embeddings")
        self.similarity_search = SimilaritySearch(embedding_model, self.cache)

        self.attempts_path = memory_dir / "attempts.jsonl"
        self.failures_path = memory_dir / "failures.jsonl"
        self.successes_path = memory_dir / "successes.jsonl"

    def record_attempt(self, entry: MemoryEntry) -> None:
        """Record an attempt to memory.

        Args:
            entry: Memory entry to record

        Note:
            Automatically categorizes into failures or successes.
        """
        # Write to attempts
        self.serializer.write_entry(entry, self.attempts_path)

        # Categorize
        if entry.critic_feedback.status == "success":
            self.serializer.write_entry(entry, self.successes_path)
        elif entry.critic_feedback.status == "failed":
            self.serializer.write_entry(entry, self.failures_path)

    def load_attempts(self) -> list[MemoryEntry]:
        """Load all attempts from memory.

        Returns:
            List of all memory entries
        """
        return self.serializer.read_entries(self.attempts_path)

    def load_failures(self) -> list[MemoryEntry]:
        """Load failure cases from memory.

        Returns:
            List of failure memory entries
        """
        return self.serializer.read_entries(self.failures_path)

    def load_successes(self) -> list[MemoryEntry]:
        """Load success cases from memory.

        Returns:
            List of success memory entries
        """
        return self.serializer.read_entries(self.successes_path)

    def find_similar_failures(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[MemoryEntry, float]]:
        """Find similar failure cases.

        Args:
            query: Query text describing the current situation
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (entry, similarity_score) tuples
        """
        failures = self.load_failures()
        return self.similarity_search.find_similar(query, failures, top_k, threshold)

    def find_similar_successes(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[MemoryEntry, float]]:
        """Find similar success cases.

        Args:
            query: Query text describing the current situation
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (entry, similarity_score) tuples
        """
        successes = self.load_successes()
        return self.similarity_search.find_similar(query, successes, top_k, threshold)

    def get_statistics(self) -> dict[str, int]:
        """Get memory statistics.

        Returns:
            Dictionary with counts
        """
        return {
            "total_attempts": len(self.load_attempts()),
            "failures": len(self.load_failures()),
            "successes": len(self.load_successes()),
        }
