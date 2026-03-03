"""Global knowledge base for read-only access across branches."""

import json
from pathlib import Path


class KnowledgeBase:
    """Global knowledge base shared across all runs (read-only).

    Location: scientist/knowledge/
    - failures.jsonl: Historical failure cases
    - successes.jsonl: Historical success cases
    - embeddings.npy: Embedding vector cache
    """

    def __init__(self, knowledge_dir: Path) -> None:
        """Initialize knowledge base.

        Args:
            knowledge_dir: Path to global knowledge directory
        """
        self.knowledge_dir = knowledge_dir
        self.failures_path = knowledge_dir / "failures.jsonl"
        self.successes_path = knowledge_dir / "successes.jsonl"
        self.embeddings_path = knowledge_dir / "embeddings.npy"

        # Ensure directory exists
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

    def load_failures(self) -> list[dict]:
        """Load historical failure cases.

        Returns:
            List of failure case dictionaries

        Note:
            Returns empty list if file doesn't exist.
        """
        if not self.failures_path.exists():
            return []

        failures = []
        with open(self.failures_path) as f:
            for line in f:
                if line.strip():
                    failures.append(json.loads(line))
        return failures

    def load_successes(self) -> list[dict]:
        """Load historical success cases.

        Returns:
            List of success case dictionaries

        Note:
            Returns empty list if file doesn't exist.
        """
        if not self.successes_path.exists():
            return []

        successes = []
        with open(self.successes_path) as f:
            for line in f:
                if line.strip():
                    successes.append(json.loads(line))
        return successes

    def get_all_entries(self) -> list[dict]:
        """Get all knowledge base entries (failures + successes).

        Returns:
            List of all entries
        """
        return self.load_failures() + self.load_successes()

    def exists(self) -> bool:
        """Check if knowledge base has any entries.

        Returns:
            True if knowledge base has entries, False otherwise
        """
        return self.failures_path.exists() or self.successes_path.exists()
