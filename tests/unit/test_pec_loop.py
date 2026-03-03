"""Unit tests for PECLoop."""

from unittest.mock import Mock

import pytest

from src.agents.planner.pec_loop import PECLoop
from src.schemas import PlanStep
from src.schemas.research_spec import ExperimentPlan


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock()
    client.call = Mock()
    return client


@pytest.fixture
def test_plan():
    """Create test experiment plan."""
    return ExperimentPlan(
        plan_id="test_plan",
        spec_id="test_spec",
        title="Test Plan",
        steps=[
            PlanStep(
                step_id="step_1",
                description="Test step",
                expected_output="Test output",
            )
        ],
        method_summary="Test method summary",
        evaluation_protocol="Test evaluation protocol",
    )


def test_pec_loop_initialization(mock_llm_client):
    """Test PEC loop initialization."""
    loop = PECLoop(mock_llm_client, max_iterations=5, early_stop_threshold=2)

    assert loop.max_iterations == 5
    assert loop.planner is not None
    assert loop.critic is not None
    assert loop.early_stop_detector is not None


def test_pec_loop_success_first_iteration(mock_llm_client, test_plan):
    """Test PEC loop succeeds on first iteration."""
    # Mock planner response
    mock_llm_client.call.side_effect = [
        '{"reasoning": "test", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "success", "feedback": "Great!", "suggestions": [], "score": 100.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5)

    def executor_fn(planner_output, state):
        return {"result": "success"}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    assert len(memory_entries) == 1
    assert final_feedback.status == "success"
    assert final_feedback.score == 100.0


def test_pec_loop_max_iterations(mock_llm_client, test_plan):
    """Test PEC loop reaches max iterations."""
    # Mock responses for 5 iterations (all needs_improvement)
    mock_llm_client.call.side_effect = [
        '{"reasoning": "iter1", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "Try again", "suggestions": [], "score": 50.0}',
        '{"reasoning": "iter2", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "Try again", "suggestions": [], "score": 55.0}',
        '{"reasoning": "iter3", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "Try again", "suggestions": [], "score": 60.0}',
        '{"reasoning": "iter4", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "Try again", "suggestions": [], "score": 65.0}',
        '{"reasoning": "iter5", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "Try again", "suggestions": [], "score": 70.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5)

    def executor_fn(planner_output, state):
        return {"result": "ok"}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    assert len(memory_entries) == 5
    assert final_feedback.status == "failed"
    assert "maximum iterations" in final_feedback.feedback.lower()


def test_pec_loop_early_stop(mock_llm_client, test_plan):
    """Test PEC loop early stops after consecutive no-improvement."""
    # Mock responses: 1st improves, 2nd & 3rd no improvement
    mock_llm_client.call.side_effect = [
        '{"reasoning": "iter1", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "OK", "suggestions": [], "score": 50.0}',
        '{"reasoning": "iter2", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "No better", "suggestions": [], "score": 45.0}',
        '{"reasoning": "iter3", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "Still no better", "suggestions": [], "score": 40.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5, early_stop_threshold=2)

    def executor_fn(planner_output, state):
        return {"result": "ok"}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    assert len(memory_entries) == 3
    assert final_feedback.status == "failed"
    assert "early stop" in final_feedback.feedback.lower()


def test_pec_loop_immediate_failure(mock_llm_client, test_plan):
    """Test PEC loop handles immediate failure."""
    mock_llm_client.call.side_effect = [
        '{"reasoning": "test", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "failed", "feedback": "Critical error", "suggestions": [], "score": 0.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5)

    def executor_fn(planner_output, state):
        return {"error": "critical"}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    assert len(memory_entries) == 1
    assert final_feedback.status == "failed"
    assert "Critical error" in final_feedback.feedback


def test_pec_loop_state_propagation(mock_llm_client, test_plan):
    """Test that state is propagated between iterations."""
    mock_llm_client.call.side_effect = [
        '{"reasoning": "iter1", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "needs_improvement", "feedback": "OK", "suggestions": [], "score": 50.0}',
        '{"reasoning": "iter2", "tool_calls": [], "expected_improvement": "test"}',
        '{"status": "success", "feedback": "Done", "suggestions": [], "score": 100.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5)

    states_seen = []

    def executor_fn(planner_output, state):
        states_seen.append(state)
        return {"iteration": len(states_seen)}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {"initial": True})

    assert len(states_seen) == 2
    assert states_seen[0] == {"initial": True}
    assert states_seen[1] == {"iteration": 1}
