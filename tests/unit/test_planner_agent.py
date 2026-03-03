"""Unit tests for PlannerAgent."""

from unittest.mock import Mock

import pytest

from src.agents.planner.planner_agent import PlannerAgent
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


def test_planner_initialization(mock_llm_client):
    """Test planner agent initialization."""
    planner = PlannerAgent(mock_llm_client)

    assert planner.llm_client == mock_llm_client


def test_generate_plan_basic(mock_llm_client, test_plan):
    """Test basic plan generation."""
    # Mock LLM response
    mock_llm_client.call.return_value = """{
        "reasoning": "Need to implement baseline",
        "tool_calls": [{"tool": "write_code", "args": {"file": "test.py"}}],
        "expected_improvement": "Baseline implementation"
    }"""

    planner = PlannerAgent(mock_llm_client)
    current_state = {"code": "empty"}

    result = planner.generate_plan(test_plan, current_state)

    assert result.reasoning == "Need to implement baseline"
    assert len(result.tool_calls) == 1
    assert result.expected_improvement == "Baseline implementation"
    mock_llm_client.call.assert_called_once()


def test_generate_plan_with_feedback(mock_llm_client, test_plan):
    """Test plan generation with previous feedback."""
    mock_llm_client.call.return_value = """{
        "reasoning": "Addressing previous feedback",
        "tool_calls": [{"tool": "fix_bug", "args": {"line": 10}}],
        "expected_improvement": "Bug fixed"
    }"""

    planner = PlannerAgent(mock_llm_client)
    current_state = {"code": "buggy"}
    previous_feedback = "Line 10 has a bug"

    result = planner.generate_plan(test_plan, current_state, previous_feedback)

    assert "Addressing previous feedback" in result.reasoning
    # Verify feedback was included in prompt
    call_args = mock_llm_client.call.call_args
    prompt = call_args[1]["messages"][0]["content"]
    assert "Line 10 has a bug" in prompt


def test_generate_plan_invalid_json(mock_llm_client, test_plan):
    """Test plan generation with invalid JSON response."""
    mock_llm_client.call.return_value = "invalid json"

    planner = PlannerAgent(mock_llm_client)
    current_state = {"code": "empty"}

    result = planner.generate_plan(test_plan, current_state)

    # Should return fallback plan
    assert result.reasoning == "Failed to parse response"
    assert len(result.tool_calls) == 0


def test_build_planner_prompt(mock_llm_client, test_plan):
    """Test planner prompt construction."""
    planner = PlannerAgent(mock_llm_client)
    current_state = {"code": "test"}
    previous_feedback = "Good progress"

    prompt = planner._build_planner_prompt(test_plan, current_state, previous_feedback)

    assert "Test method summary" in prompt
    assert "test" in prompt
    assert "Good progress" in prompt
    assert "reasoning" in prompt
    assert "tool_calls" in prompt
