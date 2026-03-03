"""Unit tests for CriticAgent."""

from unittest.mock import Mock

import pytest

from src.agents.planner.critic_agent import CriticAgent
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


def test_critic_initialization(mock_llm_client):
    """Test critic agent initialization."""
    critic = CriticAgent(mock_llm_client)

    assert critic.llm_client == mock_llm_client


def test_evaluate_success(mock_llm_client, test_plan):
    """Test evaluation with success status."""
    mock_llm_client.call.return_value = """{
        "status": "success",
        "feedback": "All tests passed",
        "suggestions": [],
        "score": 95.0
    }"""

    critic = CriticAgent(mock_llm_client)
    execution_result = {"tests_passed": True, "accuracy": 0.95}

    result = critic.evaluate(test_plan, execution_result)

    assert result.status == "success"
    assert result.feedback == "All tests passed"
    assert result.score == 95.0
    assert len(result.suggestions) == 0


def test_evaluate_failed(mock_llm_client, test_plan):
    """Test evaluation with failed status."""
    mock_llm_client.call.return_value = """{
        "status": "failed",
        "feedback": "Tests failed",
        "suggestions": ["Fix the bug", "Add error handling"],
        "score": 20.0
    }"""

    critic = CriticAgent(mock_llm_client)
    execution_result = {"tests_passed": False, "error": "RuntimeError"}

    result = critic.evaluate(test_plan, execution_result)

    assert result.status == "failed"
    assert "Tests failed" in result.feedback
    assert len(result.suggestions) == 2
    assert result.score == 20.0


def test_evaluate_needs_improvement(mock_llm_client, test_plan):
    """Test evaluation with needs_improvement status."""
    mock_llm_client.call.return_value = """{
        "status": "needs_improvement",
        "feedback": "Accuracy too low",
        "suggestions": ["Try different hyperparameters"],
        "score": 60.0
    }"""

    critic = CriticAgent(mock_llm_client)
    execution_result = {"accuracy": 0.6}

    result = critic.evaluate(test_plan, execution_result)

    assert result.status == "needs_improvement"
    assert result.score == 60.0
    assert len(result.suggestions) > 0


def test_evaluate_with_history(mock_llm_client, test_plan):
    """Test evaluation with previous attempts."""
    mock_llm_client.call.return_value = """{
        "status": "needs_improvement",
        "feedback": "Still not good enough",
        "suggestions": ["Try a different approach"],
        "score": 65.0
    }"""

    critic = CriticAgent(mock_llm_client)
    execution_result = {"accuracy": 0.65}
    previous_attempts = [
        {"iteration": 1, "score": 50.0},
        {"iteration": 2, "score": 60.0},
    ]

    _ = critic.evaluate(test_plan, execution_result, previous_attempts)

    # Verify history was included in prompt
    call_args = mock_llm_client.call.call_args
    prompt = call_args[1]["messages"][0]["content"]
    assert "2 attempts made" in prompt


def test_evaluate_invalid_json(mock_llm_client, test_plan):
    """Test evaluation with invalid JSON response."""
    mock_llm_client.call.return_value = "not json"

    critic = CriticAgent(mock_llm_client)
    execution_result = {"result": "unknown"}

    result = critic.evaluate(test_plan, execution_result)

    # Should return fallback feedback
    assert result.status == "needs_improvement"
    assert "Failed to parse" in result.feedback
    assert result.score == 0.0


def test_build_critic_prompt(mock_llm_client, test_plan):
    """Test critic prompt construction."""
    critic = CriticAgent(mock_llm_client)
    execution_result = {"accuracy": 0.8}
    previous_attempts = [{"iteration": 1}]

    prompt = critic._build_critic_prompt(test_plan, execution_result, previous_attempts)

    assert "Test method summary" in prompt
    assert "0.8" in prompt
    assert "1 attempts made" in prompt
    assert "status" in prompt
    assert "feedback" in prompt
