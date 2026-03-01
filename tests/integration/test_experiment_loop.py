"""Integration tests for ExperimentLoop with mocked LLM (no real API calls)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.agents.experiment.loop import ExperimentLoop
from src.llm.client import LLMClient, LLMConfig
from src.sandbox.subprocess_sandbox import SubprocessSandbox
from src.schemas import Constraints, CostUsage, Metric, PlanStep
from src.schemas.experiment import ExperimentRun
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.storage.artifact import ArtifactStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_spec(
    constraints: Constraints | None = None,
) -> ResearchSpec:
    return ResearchSpec(
        spec_id="test_spec",
        title="Test",
        objective="Test objective",
        metrics=[Metric(name="accuracy", direction="maximize", target=0.9)],
        constraints=constraints
        or Constraints(
            max_budget_usd=10.0,
            max_runtime_hours=1.0,
            max_iterations=5,
        ),
        status="confirmed",
    )


def make_plan() -> ExperimentPlan:
    return ExperimentPlan(
        plan_id="test_plan",
        spec_id="test_spec",
        method_summary="test method",
        evaluation_protocol="test eval",
        steps=[
            PlanStep(
                step_id="s1",
                description="test",
                expected_output="metrics.json",
            )
        ],
    )


def make_run() -> ExperimentRun:
    return ExperimentRun(
        run_id="run_001",
        spec_id="test_spec",
        plan_id="test_plan",
    )


def _mock_finish_success():
    """Mock litellm completion response with finish tool call (success)."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Experiment completed"

    mock_tool_call = Mock()
    mock_tool_call.id = "call_finish"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = "finish"
    mock_tool_call.function.arguments = '{"summary": "Test passed", "success": true, "artifacts": []}'

    mock_response.choices[0].message.tool_calls = [mock_tool_call]
    mock_cost = CostUsage(llm_calls=1, input_tokens=100, output_tokens=50, estimated_cost_usd=0.01)
    return (mock_response, mock_cost)


def _mock_finish_failure():
    """Mock litellm completion response with finish tool call (failure)."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Experiment failed"

    mock_tool_call = Mock()
    mock_tool_call.id = "call_finish"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = "finish"
    mock_tool_call.function.arguments = '{"summary": "Test failed", "success": false, "failure_reason": "error"}'

    mock_response.choices[0].message.tool_calls = [mock_tool_call]
    mock_cost = CostUsage(llm_calls=1, input_tokens=100, output_tokens=50, estimated_cost_usd=0.01)
    return (mock_response, mock_cost)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_loop_runs_3_iterations_then_stops(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop runs 3 iterations: first two fail, third succeeds."""
    llm = LLMClient(config=LLMConfig())
    llm._accumulated_cost = CostUsage()

    # Mock complete_with_tools: first 2 iterations fail, 3rd succeeds
    llm.complete_with_tools = Mock(side_effect=[
        _mock_finish_failure(),
        _mock_finish_failure(),
        _mock_finish_success(),
    ])

    sandbox = SubprocessSandbox(runs_dir=tmp_path)
    store = ArtifactStore(runs_dir=tmp_path)
    store.create_run_dir("run_001")

    loop = ExperimentLoop(llm=llm, sandbox=sandbox, store=store)
    run = make_run()

    # Act
    result = loop.run(run, make_spec(), make_plan())

    # Assert
    assert result.iteration_count == 3
    assert result.status == "succeeded"
    assert llm.complete_with_tools.call_count == 3

    # Verify iteration.json files exist
    for idx in (1, 2, 3):
        it_dir = f"iterations/it_{idx:04d}"
        assert store.path_exists("run_001", f"{it_dir}/iteration.json")


def test_loop_budget_exhausted(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop stops with budget_exhausted when cost exceeds max_budget_usd."""
    llm = LLMClient(config=LLMConfig())
    sandbox = SubprocessSandbox(runs_dir=tmp_path)
    store = ArtifactStore(runs_dir=tmp_path)
    store.create_run_dir("run_001")

    # Very tight budget
    spec = make_spec(
        constraints=Constraints(
            max_budget_usd=0.001,
            max_runtime_hours=1.0,
            max_iterations=10,
        ),
    )

    loop = ExperimentLoop(llm=llm, sandbox=sandbox, store=store)
    run = make_run()

    # Inflate cost after first iteration
    def completion_with_cost_bump(*args, **kwargs):
        llm._accumulated_cost = CostUsage(
            llm_calls=1,
            input_tokens=100,
            output_tokens=100,
            estimated_cost_usd=1.0,
        )
        return _mock_finish_failure()

    llm.complete_with_tools = Mock(side_effect=completion_with_cost_bump)

    # Act
    result = loop.run(run, spec, make_plan())

    # Assert
    assert result.status == "budget_exhausted"
    assert result.iteration_count >= 1


def test_loop_max_iterations(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop stops after reaching max_iterations."""
    llm = LLMClient(config=LLMConfig())
    llm._accumulated_cost = CostUsage()

    # Mock complete_with_tools to always return failure
    llm.complete_with_tools = Mock(return_value=_mock_finish_failure())

    sandbox = SubprocessSandbox(runs_dir=tmp_path)
    store = ArtifactStore(runs_dir=tmp_path)
    store.create_run_dir("run_001")

    spec = make_spec(
        constraints=Constraints(
            max_budget_usd=10.0,
            max_runtime_hours=1.0,
            max_iterations=2,
        ),
    )

    loop = ExperimentLoop(llm=llm, sandbox=sandbox, store=store)
    run = make_run()

    # Act
    result = loop.run(run, spec, make_plan())

    # Assert
    assert result.status == "stopped"
    assert result.iteration_count == 2
    assert result.stop_reason == "max_iterations"


def test_consecutive_failures_trigger_stop(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop fails after consecutive_failure_limit failures."""
    llm = LLMClient(config=LLMConfig())
    llm._accumulated_cost = CostUsage()

    # Mock complete_with_tools to always return failure
    llm.complete_with_tools = Mock(return_value=_mock_finish_failure())

    sandbox = SubprocessSandbox(runs_dir=tmp_path)
    store = ArtifactStore(runs_dir=tmp_path)
    store.create_run_dir("run_001")

    loop = ExperimentLoop(
        llm=llm,
        sandbox=sandbox,
        store=store,
        consecutive_failure_limit=2,
    )
    run = make_run()

    # Act
    result = loop.run(run, make_spec(), make_plan())

    # Assert
    assert result.status == "failed"
    assert result.stop_reason == "fatal_error"
    assert llm.complete_with_tools.call_count == 2

