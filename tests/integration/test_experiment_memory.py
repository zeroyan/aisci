"""Integration tests for Experiment Memory system."""

from unittest.mock import patch

import pytest

from src.memory.experiment_memory import ExperimentMemory
from src.memory.memory_aggregator import MemoryAggregator
from src.memory.branch_memory import BranchMemory
from src.schemas.orchestrator import CriticFeedback, MemoryEntry, PlannerOutput


@pytest.fixture(autouse=True)
def mock_sentence_transformer():
    """Mock SentenceTransformer for all tests in this module."""
    with patch("src.memory.similarity_search.SentenceTransformer") as mock:
        import numpy as np

        mock_model = mock.return_value
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        yield mock


def make_entry(iteration: int, status: str, score: float, reasoning: str = "") -> MemoryEntry:
    """Helper to create a MemoryEntry."""
    return MemoryEntry(
        iteration=iteration,
        planner_output=PlannerOutput(
            reasoning=reasoning or f"Reasoning {iteration}",
            tool_calls=[{"tool": "write_file", "args": {"path": "test.py"}}],
            expected_improvement="Improve",
        ),
        execution_result={"status": "executed" if status != "failed" else "error"},
        critic_feedback=CriticFeedback(
            status=status,
            feedback=f"Feedback for iteration {iteration}",
            suggestions=[f"Suggestion {iteration}"],
            score=score,
        ),
    )


@pytest.fixture
def memory_dir(tmp_path):
    """Create temporary memory directory."""
    return tmp_path / "experiment_memory"


@pytest.fixture
def experiment_memory(memory_dir):
    """Create ExperimentMemory instance."""
    return ExperimentMemory(memory_dir)


def test_end_to_end_memory_workflow(experiment_memory):
    """Test complete memory workflow: record, retrieve, aggregate."""
    # Step 1: Record multiple attempts with different outcomes
    experiment_memory.record_attempt(make_entry(1, "success", 95.0, "Implement feature X"))
    experiment_memory.record_attempt(make_entry(2, "failed", 15.0, "ImportError in module"))
    experiment_memory.record_attempt(make_entry(3, "failed", 20.0, "ImportError different module"))
    experiment_memory.record_attempt(make_entry(4, "success", 98.0, "Fixed all imports"))

    # Step 2: Verify recording
    all_attempts = experiment_memory.load_attempts()
    assert len(all_attempts) == 4

    successes = experiment_memory.load_successes()
    assert len(successes) == 2

    failures = experiment_memory.load_failures()
    assert len(failures) == 2

    # Step 3: Test similarity search for failures
    similar_failures = experiment_memory.find_similar_failures(
        "ImportError in module", top_k=2
    )
    assert isinstance(similar_failures, list)
    # Returns list of (entry, score) tuples
    if similar_failures:
        assert isinstance(similar_failures[0], tuple)

    # Step 4: Get statistics
    stats = experiment_memory.get_statistics()
    assert stats["total_attempts"] == 4
    assert stats["successes"] == 2
    assert stats["failures"] == 2


def test_memory_persistence_across_sessions(memory_dir):
    """Test that memory persists across different sessions."""
    # Session 1: Record some attempts
    memory1 = ExperimentMemory(memory_dir)
    memory1.record_attempt(make_entry(1, "success", 90.0))

    # Session 2: Load and add more
    memory2 = ExperimentMemory(memory_dir)
    attempts = memory2.load_attempts()
    assert len(attempts) == 1

    memory2.record_attempt(make_entry(2, "failed", 10.0))

    # Session 3: Verify all data
    memory3 = ExperimentMemory(memory_dir)
    all_attempts = memory3.load_attempts()
    assert len(all_attempts) == 2
    assert all_attempts[0].iteration == 1
    assert all_attempts[1].iteration == 2


def test_similarity_search_with_real_queries(experiment_memory):
    """Test similarity search with realistic queries."""
    errors = [
        ("ImportError: numpy not found", "Install numpy package"),
        ("TypeError: expected int, got str", "Check type conversion"),
        ("ImportError: pandas not found", "Install pandas package"),
        ("ValueError: invalid value", "Validate input"),
        ("ImportError: sklearn not found", "Install scikit-learn"),
    ]

    for i, (feedback, suggestion) in enumerate(errors):
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
        experiment_memory.record_attempt(entry)

    # Search for import-related errors
    import_failures = experiment_memory.find_similar_failures(
        "ImportError: module not found", top_k=3
    )
    assert len(import_failures) <= 3

    # Search for type-related errors
    type_failures = experiment_memory.find_similar_failures(
        "TypeError: wrong type", top_k=2
    )
    assert len(type_failures) <= 2


def test_memory_aggregation_workflow(tmp_path):
    """Test aggregating branch memories into global KB."""
    # Create branch memories
    branch_dirs = []
    for i in range(3):
        branch_dir = tmp_path / f"branch_{i}" / "memory"
        mem = BranchMemory(branch_dir)
        mem.record_attempt(make_entry(1, "success", 90.0))
        mem.record_attempt(make_entry(2, "failed", 10.0))
        branch_dirs.append(branch_dir)

    # Aggregate into global KB
    global_kb = tmp_path / "global_kb"
    aggregator = MemoryAggregator(global_kb)
    stats = aggregator.aggregate_from_branches(branch_dirs, run_id="run_001")

    assert stats["total_entries"] == 6
    assert stats["successes"] == 3
    assert stats["failures"] == 3
    assert stats["branches_processed"] == 3

    # Verify global KB
    global_stats = aggregator.get_global_statistics()
    assert global_stats["total_attempts"] == 6
    assert global_stats["successes"] == 3
    assert global_stats["failures"] == 3


def test_empty_memory_operations(experiment_memory):
    """Test operations on empty memory."""
    assert experiment_memory.load_attempts() == []
    assert experiment_memory.load_successes() == []
    assert experiment_memory.load_failures() == []

    similar = experiment_memory.find_similar_failures("test query", top_k=3)
    assert similar == []

    stats = experiment_memory.get_statistics()
    assert stats["total_attempts"] == 0
    assert stats["failures"] == 0
    assert stats["successes"] == 0


def test_find_similar_returns_sorted_results(experiment_memory):
    """Test that find_similar returns results sorted by score."""
    for i in range(5):
        entry = MemoryEntry(
            iteration=i + 1,
            planner_output=PlannerOutput(
                reasoning=f"Python error {i}",
                tool_calls=[],
                expected_improvement="Fix",
            ),
            execution_result={},
            critic_feedback=CriticFeedback(
                status="failed",
                feedback=f"Error type {i}",
                suggestions=["Fix it"],
                score=10.0,
            ),
        )
        experiment_memory.record_attempt(entry)

    results = experiment_memory.find_similar_failures("Python error", top_k=3, threshold=0.0)

    if len(results) >= 2:
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]
