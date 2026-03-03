"""Tests to detect placeholder implementations."""

import pytest

from src.orchestrator.branch_orchestrator import BranchOrchestrator
from src.orchestrator.config import OrchestratorConfig
from src.schemas import Baseline, PlanStep
from src.schemas.research_spec import ExperimentPlan, ResearchSpec


@pytest.fixture
def test_spec():
    """Create test research spec."""
    from src.schemas import Constraints, Metric

    return ResearchSpec(
        spec_id="test_spec",
        title="Placeholder Detection Test",
        objective="Detect placeholder implementations",
        metrics=[Metric(name="accuracy", direction="maximize")],
        constraints=Constraints(
            max_budget_usd=10.0, max_runtime_hours=1.0, max_iterations=5
        ),
        status="confirmed",
    )


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
        baseline=Baseline(status="pending"),
        method_summary="Test method",
        evaluation_protocol="Test protocol",
    )


def test_orchestrator_performs_real_execution(test_spec, test_plan, tmp_path):
    """Verify orchestrator performs real execution (not placeholder).

    This test ensures the core execution logic is implemented.
    If this test fails, it means we've regressed to placeholder behavior.
    """
    from unittest.mock import MagicMock
    from src.llm.client import LLMClient

    # Create mock LLM client
    mock_llm = MagicMock(spec=LLMClient)

    config = OrchestratorConfig.default()
    orchestrator = BranchOrchestrator(config, mock_llm)

    result = orchestrator.run(
        spec=test_spec,
        plan=test_plan,
        run_id="placeholder_test",
        runs_dir=tmp_path,
    )

    # These assertions verify real execution (not placeholder)
    # Note: With mock LLM, iterations might be 0, but time should be > 0
    assert result.total_time_seconds > 0, "Should have non-zero time (got placeholder 0.0)"
    assert result.status in ["success", "failed"], f"Should have valid status, got {result.status}"

    # Verify branch directories were created
    run_dir = tmp_path / "placeholder_test"
    assert run_dir.exists(), "Run directory should exist"
