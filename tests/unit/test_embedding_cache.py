"""Unit tests for EmbeddingCache."""

import numpy as np
import pytest

from src.memory.embedding_cache import EmbeddingCache


@pytest.fixture
def cache_dir(tmp_path):
    """Create temporary cache directory."""
    return tmp_path / "cache"


@pytest.fixture
def embedding_cache(cache_dir):
    """Create EmbeddingCache instance."""
    return EmbeddingCache(cache_dir)


def test_cache_initialization(embedding_cache, cache_dir):
    """Test cache initialization creates directory."""
    assert embedding_cache.cache_dir == cache_dir
    assert cache_dir.exists()


def test_save_and_load_embedding(embedding_cache):
    """Test saving and loading an embedding."""
    key = "test_key"
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    embedding_cache.save(key, embedding)
    loaded = embedding_cache.load(key)

    assert loaded is not None
    assert len(loaded) == len(embedding)
    np.testing.assert_array_almost_equal(embedding, loaded)


def test_load_nonexistent_embedding(embedding_cache):
    """Test loading non-existent embedding returns None."""
    loaded = embedding_cache.load("nonexistent_key")
    assert loaded is None


def test_exists_method(embedding_cache):
    """Test checking if embedding exists via exists()."""
    key = "test_key"
    embedding = [0.1, 0.2, 0.3]

    # Initially not present
    assert not embedding_cache.exists(key)

    # Save and check again
    embedding_cache.save(key, embedding)
    assert embedding_cache.exists(key)


def test_get_cache_path(embedding_cache):
    """Test that cache path is generated correctly."""
    key = "test_key"
    path = embedding_cache._get_cache_path(key)

    assert path.suffix == ".npy"
    assert path.parent == embedding_cache.cache_dir


def test_different_keys_different_paths(embedding_cache):
    """Test that different keys generate different paths."""
    path1 = embedding_cache._get_cache_path("key_1")
    path2 = embedding_cache._get_cache_path("key_2")

    assert path1 != path2


def test_save_multiple_embeddings(embedding_cache):
    """Test saving multiple embeddings."""
    keys = ["key_1", "key_2", "key_3"]
    embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

    for key, emb in zip(keys, embeddings):
        embedding_cache.save(key, emb)

    for key, expected_emb in zip(keys, embeddings):
        loaded = embedding_cache.load(key)
        assert loaded is not None
        np.testing.assert_array_almost_equal(expected_emb, loaded)


def test_overwrite_existing_embedding(embedding_cache):
    """Test overwriting an existing embedding."""
    key = "test_key"
    emb1 = [0.1, 0.2, 0.3]
    emb2 = [0.7, 0.8, 0.9]

    embedding_cache.save(key, emb1)
    embedding_cache.save(key, emb2)

    loaded = embedding_cache.load(key)
    np.testing.assert_array_almost_equal(emb2, loaded)


def test_clear_cache(embedding_cache):
    """Test clearing the cache."""
    for i in range(5):
        embedding_cache.save(f"key_{i}", [float(i), float(i + 1)])

    # Verify files exist
    assert embedding_cache.exists("key_0")

    # Clear cache
    embedding_cache.clear()

    # Verify all embeddings are gone
    for i in range(5):
        assert not embedding_cache.exists(f"key_{i}")


def test_cache_persistence(cache_dir):
    """Test that cache persists across instances."""
    key = "persistent_key"
    embedding = [0.1, 0.2, 0.3]

    cache1 = EmbeddingCache(cache_dir)
    cache1.save(key, embedding)

    cache2 = EmbeddingCache(cache_dir)
    loaded = cache2.load(key)

    assert loaded is not None
    np.testing.assert_array_almost_equal(embedding, loaded)


def test_unicode_text_key(embedding_cache):
    """Test handling of unicode text as key."""
    key = "测试_key_🚀"
    embedding = [0.1, 0.2, 0.3]

    embedding_cache.save(key, embedding)
    loaded = embedding_cache.load(key)

    assert loaded is not None
    np.testing.assert_array_almost_equal(embedding, loaded)


def test_special_characters_in_key(embedding_cache):
    """Test handling of special characters in key."""
    key = "test/with\\special_chars"
    embedding = [0.1, 0.2, 0.3]

    embedding_cache.save(key, embedding)
    loaded = embedding_cache.load(key)

    assert loaded is not None
    np.testing.assert_array_almost_equal(embedding, loaded)


def test_numpy_array_save_and_load(embedding_cache):
    """Test saving numpy array and loading as list."""
    key = "numpy_key"
    np_embedding = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

    embedding_cache.save(key, np_embedding.tolist())
    loaded = embedding_cache.load(key)

    assert loaded is not None
    assert isinstance(loaded, list)
    np.testing.assert_array_almost_equal(np_embedding, loaded)
