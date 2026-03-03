"""Unit tests for KnowledgeBase."""

import json

import pytest

from src.memory.knowledge_base import KnowledgeBase


@pytest.fixture
def knowledge_base(tmp_path):
    """Create knowledge base instance."""
    return KnowledgeBase(tmp_path / "knowledge")


def test_knowledge_base_initialization(knowledge_base):
    """Test knowledge base initialization."""
    assert knowledge_base.knowledge_dir.exists()
    assert knowledge_base.failures_path.name == "failures.jsonl"
    assert knowledge_base.successes_path.name == "successes.jsonl"
    assert knowledge_base.embeddings_path.name == "embeddings.npy"


def test_load_failures_empty(knowledge_base):
    """Test loading failures from empty knowledge base."""
    failures = knowledge_base.load_failures()
    assert failures == []


def test_load_successes_empty(knowledge_base):
    """Test loading successes from empty knowledge base."""
    successes = knowledge_base.load_successes()
    assert successes == []


def test_load_failures_with_data(knowledge_base):
    """Test loading failures with data."""
    # Write test data
    test_failures = [
        {"entry_id": "f1", "error": "Test error 1"},
        {"entry_id": "f2", "error": "Test error 2"},
    ]

    with open(knowledge_base.failures_path, "w") as f:
        for failure in test_failures:
            f.write(json.dumps(failure) + "\n")

    # Load
    failures = knowledge_base.load_failures()

    # Verify
    assert len(failures) == 2
    assert failures[0]["entry_id"] == "f1"
    assert failures[1]["entry_id"] == "f2"


def test_load_successes_with_data(knowledge_base):
    """Test loading successes with data."""
    # Write test data
    test_successes = [
        {"entry_id": "s1", "result": "Test result 1"},
        {"entry_id": "s2", "result": "Test result 2"},
    ]

    with open(knowledge_base.successes_path, "w") as f:
        for success in test_successes:
            f.write(json.dumps(success) + "\n")

    # Load
    successes = knowledge_base.load_successes()

    # Verify
    assert len(successes) == 2
    assert successes[0]["entry_id"] == "s1"
    assert successes[1]["entry_id"] == "s2"


def test_get_all_entries(knowledge_base):
    """Test getting all entries."""
    # Write test data
    test_failures = [{"entry_id": "f1", "type": "failure"}]
    test_successes = [{"entry_id": "s1", "type": "success"}]

    with open(knowledge_base.failures_path, "w") as f:
        for failure in test_failures:
            f.write(json.dumps(failure) + "\n")

    with open(knowledge_base.successes_path, "w") as f:
        for success in test_successes:
            f.write(json.dumps(success) + "\n")

    # Get all entries
    all_entries = knowledge_base.get_all_entries()

    # Verify
    assert len(all_entries) == 2
    assert any(e["entry_id"] == "f1" for e in all_entries)
    assert any(e["entry_id"] == "s1" for e in all_entries)


def test_exists_empty(knowledge_base):
    """Test exists() on empty knowledge base."""
    assert not knowledge_base.exists()


def test_exists_with_failures(knowledge_base):
    """Test exists() with failures."""
    knowledge_base.failures_path.write_text('{"test": "data"}\n')
    assert knowledge_base.exists()


def test_exists_with_successes(knowledge_base):
    """Test exists() with successes."""
    knowledge_base.successes_path.write_text('{"test": "data"}\n')
    assert knowledge_base.exists()


def test_read_only_behavior(knowledge_base):
    """Test that knowledge base is read-only (no write methods)."""
    # Verify no write methods exist
    assert not hasattr(knowledge_base, "write_failure")
    assert not hasattr(knowledge_base, "write_success")
    assert not hasattr(knowledge_base, "append")
