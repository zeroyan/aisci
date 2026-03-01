import pytest
from pydantic import ValidationError

from src.schemas import CostUsage, Constraints, EvidenceEntry, Metric
from src.schemas.errors import AiSciError, AiSciException, ErrorCode
from src.schemas.experiment import ExperimentRun
from src.schemas.research_spec import ResearchSpec
from src.schemas.sandbox_io import AgentDecision, NextAction
from src.schemas.state import (
    TERMINAL_STATUSES,
    RunStatus,
    validate_transition,
)


# ── CostUsage ────────────────────────────────────────────────────────────


def test_cost_usage_add_sums_all_fields():
    a = CostUsage(
        llm_calls=1, input_tokens=10, output_tokens=5, estimated_cost_usd=0.01
    )
    b = CostUsage(
        llm_calls=2, input_tokens=20, output_tokens=10, estimated_cost_usd=0.02
    )
    result = a + b
    assert result.llm_calls == 3
    assert result.input_tokens == 30
    assert result.output_tokens == 15
    assert result.estimated_cost_usd == pytest.approx(0.03)


def test_cost_usage_negative_cost_fails():
    with pytest.raises(ValidationError):
        CostUsage(estimated_cost_usd=-1.0)


# ── EvidenceEntry ────────────────────────────────────────────────────────


def test_evidence_entry_empty_paths_fails():
    with pytest.raises(ValidationError):
        EvidenceEntry(claim="some claim", evidence_paths=[])


# ── Metric ───────────────────────────────────────────────────────────────


def test_metric_valid_maximize():
    m = Metric(name="accuracy", direction="maximize")
    assert m.name == "accuracy"
    assert m.direction == "maximize"


def test_metric_invalid_direction():
    with pytest.raises(ValidationError):
        Metric(name="accuracy", direction="invalid")


# ── Constraints ──────────────────────────────────────────────────────────


def test_constraints_zero_budget_fails():
    with pytest.raises(ValidationError):
        Constraints(max_budget_usd=0, max_runtime_hours=1, max_iterations=1)


def test_constraints_negative_budget_fails():
    with pytest.raises(ValidationError):
        Constraints(max_budget_usd=-5, max_runtime_hours=1, max_iterations=1)


# ── ResearchSpec ─────────────────────────────────────────────────────────


def _make_constraints(**overrides):
    defaults = dict(max_budget_usd=10, max_runtime_hours=2, max_iterations=5)
    defaults.update(overrides)
    return Constraints(**defaults)


def _make_metric(**overrides):
    defaults = dict(name="accuracy", direction="maximize")
    defaults.update(overrides)
    return Metric(**defaults)


def test_research_spec_valid_confirmed():
    spec = ResearchSpec(
        spec_id="spec-001",
        title="Test",
        objective="Objective",
        metrics=[_make_metric()],
        constraints=_make_constraints(),
        status="confirmed",
    )
    assert spec.status == "confirmed"
    assert spec.spec_id == "spec-001"


def test_research_spec_empty_metrics_fails():
    with pytest.raises(ValidationError):
        ResearchSpec(
            spec_id="spec-001",
            title="Test",
            objective="Objective",
            metrics=[],
            constraints=_make_constraints(),
            status="draft",
        )


def test_research_spec_empty_spec_id_fails():
    with pytest.raises(ValidationError):
        ResearchSpec(
            spec_id="",
            title="Test",
            objective="Objective",
            metrics=[_make_metric()],
            constraints=_make_constraints(),
            status="draft",
        )


# ── ExperimentRun ────────────────────────────────────────────────────────


def test_experiment_run_default_status_is_queued():
    run = ExperimentRun(run_id="run-1", spec_id="spec-1")
    assert run.status == RunStatus.QUEUED


def test_experiment_run_valid_transition_queued_to_running():
    run = ExperimentRun(run_id="run-1", spec_id="spec-1")
    run.transition_to(RunStatus.RUNNING)
    assert run.status == RunStatus.RUNNING


def test_experiment_run_invalid_transition_queued_to_succeeded():
    run = ExperimentRun(run_id="run-1", spec_id="spec-1")
    with pytest.raises(ValueError):
        run.transition_to(RunStatus.SUCCEEDED)


# ── RunStatus & state machine ────────────────────────────────────────────


def test_validate_transition_valid():
    validate_transition(RunStatus.QUEUED, RunStatus.RUNNING)


def test_validate_transition_invalid():
    with pytest.raises(ValueError):
        validate_transition(RunStatus.QUEUED, RunStatus.SUCCEEDED)


def test_terminal_statuses():
    expected = {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.STOPPED,
        RunStatus.BUDGET_EXHAUSTED,
        RunStatus.TIMEOUT,
    }
    assert TERMINAL_STATUSES == expected


# ── AiSciError / AiSciException ─────────────────────────────────────────


def test_error_code_has_8_members():
    assert len(ErrorCode) == 8


def test_aisci_exception_stores_error_and_message():
    err = AiSciError(code=ErrorCode.unknown, message="boom", retryable=False)
    exc = AiSciException(err)
    assert exc.error is err
    assert str(exc) == "boom"


# ── AgentDecision ────────────────────────────────────────────────────────


def test_agent_decision_stop_without_stop_reason_fails():
    with pytest.raises(ValidationError):
        AgentDecision(
            iteration_id="it-1",
            run_id="run-1",
            decision="stop",
            analysis_summary="done",
        )


def test_agent_decision_continue_without_next_action_fails():
    with pytest.raises(ValidationError):
        AgentDecision(
            iteration_id="it-1",
            run_id="run-1",
            decision="continue",
            analysis_summary="improving",
        )


def test_agent_decision_valid_stop():
    d = AgentDecision(
        iteration_id="it-1",
        run_id="run-1",
        decision="stop",
        stop_reason="goal_met",
        analysis_summary="target reached",
    )
    assert d.decision == "stop"
    assert d.stop_reason == "goal_met"


def test_agent_decision_valid_continue():
    d = AgentDecision(
        iteration_id="it-1",
        run_id="run-1",
        decision="continue",
        analysis_summary="improving",
        next_action=NextAction(strategy="lr_decay", rationale="loss plateau"),
    )
    assert d.decision == "continue"
    assert d.next_action is not None
    assert d.next_action.strategy == "lr_decay"
