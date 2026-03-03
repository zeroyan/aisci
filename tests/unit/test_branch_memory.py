"""Unit tests for BranchMemory."""


import pytest

from src.memory.branch_memory import BranchMemory
from src.schemas.orchestrator import CriticFeedback, MemoryEntry, PlannerOutput


@pytest.fixture
def branch_memory(tmp_path):
    """Create branch memory instance."""
    return BranchMemory(tmp_path / "memory")


@pytest.fixture
def test_memory_entry():
    """Create test memory entry."""
    return MemoryEntry(
        iteration=1,
        planner_output=PlannerOutput(
            reasoning="Test reasoning",
            tool_calls=[{"tool": "write_file", "args": {}}],
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


def test_branch_memory_initialization(branch_memory):
    """Test branch memory initialization."""
    assert branch_memory.memory_dir.exists()
    assert branch_memory.attempts_path.name == "attempts.jsonl"
    assert branch_memory.failures_path.name == "failures.jsonl"
    assert branch_memory.successes_path.name == "successes.jsonl"


def test_record_success_attempt(branch_memory, test_memory_entry):
    """Test recording a successful attempt."""
    branch_memory.record_attempt(test_memory_entry)

    # Verify written to attempts.jsonl
    assert branch_memory.attempts_path.exists()
    attempts = branch_memory.load_attempts()
    assert len(attempts) == 1
    assert attempts[0].iteration == 1
    assert attempts[0].critic_feedback.status == "success"

    # Verify written to successes.jsonl
    assert branch_memory.successes_path.exists()
    successes = branch_memory.load_successes()
    assert len(successes) == 1
    assert successes[0].iteration == 1

    # Verify NOT written to failures.jsonl
    failures = branch_memory.load_failures()
    assert len(failures) == 0


def test_record_failed_attempt(branch_memory):
    """Test recording a failed attempt."""
    failed_entry = MemoryEntry(
        iteration=2,
        planner_output=PlannerOutput(
            reasoning="Failed reasoning",
            tool_calls=[{"tool": "write_file", "args": {}}],
            expected_improvement="Try to fix",
        ),
        execution_result={"status": "error", "output": "Error occurred"},
        critic_feedback=CriticFeedback(
            status="failed",
            feedback="Failed",
            suggestions=["Try again"],
            score=10.0,
        ),
    )

    branch_memory.record_attempt(failed_entry)

    # Verify written to attempts.jsonl
    attempts = branch_memory.load_attempts()
    assert len(attempts) == 1
    assert attempts[0].iteration == 2

    # Verify written to failures.jsonl
    failures = branch_memory.load_failures()
    assert len(failures) == 1
    assert failures[0].iteration == 2
    assert failures[0].critic_feedback.status == "failed"

    # Verify NOT written to successes.jsonl
    successes = branch_memory.load_successes()
    assert len(successes) == 0


def test_record_needs_improvement_attempt(branch_memory):
    """Test recording a needs_improvement attempt."""
    needs_improvement_entry = MemoryEntry(
        iteration=3,
        planner_output=PlannerOutput(
            reasoning="Needs improvement reasoning",
            tool_calls=[{"tool": "write_file", "args": {}}],
            expected_improvement="Can be better",
        ),
        execution_result={"status": "executed", "output": "OK"},
        critic_feedback=CriticFeedback(
            status="needs_improvement",
            feedback="Needs work",
            suggestions=["Improve"],
            score=50.0,
        ),
    )

    branch_memory.record_attempt(needs_improvement_entry)

    # Verify written to attempts.jsonl
    attempts = branch_memory.load_attempts()
    assert len(attempts) == 1
    assert attempts[0].iteration == 3

    # Verify NOT written to failures or successes
    failures = branch_memory.load_failures()
    successes = branch_memory.load_successes()
    assert len(failures) == 0
    assert len(successes) == 0


def test_load_attempts_empty(branch_memory):
    """Test loading attempts from empty memory."""
    attempts = branch_memory.load_attempts()
    assert attempts == []


def test_load_multiple_attempts(branch_memory, test_memory_entry):
    """Test loading multiple attempts."""
    # Record multiple attempts
    for i in range(3):
        entry = test_memory_entry.model_copy(update={"iteration": i + 1})
        branch_memory.record_attempt(entry)

    # Load
    attempts = branch_memory.load_attempts()

    # Verify
    assert len(attempts) == 3
    assert attempts[0].iteration == 1
    assert attempts[1].iteration == 2
    assert attempts[2].iteration == 3


def test_get_entry_count(branch_memory, test_memory_entry):
    """Test getting entry counts."""
    # Initially empty
    counts = branch_memory.get_entry_count()
    assert counts["attempts"] == 0
    assert counts["failures"] == 0
    assert counts["successes"] == 0

    # Record some entries
    branch_memory.record_attempt(test_memory_entry)

    failed_entry = test_memory_entry.model_copy(
        update={
            "iteration": 2,
            "critic_feedback": CriticFeedback(
                status="failed", score=10.0, feedback="Failed", suggestions=[]
            ),
        }
    )
    branch_memory.record_attempt(failed_entry)

    # Check counts
    counts = branch_memory.get_entry_count()
    assert counts["attempts"] == 2
    assert counts["failures"] == 1
    assert counts["successes"] == 1
