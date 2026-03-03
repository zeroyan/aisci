"""Unit tests for BranchOrchestrator."""

from unittest.mock import MagicMock

import pytest

from src.llm.client import LLMClient
from src.orchestrator.branch_orchestrator import BranchOrchestrator
from src.orchestrator.config import OrchestratorConfig
from src.schemas.research_spec import ExperimentPlan, ResearchSpec


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    return MagicMock(spec=LLMClient)


@pytest.fixture
def orchestrator_config():
    """Create test orchestrator configuration."""
    return OrchestratorConfig.default()


@pytest.fixture
def test_spec():
    """Create minimal test research spec."""
    from src.schemas import Constraints, Metric

    return ResearchSpec(
        spec_id="test_spec",
        title="Test Spec",
        objective="Test objective",
        metrics=[Metric(name="accuracy", direction="maximize")],
        constraints=Constraints(
            max_budget_usd=10.0, max_runtime_hours=1.0, max_iterations=5
        ),
        status="confirmed",
    )


@pytest.fixture
def test_plan():
    """Create minimal test experiment plan."""
    from src.schemas import Baseline, PlanStep

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


def test_orchestrator_initialization(orchestrator_config, mock_llm_client):
    """Test orchestrator initialization."""
    orchestrator = BranchOrchestrator(orchestrator_config, mock_llm_client)

    assert orchestrator.config == orchestrator_config
    assert orchestrator.variant_generator is not None
    assert orchestrator.workspace_manager is not None


def test_create_branch_configs(orchestrator_config, mock_llm_client, test_plan, tmp_path):
    """Test branch configuration creation."""
    orchestrator = BranchOrchestrator(orchestrator_config, mock_llm_client)

    # Generate variants
    variants = orchestrator.variant_generator.generate_variants(test_plan, num_branches=3)

    # Create branch configs
    configs = orchestrator._create_branch_configs(
        run_id="test_run",
        runs_dir=tmp_path,
        variants=variants,
    )

    # Verify
    assert len(configs) == 3
    assert configs[0].branch_id == "branch_001"
    assert configs[1].branch_id == "branch_002"
    assert configs[2].branch_id == "branch_003"

    # Verify workspaces created
    for config in configs:
        assert config.workspace_path.exists()
        assert (config.workspace_path / "code").exists()
        assert (config.workspace_path / "data").exists()
        assert (config.workspace_path / "results").exists()


def test_orchestrator_run_validation(orchestrator_config, mock_llm_client, test_spec, test_plan, tmp_path):
    """Test orchestrator run with invalid configuration."""
    # Create config with invalid num_branches
    invalid_config = orchestrator_config.model_copy(
        update={
            "orchestrator": orchestrator_config.orchestrator.model_copy(
                update={"num_branches": 5}
            )
        }
    )

    # Should raise ValueError during initialization (from BranchExecutor)
    with pytest.raises(ValueError, match="max_workers must be <= 3"):
        BranchOrchestrator(invalid_config, mock_llm_client)
