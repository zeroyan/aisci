"""Unit tests for BudgetScheduler."""

import pytest

from src.scheduler.budget_scheduler import BudgetScheduler


@pytest.fixture
def total_budget():
    """Create test budget."""
    return {
        "max_cost_usd": 30.0,
        "max_time_hours": 3.0,
        "max_iterations": 15,
    }


def test_scheduler_initialization(total_budget):
    """Test scheduler initialization."""
    scheduler = BudgetScheduler(total_budget)

    assert scheduler.total_budget == total_budget
    assert scheduler.resource_tracker is not None
    assert scheduler.allocation_strategy is not None
    assert scheduler.early_stop_strategy is not None


def test_record_usage(total_budget):
    """Test recording resource usage."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.record_usage("branch_1", tokens=1000, cost_usd=0.5, time_seconds=10, iterations=1)

    usage = scheduler.get_usage("branch_1")
    assert usage.tokens_used == 1000
    assert usage.cost_usd == 0.5
    assert usage.time_seconds == 10
    assert usage.iterations == 1


def test_update_score(total_budget):
    """Test updating branch scores."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 75.0)
    scheduler.update_score("branch_2", 85.0)

    assert scheduler.branch_scores["branch_1"] == 75.0
    assert scheduler.branch_scores["branch_2"] == 85.0


def test_record_failure(total_budget):
    """Test recording failures."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.record_failure("branch_1")
    scheduler.record_failure("branch_1")

    assert scheduler.failure_counts["branch_1"] == 2


def test_record_success_resets_failures(total_budget):
    """Test that success resets failure count."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.record_failure("branch_1")
    scheduler.record_failure("branch_1")
    scheduler.record_success("branch_1")

    assert scheduler.failure_counts["branch_1"] == 0


def test_allocate_budget_equal_scores(total_budget):
    """Test budget allocation with equal scores."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 50.0)
    scheduler.update_score("branch_2", 50.0)
    scheduler.update_score("branch_3", 50.0)

    allocation = scheduler.allocate_budget()

    # With equal scores, allocation should be roughly equal
    assert len(allocation) == 3
    for branch_id, budget in allocation.items():
        assert budget["max_cost_usd"] > 0
        assert budget["max_time_hours"] > 0
        assert budget["max_iterations"] > 0


def test_allocate_budget_performance_based(total_budget):
    """Test budget allocation favors better performers."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 90.0)  # Best performer
    scheduler.update_score("branch_2", 50.0)  # Medium
    scheduler.update_score("branch_3", 30.0)  # Worst

    allocation = scheduler.allocate_budget()

    # Best performer should get more budget
    assert allocation["branch_1"]["max_cost_usd"] > allocation["branch_2"]["max_cost_usd"]
    assert allocation["branch_2"]["max_cost_usd"] > allocation["branch_3"]["max_cost_usd"]


def test_should_stop_branch_consecutive_failures(total_budget):
    """Test early stop on consecutive failures."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 50.0)
    scheduler.record_failure("branch_1")
    scheduler.record_failure("branch_1")

    should_stop, reason = scheduler.should_stop_branch("branch_1")

    assert should_stop
    assert "consecutive failures" in reason.lower()


def test_should_stop_branch_budget_exceeded(total_budget):
    """Test early stop when budget exceeded."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 50.0)
    # Exceed cost budget
    scheduler.record_usage("branch_1", cost_usd=35.0)

    should_stop, reason = scheduler.should_stop_branch("branch_1")

    assert should_stop
    assert "cost" in reason.lower()


def test_should_not_stop_within_budget(total_budget):
    """Test no early stop when within budget."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 50.0)
    scheduler.record_usage("branch_1", cost_usd=5.0, time_seconds=300, iterations=2)

    should_stop, reason = scheduler.should_stop_branch("branch_1")

    assert not should_stop
    assert reason == ""


def test_get_total_usage(total_budget):
    """Test getting total usage across branches."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.record_usage("branch_1", cost_usd=5.0, time_seconds=100, iterations=2)
    scheduler.record_usage("branch_2", cost_usd=3.0, time_seconds=50, iterations=1)

    total = scheduler.get_total_usage()

    assert total.cost_usd == 8.0
    assert total.time_seconds == 150
    assert total.iterations == 3


def test_get_remaining_budget(total_budget):
    """Test getting remaining budget."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.record_usage("branch_1", cost_usd=10.0, time_seconds=3600, iterations=5)

    remaining = scheduler.get_remaining_budget()

    assert remaining["max_cost_usd"] == 20.0
    assert remaining["max_time_hours"] == 2.0
    assert remaining["max_iterations"] == 10
