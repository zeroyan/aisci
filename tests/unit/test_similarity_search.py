"""Unit tests for SimilaritySearch."""

from unittest.mock import MagicMock, patch

import pytest

from src.memory.embedding_cache import EmbeddingCache
from src.memory.similarity_search import SimilaritySearch
from src.schemas.orchestrator import CriticFeedback, MemoryEntry, PlannerOutput


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer to avoid downloading models."""
    with patch("src.memory.similarity_search.SentenceTransformer") as mock:
        # Create a mock model that returns fake embeddings
        import numpy as np

        mock_model = MagicMock()
        # Return numpy array with correct shape (384 dimensions for all-MiniLM-L6-v2)
        mock_model.encode.return_value = np.random.rand(384)
        mock.return_value = mock_model
        yield mock


@pytest.fixture
def cache_dir(tmp_path):
    """Create temporary cache directory."""
    return tmp_path / "embeddings"


@pytest.fixture
def similarity_search(cache_dir, mock_sentence_transformer):
    """Create SimilaritySearch instance with cache and mocked model."""
    cache = EmbeddingCache(cache_dir)
    return SimilaritySearch(embedding_cache=cache)


@pytest.fixture
def sample_entries():
    """Create sample memory entries for testing."""
    entries = []
    texts = [
        ("ImportError: numpy not found", "Install numpy"),
        ("TypeError: expected int got str", "Check type conversion"),
        ("ImportError: pandas not found", "Install pandas"),
        ("ValueError: invalid value", "Validate input"),
    ]
    for i, (feedback, suggestion) in enumerate(texts):
        entry = MemoryEntry(
            iteration=i + 1,
            planner_output=PlannerOutput(
                reasoning=f"Attempt {i + 1}",
                tool_calls=[],
                expected_improvement="Fix error",
            ),
            execution_result={"status": "error"},
            critic_feedback=CriticFeedback(
                status="failed",
                feedback=feedback,
                suggestions=[suggestion],
                score=10.0,
            ),
        )
        entries.append(entry)
    return entries


def test_similarity_search_initialization(similarity_search):
    """Test similarity search initialization."""
    assert similarity_search.model is not None
    assert similarity_search.embedding_cache is not None


def test_similarity_search_no_cache(mock_sentence_transformer):
    """Test similarity search without cache."""
    search = SimilaritySearch()
    assert search._model is None  # Lazy loading - not loaded yet
    assert search.embedding_cache is None


def test_compute_embedding_returns_list(similarity_search):
    """Test that compute_embedding returns a list."""
    text = "This is a test sentence"
    embedding = similarity_search.compute_embedding(text)

    assert isinstance(embedding, list)
    assert len(embedding) == 384  # all-MiniLM-L6-v2 dimension
    assert all(isinstance(v, float) for v in embedding)


def test_compute_embedding_with_cache_key(similarity_search, cache_dir):
    """Test that embedding is cached when cache_key is provided."""
    text = "Test text for caching"
    cache_key = "test_cache_key"

    # First call - computes and caches
    emb1 = similarity_search.compute_embedding(text, cache_key=cache_key)

    # Verify cached
    assert similarity_search.embedding_cache.exists(cache_key)

    # Second call - loads from cache
    emb2 = similarity_search.compute_embedding(text, cache_key=cache_key)

    # Should be identical
    assert emb1 == emb2


def test_compute_embedding_consistency(similarity_search):
    """Test that same text produces same embedding."""
    text = "Consistent embedding test"
    emb1 = similarity_search.compute_embedding(text)
    emb2 = similarity_search.compute_embedding(text)

    assert emb1 == emb2


def test_find_similar_empty_entries(similarity_search):
    """Test finding similar with empty entries list."""
    results = similarity_search.find_similar("test query", [], top_k=3)
    assert results == []


def test_find_similar_returns_tuples(similarity_search, sample_entries):
    """Test that find_similar returns list of (entry, score) tuples."""
    results = similarity_search.find_similar(
        "ImportError module not found", sample_entries, top_k=2
    )

    assert isinstance(results, list)
    if results:
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2
        assert isinstance(results[0][0], MemoryEntry)
        assert isinstance(results[0][1], float)


def test_find_similar_respects_top_k(similarity_search, sample_entries):
    """Test that top_k parameter limits results."""
    results = similarity_search.find_similar(
        "error", sample_entries, top_k=2, threshold=0.0
    )
    assert len(results) <= 2


def test_find_similar_sorted_by_score(similarity_search, sample_entries):
    """Test that results are sorted by similarity score descending."""
    results = similarity_search.find_similar(
        "ImportError", sample_entries, top_k=4, threshold=0.0
    )

    if len(results) >= 2:
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]


def test_find_similar_threshold_filters(similarity_search, sample_entries):
    """Test that threshold filters out low-similarity results."""
    # High threshold - should return fewer results
    high_threshold_results = similarity_search.find_similar(
        "ImportError", sample_entries, top_k=10, threshold=0.99
    )

    # Low threshold - should return more results
    low_threshold_results = similarity_search.find_similar(
        "ImportError", sample_entries, top_k=10, threshold=0.0
    )

    assert len(high_threshold_results) <= len(low_threshold_results)


def test_find_similar_import_errors(similarity_search, sample_entries):
    """Test finding import-related errors."""
    results = similarity_search.find_similar(
        "ImportError: module not found", sample_entries, top_k=3, threshold=0.0
    )

    # Should find some results
    assert len(results) > 0

    # Top result should be import-related
    top_entry, top_score = results[0]
    assert "Import" in top_entry.critic_feedback.feedback


def test_entry_to_text_conversion(similarity_search):
    """Test that entry is converted to text correctly."""
    entry = MemoryEntry(
        iteration=1,
        planner_output=PlannerOutput(
            reasoning="Test reasoning",
            tool_calls=[],
            expected_improvement="Improve",
        ),
        execution_result={},
        critic_feedback=CriticFeedback(
            status="failed",
            feedback="Test feedback",
            suggestions=["Suggestion 1"],
            score=10.0,
        ),
    )

    text = similarity_search._entry_to_text(entry)

    assert "Test reasoning" in text
    assert "Test feedback" in text
    assert "failed" in text
    assert "Suggestion 1" in text


def test_cosine_similarity_batch(similarity_search):
    """Test cosine similarity batch computation."""
    query = [1.0, 0.0, 0.0]
    vectors = [
        [1.0, 0.0, 0.0],   # identical - similarity = 1.0
        [0.0, 1.0, 0.0],   # orthogonal - similarity = 0.0
        [0.707, 0.707, 0.0],  # 45 degrees - similarity ≈ 0.707
    ]

    similarities = similarity_search._cosine_similarity_batch(query, vectors)

    assert len(similarities) == 3
    assert abs(similarities[0] - 1.0) < 0.001
    assert abs(similarities[1] - 0.0) < 0.001
    assert abs(similarities[2] - 0.707) < 0.01
