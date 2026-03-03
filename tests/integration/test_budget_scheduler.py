"""Integration tests for Budget Scheduler."""

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


def test_full_budget_lifecycle(total_budget):
    """Test complete budget management lifecycle.

    Simulates:
    1. Initialize 3 branches
    2. Record usage and scores
    3. Allocate budget dynamically
    4. Detect early stop conditions
    """
    scheduler = BudgetScheduler(total_budget)

    # Initialize 3 branches with scores
    scheduler.update_score("branch_1", 50.0)
    scheduler.update_score("branch_2", 50.0)
    scheduler.update_score("branch_3", 50.0)

    # Initial allocation should be equal
    allocation = scheduler.allocate_budget()
    assert len(allocation) == 3

    # Simulate iteration 1: branch_1 performs well
    scheduler.record_usage("branch_1", cost_usd=2.0, time_seconds=100, iterations=1)
    scheduler.update_score("branch_1", 80.0)

    scheduler.record_usage("branch_2", cost_usd=2.0, time_seconds=100, iterations=1)
    scheduler.update_score("branch_2", 60.0)

    scheduler.record_usage("branch_3", cost_usd=2.0, time_seconds=100, iterations=1)
    scheduler.update_score("branch_3", 40.0)

    # Reallocation should favor branch_1
    allocation = scheduler.allocate_budget()
    assert allocation["branch_1"]["max_cost_usd"] > allocation["branch_2"]["max_cost_usd"]
    assert allocation["branch_2"]["max_cost_usd"] > allocation["branch_3"]["max_cost_usd"]

    # Simulate iteration 2: branch_3 fails twice
    scheduler.record_failure("branch_3")
    scheduler.record_failure("branch_3")

    # Branch_3 should be stopped
    should_stop, reason = scheduler.should_stop_branch("branch_3")
    assert should_stop
    assert "consecutive failures" in reason.lower()

    # Other branches should continue
    should_stop, _ = scheduler.should_stop_branch("branch_1")
    assert not should_stop

    should_stop, _ = scheduler.should_stop_branch("branch_2")
    assert not should_stop


def test_budget_exhaustion(total_budget):
    """Test behavior when budget is exhausted."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 50.0)

    # Use up most of the budget
    scheduler.record_usage("branch_1", cost_usd=28.0, time_seconds=10000, iterations=14)

    # Check remaining budget
    remaining = scheduler.get_remaining_budget()
    assert remaining["max_cost_usd"] == pytest.approx(2.0)
    assert remaining["max_time_hours"] < 0.5
    assert remaining["max_iterations"] == 1

    # One more iteration should exceed budget
    scheduler.record_usage("branch_1", cost_usd=3.0, time_seconds=100, iterations=1)

    should_stop, reason = scheduler.should_stop_branch("branch_1")
    assert should_stop
    assert "cost" in reason.lower()


def test_dynamic_reallocation_scenario(total_budget):
    """Test dynamic budget reallocation based on performance.

    Scenario:
    - Start with 3 equal branches
    - Branch 1 improves significantly
    - Branch 2 stays mediocre
    - Branch 3 degrades
    - Budget should shift to branch 1
    """
    scheduler = BudgetScheduler(total_budget)

    # Initial state: all equal
    for i in range(1, 4):
        scheduler.update_score(f"branch_{i}", 50.0)

    initial_allocation = scheduler.allocate_budget()

    # After some iterations: branch_1 improves
    scheduler.update_score("branch_1", 90.0)
    scheduler.update_score("branch_2", 55.0)
    scheduler.update_score("branch_3", 30.0)

    new_allocation = scheduler.allocate_budget()

    # Branch 1 should get more budget than initially
    assert (
        new_allocation["branch_1"]["max_cost_usd"]
        > initial_allocation["branch_1"]["max_cost_usd"]
    )

    # Branch 3 should get less budget
    assert (
        new_allocation["branch_3"]["max_cost_usd"]
        < initial_allocation["branch_3"]["max_cost_usd"]
    )


def test_failure_recovery(total_budget):
    """Test that success resets failure count."""
    scheduler = BudgetScheduler(total_budget)

    scheduler.update_score("branch_1", 50.0)

    # Record one failure
    scheduler.record_failure("branch_1")
    assert scheduler.failure_counts["branch_1"] == 1

    # Record success - should reset
    scheduler.record_success("branch_1")
    assert scheduler.failure_counts["branch_1"] == 0

    # One more failure should not trigger early stop
    scheduler.record_failure("branch_1")
    should_stop, _ = scheduler.should_stop_branch("branch_1")
    assert not should_stop


def test_multi_branch_independent_tracking(total_budget):
    """Test that branches are tracked independently."""
    scheduler = BudgetScheduler(total_budget)

    # Initialize branches
    scheduler.update_score("branch_1", 50.0)
    scheduler.update_score("branch_2", 50.0)

    # Branch 1 uses resources
    scheduler.record_usage("branch_1", cost_usd=5.0, time_seconds=500, iterations=2)

    # Branch 2 uses different resources
    scheduler.record_usage("branch_2", cost_usd=3.0, time_seconds=300, iterations=1)

    # Check independent tracking
    usage_1 = scheduler.get_usage("branch_1")
    usage_2 = scheduler.get_usage("branch_2")

    assert usage_1.cost_usd == 5.0
    assert usage_2.cost_usd == 3.0

    # Total should be sum
    total = scheduler.get_total_usage()
    assert total.cost_usd == 8.0
    assert total.time_seconds == 800
    assert total.iterations == 3


def test_zero_score_handling(total_budget):
    """Test handling of zero scores."""
    scheduler = BudgetScheduler(total_budget)

    # All branches have zero score initially
    scheduler.update_score("branch_1", 0.0)
    scheduler.update_score("branch_2", 0.0)
    scheduler.update_score("branch_3", 0.0)

    # Should fall back to equal allocation
    allocation = scheduler.allocate_budget()

    for branch_id, budget in allocation.items():
        assert budget["max_cost_usd"] == pytest.approx(10.0)
