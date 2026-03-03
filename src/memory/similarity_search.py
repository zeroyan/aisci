"""Semantic similarity search for memory retrieval."""

import numpy as np
from sentence_transformers import SentenceTransformer

from src.memory.embedding_cache import EmbeddingCache
from src.schemas.orchestrator import MemoryEntry


class SimilaritySearch:
    """Search for similar memory entries using semantic similarity."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        embedding_cache: EmbeddingCache | None = None,
    ) -> None:
        """Initialize similarity search.

        Args:
            model_name: Name of sentence-transformers model
            embedding_cache: Optional embedding cache
        """
        self.model_name = model_name
        self._model = None  # Lazy load
        self.embedding_cache = embedding_cache

    @property
    def model(self) -> SentenceTransformer:
        """Get model, loading it lazily on first access."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def compute_embedding(self, text: str, cache_key: str | None = None) -> list[float]:
        """Compute embedding for text.

        Args:
            text: Text to embed
            cache_key: Optional cache key for storing embedding

        Returns:
            Embedding vector
        """
        # Check cache first
        if cache_key and self.embedding_cache:
            cached = self.embedding_cache.load(cache_key)
            if cached is not None:
                return cached

        # Compute embedding
        embedding = self.model.encode(text).tolist()

        # Cache if key provided
        if cache_key and self.embedding_cache:
            self.embedding_cache.save(cache_key, embedding)

        return embedding

    def find_similar(
        self,
        query_text: str,
        entries: list[MemoryEntry],
        top_k: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[MemoryEntry, float]]:
        """Find similar memory entries.

        Args:
            query_text: Query text
            entries: List of memory entries to search
            top_k: Number of top results to return
            threshold: Minimum similarity threshold (0-1)

        Returns:
            List of (entry, similarity_score) tuples, sorted by score descending
        """
        if not entries:
            return []

        # Compute query embedding
        query_embedding = self.compute_embedding(query_text)

        # Compute embeddings for all entries
        entry_embeddings = []
        for entry in entries:
            # Create text representation of entry
            entry_text = self._entry_to_text(entry)
            # Use unique cache key with timestamp and iteration to avoid conflicts
            timestamp_str = entry.timestamp.isoformat().replace(":", "-").replace(".", "-")
            cache_key = f"entry_{timestamp_str}_{entry.iteration}"
            embedding = self.compute_embedding(entry_text, cache_key)
            entry_embeddings.append(embedding)

        # Compute cosine similarities
        similarities = self._cosine_similarity_batch(query_embedding, entry_embeddings)

        # Filter by threshold and sort
        results = []
        for entry, similarity in zip(entries, similarities):
            if similarity >= threshold:
                results.append((entry, similarity))

        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def _entry_to_text(self, entry: MemoryEntry) -> str:
        """Convert memory entry to text for embedding.

        Args:
            entry: Memory entry

        Returns:
            Text representation
        """
        parts = [
            f"Reasoning: {entry.planner_output.reasoning}",
            f"Feedback: {entry.critic_feedback.feedback}",
            f"Status: {entry.critic_feedback.status}",
        ]

        if entry.critic_feedback.suggestions:
            parts.append(f"Suggestions: {', '.join(entry.critic_feedback.suggestions)}")

        return " | ".join(parts)

    def _cosine_similarity_batch(
        self, query: list[float], vectors: list[list[float]]
    ) -> list[float]:
        """Compute cosine similarity between query and multiple vectors.

        Args:
            query: Query vector
            vectors: List of vectors

        Returns:
            List of similarity scores
        """
        query_np = np.array(query)
        vectors_np = np.array(vectors)

        # Normalize
        query_norm = query_np / np.linalg.norm(query_np)
        vectors_norm = vectors_np / np.linalg.norm(vectors_np, axis=1, keepdims=True)

        # Compute dot product
        similarities = np.dot(vectors_norm, query_norm)

        return similarities.tolist()
