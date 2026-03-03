"""Unit tests for EarlyStopStrategy."""

import pytest

from src.scheduler.early_stop_strategy import CompositeEarlyStopStrategy
from src.scheduler.resource_tracker import ResourceUsage


@pytest.fixture
def budget():
    """Create test budget."""
    return {
        "max_cost_usd": 10.0,
        "max_time_hours": 1.0,
        "max_iterations": 5,
    }


def test_strategy_initialization():
    """Test strategy initialization."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=3)

    assert strategy.max_consecutive_failures == 3


def test_no_stop_within_limits(budget):
    """Test no stop when within all limits."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=5.0, time_seconds=1800, iterations=2)
    failure_count = 0

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert not should_stop
    assert reason == ""


def test_stop_on_consecutive_failures(budget):
    """Test stop on consecutive failures."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=5.0, time_seconds=1800, iterations=2)
    failure_count = 2

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert should_stop
    assert "consecutive failures" in reason.lower()
    assert "branch_1" in reason


def test_stop_on_cost_exceeded(budget):
    """Test stop when cost budget exceeded."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=12.0, time_seconds=1800, iterations=2)
    failure_count = 0

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert should_stop
    assert "cost" in reason.lower()


def test_stop_on_time_exceeded(budget):
    """Test stop when time budget exceeded."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=5.0, time_seconds=4000, iterations=2)  # > 1 hour
    failure_count = 0

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert should_stop
    assert "time" in reason.lower()


def test_stop_on_iterations_exceeded(budget):
    """Test stop when iterations budget exceeded."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=5.0, time_seconds=1800, iterations=6)
    failure_count = 0

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert should_stop
    assert "iterations" in reason.lower()


def test_custom_failure_threshold(budget):
    """Test custom consecutive failure threshold."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=5)

    usage = ResourceUsage(cost_usd=5.0, time_seconds=1800, iterations=2)

    # 4 failures should not stop
    should_stop, _ = strategy.should_stop("branch_1", usage, budget, 4)
    assert not should_stop

    # 5 failures should stop
    should_stop, reason = strategy.should_stop("branch_1", usage, budget, 5)
    assert should_stop
    assert "5 consecutive failures" in reason


def test_multiple_conditions_first_triggers(budget):
    """Test that first violated condition triggers stop."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    # Both failures and cost exceeded
    usage = ResourceUsage(cost_usd=15.0, time_seconds=1800, iterations=2)
    failure_count = 3

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert should_stop
    # Should report failures first (checked first in implementation)
    assert "consecutive failures" in reason.lower()


def test_edge_case_exact_budget(budget):
    """Test edge case when usage exactly equals budget."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=10.0, time_seconds=3600, iterations=5)
    failure_count = 0

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    # Exact budget should not trigger stop (only exceeding should)
    assert not should_stop


def test_zero_failures_no_stop(budget):
    """Test that zero failures don't trigger stop."""
    strategy = CompositeEarlyStopStrategy(max_consecutive_failures=2)

    usage = ResourceUsage(cost_usd=5.0, time_seconds=1800, iterations=2)
    failure_count = 0

    should_stop, reason = strategy.should_stop("branch_1", usage, budget, failure_count)

    assert not should_stop
    assert reason == ""
