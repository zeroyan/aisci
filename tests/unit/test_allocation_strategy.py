"""Unit tests for AllocationStrategy."""

import pytest

from src.scheduler.allocation_strategy import (
    EqualAllocationStrategy,
    PerformanceBasedAllocationStrategy,
)
from src.scheduler.resource_tracker import ResourceUsage


@pytest.fixture
def total_budget():
    """Create test budget."""
    return {
        "max_cost_usd": 30.0,
        "max_time_hours": 3.0,
        "max_iterations": 15,
    }


@pytest.fixture
def branch_scores():
    """Create test branch scores."""
    return {
        "branch_1": 80.0,
        "branch_2": 60.0,
        "branch_3": 40.0,
    }


@pytest.fixture
def branch_usage():
    """Create test branch usage."""
    return {
        "branch_1": ResourceUsage(cost_usd=5.0, time_seconds=300, iterations=2),
        "branch_2": ResourceUsage(cost_usd=3.0, time_seconds=200, iterations=1),
        "branch_3": ResourceUsage(cost_usd=2.0, time_seconds=100, iterations=1),
    }


def test_equal_allocation(total_budget, branch_scores, branch_usage):
    """Test equal allocation strategy."""
    strategy = EqualAllocationStrategy()

    allocation = strategy.allocate(total_budget, branch_scores, branch_usage)

    # Each branch should get 1/3 of total budget
    assert len(allocation) == 3
    for branch_id, budget in allocation.items():
        assert budget["max_cost_usd"] == pytest.approx(10.0)
        assert budget["max_time_hours"] == pytest.approx(1.0)
        assert budget["max_iterations"] == 5


def test_equal_allocation_empty_branches(total_budget):
    """Test equal allocation with no branches."""
    strategy = EqualAllocationStrategy()

    allocation = strategy.allocate(total_budget, {}, {})

    assert allocation == {}


def test_performance_based_allocation(total_budget, branch_scores, branch_usage):
    """Test performance-based allocation."""
    strategy = PerformanceBasedAllocationStrategy(min_allocation_ratio=0.2)

    allocation = strategy.allocate(total_budget, branch_scores, branch_usage)

    # Better performers should get more budget
    assert allocation["branch_1"]["max_cost_usd"] > allocation["branch_2"]["max_cost_usd"]
    assert allocation["branch_2"]["max_cost_usd"] > allocation["branch_3"]["max_cost_usd"]

    # Total should equal original budget
    total_cost = sum(b["max_cost_usd"] for b in allocation.values())
    assert total_cost == pytest.approx(30.0)


def test_performance_based_minimum_allocation(total_budget, branch_usage):
    """Test that minimum allocation is respected."""
    strategy = PerformanceBasedAllocationStrategy(min_allocation_ratio=0.2)

    # One branch has very high score, others have low scores
    branch_scores = {
        "branch_1": 95.0,
        "branch_2": 3.0,
        "branch_3": 2.0,
    }

    allocation = strategy.allocate(total_budget, branch_scores, branch_usage)

    # Even worst performer should get at least min_allocation_ratio / num_branches
    min_expected = (0.2 / 3) * 30.0  # ~2.0
    assert allocation["branch_3"]["max_cost_usd"] >= min_expected


def test_performance_based_zero_scores(total_budget, branch_usage):
    """Test performance-based allocation with zero scores."""
    strategy = PerformanceBasedAllocationStrategy()

    branch_scores = {
        "branch_1": 0.0,
        "branch_2": 0.0,
        "branch_3": 0.0,
    }

    allocation = strategy.allocate(total_budget, branch_scores, branch_usage)

    # Should fall back to equal allocation
    for branch_id, budget in allocation.items():
        assert budget["max_cost_usd"] == pytest.approx(10.0)


def test_performance_based_single_branch(total_budget):
    """Test performance-based allocation with single branch."""
    strategy = PerformanceBasedAllocationStrategy()

    branch_scores = {"branch_1": 80.0}
    branch_usage = {"branch_1": ResourceUsage()}

    allocation = strategy.allocate(total_budget, branch_scores, branch_usage)

    # Single branch should get all budget
    assert allocation["branch_1"]["max_cost_usd"] == pytest.approx(30.0)
    assert allocation["branch_1"]["max_time_hours"] == pytest.approx(3.0)
    assert allocation["branch_1"]["max_iterations"] == 15


def test_performance_based_custom_min_ratio(total_budget, branch_scores, branch_usage):
    """Test performance-based allocation with custom minimum ratio."""
    strategy = PerformanceBasedAllocationStrategy(min_allocation_ratio=0.5)

    allocation = strategy.allocate(total_budget, branch_scores, branch_usage)

    # With higher min ratio, allocation should be more equal
    cost_range = max(b["max_cost_usd"] for b in allocation.values()) - min(
        b["max_cost_usd"] for b in allocation.values()
    )

    # Compare with lower min ratio
    strategy_low = PerformanceBasedAllocationStrategy(min_allocation_ratio=0.1)
    allocation_low = strategy_low.allocate(total_budget, branch_scores, branch_usage)
    cost_range_low = max(b["max_cost_usd"] for b in allocation_low.values()) - min(
        b["max_cost_usd"] for b in allocation_low.values()
    )

    assert cost_range < cost_range_low
