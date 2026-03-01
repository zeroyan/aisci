"""Integration tests for ExperimentLoop with mocked LLM (no real API calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.experiment.analyzer import AnalyzerAgent
from src.agents.experiment.codegen import CodegenAgent
from src.agents.experiment.loop import ExperimentLoop
from src.llm.client import LLMClient, LLMConfig
from src.sandbox.subprocess_sandbox import SubprocessSandbox
from src.schemas import Constraints, CostUsage, Metric, PlanStep
from src.schemas.experiment import ExperimentRun
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.schemas.sandbox_io import AgentDecision, CodeSnapshot, NextAction
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


def _code_snapshot() -> CodeSnapshot:
    """A code snapshot whose entrypoint actually produces metrics.json."""
    return CodeSnapshot(
        files={
            "main.py": (
                "import json; json.dump({'accuracy': 0.85}, open('metrics.json','w'))"
            ),
        },
        entrypoint="python main.py",
    )


def _continue_decision(iteration_id: str, run_id: str) -> AgentDecision:
    return AgentDecision(
        iteration_id=iteration_id,
        run_id=run_id,
        decision="continue",
        analysis_summary="Metrics improving, continue.",
        next_action=NextAction(
            strategy="tune hyperparams",
            rationale="accuracy not yet at target",
        ),
    )


def _stop_decision(
    iteration_id: str,
    run_id: str,
    stop_reason: str = "goal_met",
) -> AgentDecision:
    return AgentDecision(
        iteration_id=iteration_id,
        run_id=run_id,
        decision="stop",
        stop_reason=stop_reason,
        analysis_summary="Goal met, stopping.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch.object(CodegenAgent, "generate")
@patch.object(AnalyzerAgent, "analyze")
def test_loop_runs_3_iterations_then_stops(
    mock_analyze: MagicMock,
    mock_generate: MagicMock,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop runs 3 iterations: first two continue, third stops with goal_met."""
    # -- Arrange --
    mock_generate.return_value = _code_snapshot()

    # Continue for iterations 1-2, stop on iteration 3
    mock_analyze.side_effect = [
        _continue_decision("it_0001", "run_001"),
        _continue_decision("it_0002", "run_001"),
        _stop_decision("it_0003", "run_001", stop_reason="goal_met"),
    ]

    llm = LLMClient(config=LLMConfig())
    # Provide a zero-cost accumulated_cost so budget guard never triggers
    llm._accumulated_cost = CostUsage()

    sandbox = SubprocessSandbox(runs_dir=tmp_path)
    store = ArtifactStore(runs_dir=tmp_path)
    store.create_run_dir("run_001")

    loop = ExperimentLoop(llm=llm, sandbox=sandbox, store=store)
    run = make_run()

    # -- Act --
    result = loop.run(run, make_spec(), make_plan())

    # -- Assert --
    assert result.iteration_count == 3
    assert result.status == "succeeded"
    assert mock_generate.call_count == 3
    assert mock_analyze.call_count == 3

    # Verify iteration.json files exist on disk
    for idx in (1, 2, 3):
        it_dir = f"iterations/it_{idx:04d}"
        assert store.path_exists("run_001", f"{it_dir}/iteration.json")


@patch.object(CodegenAgent, "generate")
@patch.object(AnalyzerAgent, "analyze")
def test_loop_budget_exhausted(
    mock_analyze: MagicMock,
    mock_generate: MagicMock,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop stops with budget_exhausted when cost exceeds max_budget_usd."""
    # -- Arrange --
    mock_generate.return_value = _code_snapshot()
    mock_analyze.return_value = _continue_decision("it_0001", "run_001")

    llm = LLMClient(config=LLMConfig())
    sandbox = SubprocessSandbox(runs_dir=tmp_path)
    store = ArtifactStore(runs_dir=tmp_path)
    store.create_run_dir("run_001")

    # Use a very tight budget
    spec = make_spec(
        constraints=Constraints(
            max_budget_usd=0.001,
            max_runtime_hours=1.0,
            max_iterations=10,
        ),
    )

    loop = ExperimentLoop(llm=llm, sandbox=sandbox, store=store)
    run = make_run()

    # After the first iteration completes and the loop updates cost,
    # set accumulated_cost high so the budget guard fires on the next check.

    def analyze_with_cost_bump(*args, **kwargs):
        # After analyze returns, the loop sets run.cost_usage from
        # llm.accumulated_cost. We inflate cost so the *next* guard fires.
        llm._accumulated_cost = CostUsage(
            llm_calls=1,
            input_tokens=100,
            output_tokens=100,
            estimated_cost_usd=1.0,
        )
        return _continue_decision("it_0001", "run_001")

    mock_analyze.side_effect = analyze_with_cost_bump

    # -- Act --
    result = loop.run(run, spec, make_plan())

    # -- Assert --
    assert result.status == "budget_exhausted"
    assert result.iteration_count >= 1


@patch.object(CodegenAgent, "generate")
@patch.object(AnalyzerAgent, "analyze")
def test_loop_max_iterations(
    mock_analyze: MagicMock,
    mock_generate: MagicMock,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop stops after reaching max_iterations with status stopped."""
    # -- Arrange --
    mock_generate.return_value = _code_snapshot()
    # Always continue — the loop should be stopped by the max_iterations guard
    mock_analyze.return_value = _continue_decision("placeholder", "run_001")

    # Override side_effect to produce the correct iteration_id dynamically
    call_count = 0

    def dynamic_analyze(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _continue_decision(f"it_{call_count:04d}", "run_001")

    mock_analyze.side_effect = dynamic_analyze

    llm = LLMClient(config=LLMConfig())
    llm._accumulated_cost = CostUsage()

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

    # -- Act --
    result = loop.run(run, spec, make_plan())

    # -- Assert --
    assert result.status == "stopped"
    assert result.iteration_count == 2
    assert result.stop_reason == "max_iterations"


@patch.object(CodegenAgent, "generate")
def test_consecutive_failures_trigger_stop(
    mock_generate: MagicMock,
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Loop fails after consecutive_failure_limit codegen exceptions."""
    # -- Arrange --
    mock_generate.side_effect = RuntimeError("LLM unavailable")

    llm = LLMClient(config=LLMConfig())
    llm._accumulated_cost = CostUsage()

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

    # -- Act --
    result = loop.run(run, make_spec(), make_plan())

    # -- Assert --
    assert result.status == "failed"
    assert result.stop_reason == "fatal_error"
    # generate should have been called exactly consecutive_failure_limit times
    assert mock_generate.call_count == 2
