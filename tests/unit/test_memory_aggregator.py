"""Unit tests for MemoryAggregator."""


import pytest

from src.memory.branch_memory import BranchMemory
from src.memory.memory_aggregator import MemoryAggregator
from src.schemas.orchestrator import CriticFeedback, MemoryEntry, PlannerOutput


def make_entry(iteration: int, status: str, score: float) -> MemoryEntry:
    """Helper to create a MemoryEntry."""
    return MemoryEntry(
        iteration=iteration,
        planner_output=PlannerOutput(
            reasoning=f"Reasoning {iteration}",
            tool_calls=[],
            expected_improvement="Improve",
        ),
        execution_result={"status": "executed"},
        critic_feedback=CriticFeedback(
            status=status,
            feedback=f"Feedback {iteration}",
            suggestions=[f"Suggestion {iteration}"],
            score=score,
        ),
    )


@pytest.fixture
def global_kb_path(tmp_path):
    """Create global knowledge base path."""
    return tmp_path / "global_kb"


@pytest.fixture
def aggregator(global_kb_path):
    """Create MemoryAggregator instance."""
    return MemoryAggregator(global_kb_path)


@pytest.fixture
def branch_dirs(tmp_path):
    """Create branch memory directories with test data."""
    dirs = []
    for i in range(3):
        branch_dir = tmp_path / f"branch_{i}" / "memory"
        mem = BranchMemory(branch_dir)

        # Add success and failure entries
        mem.record_attempt(make_entry(1, "success", 90.0))
        mem.record_attempt(make_entry(2, "failed", 10.0))

        dirs.append(branch_dir)
    return dirs


def test_aggregator_initialization(aggregator, global_kb_path):
    """Test aggregator initialization creates directory."""
    assert aggregator.global_kb_path == global_kb_path
    assert global_kb_path.exists()


def test_aggregate_from_branches_basic(aggregator, branch_dirs):
    """Test basic aggregation from multiple branches."""
    stats = aggregator.aggregate_from_branches(branch_dirs, run_id="run_001")

    assert stats["run_id"] == "run_001"
    assert stats["total_entries"] == 6   # 3 branches × 2 entries
    assert stats["failures"] == 3        # 3 branches × 1 failure
    assert stats["successes"] == 3       # 3 branches × 1 success
    assert stats["branches_processed"] == 3


def test_aggregate_from_empty_branches(aggregator, tmp_path):
    """Test aggregation from empty branch directories."""
    empty_dirs = [tmp_path / f"empty_{i}" / "memory" for i in range(3)]
    for d in empty_dirs:
        d.mkdir(parents=True)

    stats = aggregator.aggregate_from_branches(empty_dirs, run_id="run_empty")

    assert stats["total_entries"] == 0
    assert stats["failures"] == 0
    assert stats["successes"] == 0


def test_aggregate_from_single_branch(aggregator, tmp_path):
    """Test aggregation from a single branch."""
    branch_dir = tmp_path / "single_branch" / "memory"
    mem = BranchMemory(branch_dir)
    mem.record_attempt(make_entry(1, "success", 95.0))
    mem.record_attempt(make_entry(2, "success", 88.0))
    mem.record_attempt(make_entry(3, "failed", 15.0))

    stats = aggregator.aggregate_from_branches([branch_dir], run_id="run_single")

    assert stats["total_entries"] == 3
    assert stats["successes"] == 2
    assert stats["failures"] == 1
    assert stats["branches_processed"] == 1


def test_load_global_failures(aggregator, branch_dirs):
    """Test loading global failures after aggregation."""
    aggregator.aggregate_from_branches(branch_dirs, run_id="run_001")

    failures = aggregator.load_global_failures()
    assert len(failures) == 3  # 3 branches × 1 failure each


def test_load_global_successes(aggregator, branch_dirs):
    """Test loading global successes after aggregation."""
    aggregator.aggregate_from_branches(branch_dirs, run_id="run_001")

    successes = aggregator.load_global_successes()
    assert len(successes) == 3  # 3 branches × 1 success each


def test_get_global_statistics(aggregator, branch_dirs):
    """Test getting global statistics after aggregation."""
    aggregator.aggregate_from_branches(branch_dirs, run_id="run_001")

    stats = aggregator.get_global_statistics()

    assert stats["total_attempts"] == 6
    assert stats["failures"] == 3
    assert stats["successes"] == 3


def test_get_global_statistics_empty(aggregator):
    """Test getting global statistics when empty."""
    stats = aggregator.get_global_statistics()

    assert stats["total_attempts"] == 0
    assert stats["failures"] == 0
    assert stats["successes"] == 0


def test_aggregate_multiple_runs(aggregator, tmp_path):
    """Test aggregating from multiple runs (cumulative)."""
    # First run
    branch1 = tmp_path / "run1_branch" / "memory"
    mem1 = BranchMemory(branch1)
    mem1.record_attempt(make_entry(1, "success", 90.0))
    aggregator.aggregate_from_branches([branch1], run_id="run_001")

    # Second run
    branch2 = tmp_path / "run2_branch" / "memory"
    mem2 = BranchMemory(branch2)
    mem2.record_attempt(make_entry(1, "failed", 20.0))
    aggregator.aggregate_from_branches([branch2], run_id="run_002")

    # Global KB should have entries from both runs
    stats = aggregator.get_global_statistics()
    assert stats["total_attempts"] == 2
    assert stats["successes"] == 1
    assert stats["failures"] == 1


def test_aggregate_needs_improvement_not_categorized(aggregator, tmp_path):
    """Test that needs_improvement entries are not in failures or successes."""
    branch_dir = tmp_path / "branch" / "memory"
    mem = BranchMemory(branch_dir)
    mem.record_attempt(make_entry(1, "needs_improvement", 50.0))
    mem.record_attempt(make_entry(2, "success", 90.0))

    stats = aggregator.aggregate_from_branches([branch_dir], run_id="run_001")

    assert stats["total_entries"] == 2
    assert stats["successes"] == 1
    assert stats["failures"] == 0  # needs_improvement not counted as failure


def test_aggregate_preserves_entry_data(aggregator, tmp_path):
    """Test that aggregation preserves entry data correctly."""
    branch_dir = tmp_path / "branch" / "memory"
    mem = BranchMemory(branch_dir)
    entry = make_entry(5, "success", 95.0)
    mem.record_attempt(entry)

    aggregator.aggregate_from_branches([branch_dir], run_id="run_001")

    successes = aggregator.load_global_successes()
    assert len(successes) == 1
    assert successes[0].iteration == 5
    assert successes[0].critic_feedback.score == 95.0
    assert successes[0].critic_feedback.status == "success"
