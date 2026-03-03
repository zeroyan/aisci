"""Unit tests for ToolAgent with mocked LLM and sandbox."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock


from src.agents.experiment.tool_agent import ToolAgent
from src.llm.client import LLMClient, LLMConfig
from src.sandbox.base import SandboxExecutor
from src.schemas import CostUsage


def test_tool_agent_finish_success(tmp_path: Path) -> None:
    """ToolAgent calls finish tool and returns success."""
    # Mock LLM to return finish tool call
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()

    mock_sandbox = Mock(spec=SandboxExecutor)

    # Mock litellm completion response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Experiment completed successfully"

    # Create mock tool call with proper attributes
    mock_tool_call = Mock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = "finish"
    mock_tool_call.function.arguments = '{"summary": "Test passed", "success": true, "artifacts": ["results.txt"]}'

    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    # Mock complete_with_tools to return (response, cost)
    mock_cost = CostUsage(llm_calls=1, input_tokens=100, output_tokens=50, estimated_cost_usd=0.01)
    mock_llm.complete_with_tools = Mock(return_value=(mock_response, mock_cost))

    agent = ToolAgent(
        llm_client=mock_llm,
        sandbox=mock_sandbox,
        system_prompt="Test system prompt",
        max_turns=5,
    )

    workspace = tmp_path / "workspace"
    record = agent.run_iteration(
        run_id="test_run",
        iteration_index=1,
        workspace=workspace,
        initial_prompt="Run the test",
    )

    assert record.status == "finished"
    assert record.finish_result is not None
    assert record.finish_result.success is True
    assert record.finish_result.summary == "Test passed"
    assert record.total_turns == 1


def test_tool_agent_max_turns_timeout(tmp_path: Path) -> None:
    """ToolAgent times out after max_turns without finish."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()
    mock_sandbox = Mock(spec=SandboxExecutor)

    # Mock LLM to always return write_file (never finish)
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Writing file"

    mock_tool_call = Mock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = "write_file"
    mock_tool_call.function.arguments = '{"path": "test.py", "content": "print(1)"}'

    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    # Mock complete_with_tools to return (response, cost)
    mock_cost = CostUsage(llm_calls=1, input_tokens=100, output_tokens=50, estimated_cost_usd=0.01)
    mock_llm.complete_with_tools = Mock(return_value=(mock_response, mock_cost))

    agent = ToolAgent(
        llm_client=mock_llm,
        sandbox=mock_sandbox,
        system_prompt="Test",
        max_turns=3,
    )

    workspace = tmp_path / "workspace"
    record = agent.run_iteration(
        run_id="test_run",
        iteration_index=1,
        workspace=workspace,
        initial_prompt="Run test",
    )

    assert record.status == "timeout"
    assert record.total_turns == 3
    assert record.finish_result is not None
    assert record.finish_result.success is False
    assert "max_turns" in record.finish_result.failure_reason.lower()


def test_tool_agent_finish_failure(tmp_path: Path) -> None:
    """ToolAgent calls finish with success=false."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()
    mock_sandbox = Mock(spec=SandboxExecutor)

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Experiment failed"

    mock_tool_call = Mock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = "finish"
    mock_tool_call.function.arguments = '{"summary": "Test failed", "success": false, "failure_reason": "Import error"}'

    mock_response.choices[0].message.tool_calls = [mock_tool_call]

    # Mock complete_with_tools to return (response, cost)
    mock_cost = CostUsage(llm_calls=1, input_tokens=100, output_tokens=50, estimated_cost_usd=0.01)
    mock_llm.complete_with_tools = Mock(return_value=(mock_response, mock_cost))

    agent = ToolAgent(
        llm_client=mock_llm,
        sandbox=mock_sandbox,
        system_prompt="Test",
        max_turns=5,
    )

    workspace = tmp_path / "workspace"
    record = agent.run_iteration(
        run_id="test_run",
        iteration_index=1,
        workspace=workspace,
        initial_prompt="Run test",
    )

    assert record.status == "finished"
    assert record.finish_result is not None
    assert record.finish_result.success is False
    assert record.finish_result.failure_reason == "Import error"
