"""Unit tests for ExperimentMemory."""

from unittest.mock import patch

import pytest

from src.memory.experiment_memory import ExperimentMemory
from src.schemas.orchestrator import CriticFeedback, MemoryEntry, PlannerOutput


@pytest.fixture
def mock_sentence_transformer():
    """Mock SentenceTransformer to avoid downloading models."""
    with patch("src.memory.similarity_search.SentenceTransformer") as mock:
        import numpy as np

        mock_model = mock.return_value
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        yield mock


@pytest.fixture
def memory_dir(tmp_path):
    """Create temporary memory directory."""
    return tmp_path / "memory"


@pytest.fixture
def experiment_memory(memory_dir, mock_sentence_transformer):
    """Create ExperimentMemory instance with mocked model."""
    return ExperimentMemory(memory_dir)


@pytest.fixture
def sample_memory_entry():
    """Create sample memory entry."""
    return MemoryEntry(
        iteration=1,
        planner_output=PlannerOutput(
            reasoning="Test reasoning",
            tool_calls=[{"tool": "write_file", "args": {"path": "test.py"}}],
            expected_improvement="Better code",
        ),
        execution_result={"status": "executed", "output": "Success"},
        critic_feedback=CriticFeedback(
            status="success",
            feedback="Good result",
            suggestions=[],
            score=90.0,
        ),
    )


def test_memory_initialization(experiment_memory, memory_dir):
    """Test memory initialization creates directories."""
    assert experiment_memory.memory_dir == memory_dir
    assert experiment_memory.memory_dir.exists()
    # Files are created on first write, not on init
    assert not experiment_memory.attempts_path.exists()


def test_record_attempt_success(experiment_memory, sample_memory_entry):
    """Test recording a successful attempt."""
    experiment_memory.record_attempt(sample_memory_entry)

    # Verify written to attempts
    attempts = experiment_memory.load_attempts()
    assert len(attempts) == 1
    assert attempts[0].iteration == 1
    assert attempts[0].critic_feedback.status == "success"

    # Verify written to successes
    successes = experiment_memory.load_successes()
    assert len(successes) == 1

    # Verify NOT written to failures
    failures = experiment_memory.load_failures()
    assert len(failures) == 0


def test_record_attempt_failure(experiment_memory):
    """Test recording a failed attempt."""
    failed_entry = MemoryEntry(
        iteration=2,
        planner_output=PlannerOutput(
            reasoning="Failed reasoning",
            tool_calls=[{"tool": "write_file", "args": {}}],
            expected_improvement="Fix error",
        ),
        execution_result={"status": "error", "output": "Error occurred"},
        critic_feedback=CriticFeedback(
            status="failed",
            feedback="Failed",
            suggestions=["Try again"],
            score=10.0,
        ),
    )

    experiment_memory.record_attempt(failed_entry)

    # Verify written to failures
    failures = experiment_memory.load_failures()
    assert len(failures) == 1
    assert failures[0].critic_feedback.status == "failed"


def test_find_similar_failures_empty(experiment_memory):
    """Test finding similar failures when memory is empty."""
    similar = experiment_memory.find_similar_failures("test query", top_k=3)
    assert similar == []


def test_find_similar_failures_with_data(experiment_memory):
    """Test finding similar failures with data."""
    # Record some failures
    for i in range(3):
        entry = MemoryEntry(
            iteration=i + 1,
            planner_output=PlannerOutput(
                reasoning=f"Reasoning {i}",
                tool_calls=[],
                expected_improvement=f"Improvement {i}",
            ),
            execution_result={"status": "error"},
            critic_feedback=CriticFeedback(
                status="failed",
                feedback=f"Feedback {i}",
                suggestions=[],
                score=10.0,
            ),
        )
        experiment_memory.record_attempt(entry)

    # Search for similar failures
    similar = experiment_memory.find_similar_failures("Reasoning 1", top_k=2)

    # Should return list of tuples (entry, score)
    assert isinstance(similar, list)
    assert len(similar) <= 2
    if similar:
        assert isinstance(similar[0], tuple)
        assert isinstance(similar[0][0], MemoryEntry)
        assert isinstance(similar[0][1], float)


def test_get_statistics_empty(experiment_memory):
    """Test getting statistics when empty."""
    stats = experiment_memory.get_statistics()

    assert stats["total_attempts"] == 0
    assert stats["failures"] == 0
    assert stats["successes"] == 0


def test_get_statistics_with_data(experiment_memory, sample_memory_entry):
    """Test getting statistics with data."""
    # Record success
    experiment_memory.record_attempt(sample_memory_entry)

    # Record failure
    failed_entry = sample_memory_entry.model_copy(
        update={
            "iteration": 2,
            "critic_feedback": CriticFeedback(
                status="failed", feedback="Failed", suggestions=[], score=10.0
            ),
        }
    )
    experiment_memory.record_attempt(failed_entry)

    # Get statistics
    stats = experiment_memory.get_statistics()

    assert stats["total_attempts"] == 2
    assert stats["failures"] == 1
    assert stats["successes"] == 1


def test_load_attempts_preserves_order(experiment_memory):
    """Test that loading attempts preserves insertion order."""
    # Record multiple attempts
    for i in range(5):
        entry = MemoryEntry(
            iteration=i + 1,
            planner_output=PlannerOutput(
                reasoning=f"Reasoning {i}",
                tool_calls=[],
                expected_improvement="Improvement",
            ),
            execution_result={},
            critic_feedback=CriticFeedback(
                status="success", feedback="Good", suggestions=[], score=90.0
            ),
        )
        experiment_memory.record_attempt(entry)

    # Load and verify order
    attempts = experiment_memory.load_attempts()
    assert len(attempts) == 5
    for i, attempt in enumerate(attempts):
        assert attempt.iteration == i + 1


def test_memory_persistence(memory_dir):
    """Test that memory persists across instances."""
    # Create first instance and record
    memory1 = ExperimentMemory(memory_dir)
    entry = MemoryEntry(
        iteration=1,
        planner_output=PlannerOutput(
            reasoning="Test", tool_calls=[], expected_improvement="Improve"
        ),
        execution_result={},
        critic_feedback=CriticFeedback(
            status="success", feedback="Good", suggestions=[], score=90.0
        ),
    )
    memory1.record_attempt(entry)

    # Create second instance and verify data persists
    memory2 = ExperimentMemory(memory_dir)
    attempts = memory2.load_attempts()
    assert len(attempts) == 1
    assert attempts[0].iteration == 1


def test_find_similar_successes(experiment_memory):
    """Test finding similar successful attempts."""
    # Record some successes
    for i in range(3):
        entry = MemoryEntry(
            iteration=i + 1,
            planner_output=PlannerOutput(
                reasoning=f"Success reasoning {i}",
                tool_calls=[],
                expected_improvement="Improve",
            ),
            execution_result={},
            critic_feedback=CriticFeedback(
                status="success",
                feedback=f"Success feedback {i}",
                suggestions=[],
                score=90.0,
            ),
        )
        experiment_memory.record_attempt(entry)

    # Search for similar successes
    similar = experiment_memory.find_similar_successes("Success reasoning 1", top_k=2)

    assert isinstance(similar, list)
    assert len(similar) <= 2
