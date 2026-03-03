"""Integration tests for Planner-Executor-Critic loop."""

from unittest.mock import Mock

import pytest

from src.agents.planner.pec_loop import PECLoop
from src.orchestrator.branch_executor import BranchExecutor
from src.schemas import Baseline, Constraints, Metric, PlanStep
from src.schemas.orchestrator import BranchConfig, BudgetAllocation
from src.schemas.research_spec import ExperimentPlan, ResearchSpec


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = Mock()
    client.call = Mock()
    return client


@pytest.fixture
def test_spec():
    """Create test research spec."""
    return ResearchSpec(
        spec_id="test_spec",
        title="PEC Loop Test",
        objective="Test PEC loop integration",
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
                description="Implement baseline",
                expected_output="Working baseline",
            ),
            PlanStep(
                step_id="step_2",
                description="Tune hyperparameters",
                expected_output="Optimized model",
            ),
        ],
        baseline=Baseline(status="pending"),
        method_summary="Test method with multiple steps",
        evaluation_protocol="Measure accuracy on test set",
    )


def test_pec_loop_multi_iteration_success(mock_llm_client, test_plan):
    """Test PEC loop with multiple iterations leading to success."""
    # Simulate 3 iterations: needs_improvement, needs_improvement, success
    mock_llm_client.call.side_effect = [
        # Iteration 1
        '{"reasoning": "Start with baseline", "tool_calls": [{"tool": "write_code"}], "expected_improvement": "Baseline"}',
        '{"status": "needs_improvement", "feedback": "Accuracy 60%, need 80%", "suggestions": ["Add regularization"], "score": 60.0}',
        # Iteration 2
        '{"reasoning": "Add regularization", "tool_calls": [{"tool": "update_code"}], "expected_improvement": "Better generalization"}',
        '{"status": "needs_improvement", "feedback": "Accuracy 75%, almost there", "suggestions": ["Tune learning rate"], "score": 75.0}',
        # Iteration 3
        '{"reasoning": "Tune learning rate", "tool_calls": [{"tool": "tune_params"}], "expected_improvement": "Reach target"}',
        '{"status": "success", "feedback": "Accuracy 85%, target reached!", "suggestions": [], "score": 85.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5, early_stop_threshold=2)

    def executor_fn(planner_output, state):
        iteration = state.get("iteration", 0) + 1
        return {"iteration": iteration, "executed": True}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    # Verify 3 iterations
    assert len(memory_entries) == 3

    # Verify progression
    assert memory_entries[0].critic_feedback.score == 60.0
    assert memory_entries[1].critic_feedback.score == 75.0
    assert memory_entries[2].critic_feedback.score == 85.0

    # Verify success
    assert final_feedback.status == "success"
    assert final_feedback.score == 85.0


def test_pec_loop_early_stop_on_no_improvement(mock_llm_client, test_plan):
    """Test PEC loop early stops when no improvement."""
    # Simulate: improve, no improve, no improve -> early stop
    mock_llm_client.call.side_effect = [
        # Iteration 1
        '{"reasoning": "First try", "tool_calls": [], "expected_improvement": "Baseline"}',
        '{"status": "needs_improvement", "feedback": "Score 50", "suggestions": [], "score": 50.0}',
        # Iteration 2
        '{"reasoning": "Second try", "tool_calls": [], "expected_improvement": "Better"}',
        '{"status": "needs_improvement", "feedback": "Score 45", "suggestions": [], "score": 45.0}',
        # Iteration 3
        '{"reasoning": "Third try", "tool_calls": [], "expected_improvement": "Even better"}',
        '{"status": "needs_improvement", "feedback": "Score 40", "suggestions": [], "score": 40.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5, early_stop_threshold=2)

    def executor_fn(planner_output, state):
        return {"executed": True}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    # Should stop after 3 iterations
    assert len(memory_entries) == 3

    # Verify early stop
    assert final_feedback.status == "failed"
    assert "early stop" in final_feedback.feedback.lower()


def test_pec_loop_max_iterations_reached(mock_llm_client, test_plan):
    """Test PEC loop reaches max iterations."""
    # All iterations show improvement but never succeed
    responses = []
    for i in range(1, 6):
        responses.extend(
            [
                f'{{"reasoning": "Iteration {i}", "tool_calls": [], "expected_improvement": "Better"}}',
                f'{{"status": "needs_improvement", "feedback": "Score {50 + i*5}", "suggestions": [], "score": {50.0 + i*5}}}',
            ]
        )

    mock_llm_client.call.side_effect = responses

    loop = PECLoop(mock_llm_client, max_iterations=5, early_stop_threshold=2)

    def executor_fn(planner_output, state):
        return {"executed": True}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    # Should run all 5 iterations
    assert len(memory_entries) == 5

    # Verify max iterations reached
    assert final_feedback.status == "failed"
    assert "maximum iterations" in final_feedback.feedback.lower()


def test_pec_loop_immediate_failure(mock_llm_client, test_plan):
    """Test PEC loop handles immediate failure."""
    mock_llm_client.call.side_effect = [
        '{"reasoning": "Try something", "tool_calls": [], "expected_improvement": "Work"}',
        '{"status": "failed", "feedback": "Critical error occurred", "suggestions": ["Fix the bug"], "score": 0.0}',
    ]

    loop = PECLoop(mock_llm_client, max_iterations=5, early_stop_threshold=2)

    def executor_fn(planner_output, state):
        return {"error": "critical"}

    memory_entries, final_feedback = loop.run(test_plan, executor_fn, {})

    # Should stop immediately
    assert len(memory_entries) == 1

    # Verify failure
    assert final_feedback.status == "failed"
    assert "Critical error" in final_feedback.feedback


def test_branch_executor_with_pec_loop(mock_llm_client, test_plan, tmp_path):
    """Test BranchExecutor integration with PEC loop."""
    # Mock success on first iteration
    mock_llm_client.call.side_effect = [
        '{"reasoning": "Implement", "tool_calls": [], "expected_improvement": "Work"}',
        '{"status": "success", "feedback": "Done!", "suggestions": [], "score": 100.0}',
    ]

    executor = BranchExecutor(
        max_workers=1,
        llm_client=mock_llm_client,
        max_iterations=5,
        early_stop_threshold=2,
    )

    branch_config = BranchConfig(
        branch_id="branch_1",
        variant_params={"approach": "baseline"},
        initial_budget=BudgetAllocation(
            max_cost_usd=5.0, max_time_hours=0.5, max_iterations=5
        ),
        workspace_path=tmp_path / "workspace",
    )

    result = executor._execute_single_branch(branch_config, test_plan)

    assert result.branch_id == "branch_1"
    assert result.status == "success"
    assert result.iterations == 1
