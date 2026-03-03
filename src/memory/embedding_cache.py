"""Embedding cache for storing and loading embeddings."""

import numpy as np
from pathlib import Path


class EmbeddingCache:
    """Cache embeddings to disk for faster retrieval."""

    def __init__(self, cache_dir: Path) -> None:
        """Initialize embedding cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, embedding: list[float]) -> None:
        """Save embedding to cache.

        Args:
            key: Cache key (e.g., entry_id)
            embedding: Embedding vector
        """
        cache_path = self._get_cache_path(key)
        np.save(cache_path, np.array(embedding))

    def load(self, key: str) -> list[float] | None:
        """Load embedding from cache.

        Args:
            key: Cache key

        Returns:
            Embedding vector if found, None otherwise
        """
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None

        embedding = np.load(cache_path)
        return embedding.tolist()

    def exists(self, key: str) -> bool:
        """Check if embedding exists in cache.

        Args:
            key: Cache key

        Returns:
            True if cached, False otherwise
        """
        return self._get_cache_path(key).exists()

    def clear(self) -> None:
        """Clear all cached embeddings."""
        for cache_file in self.cache_dir.glob("*.npy"):
            cache_file.unlink()

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Sanitize key for filename
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_key}.npy"
