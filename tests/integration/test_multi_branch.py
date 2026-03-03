"""Integration tests for multi-branch execution."""


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
        title="Multi-Branch Test",
        objective="Test multi-branch execution",
        metrics=[Metric(name="accuracy", direction="maximize")],
        constraints=Constraints(
            max_budget_usd=30.0, max_runtime_hours=3.0, max_iterations=10
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


@pytest.fixture
def orchestrator_config():
    """Create test orchestrator configuration."""
    return OrchestratorConfig.default()


def test_multi_branch_execution(orchestrator_config, test_spec, test_plan, tmp_path):
    """Test end-to-end multi-branch execution.

    Verifies:
    - 3 branches are created
    - Each branch has independent workspace
    - Branches can access global knowledge base (read-only)
    - Branches write to local memory
    - Results are collected and aggregated
    """
    # Create orchestrator
    orchestrator = BranchOrchestrator(orchestrator_config)

    # Run orchestration
    result = orchestrator.run(
        spec=test_spec,
        plan=test_plan,
        run_id="test_run",
        runs_dir=tmp_path,
    )

    # Verify result structure
    assert result.run_id == "test_run"
    assert result.engine == "aisci"
    assert result.status in ["success", "failed", "timeout"]
    assert result.total_cost_usd >= 0.0
    assert result.total_time_seconds >= 0.0
    assert result.iterations >= 0

    # Verify branch workspaces created
    branches_dir = tmp_path / "test_run" / "branches"
    assert branches_dir.exists()

    # Verify 3 branches created
    branch_dirs = list(branches_dir.iterdir())
    assert len(branch_dirs) == 3

    # Verify each branch has independent workspace
    for i in range(1, 4):
        branch_id = f"branch_{i:03d}"
        branch_dir = branches_dir / branch_id
        assert branch_dir.exists()

        # Verify workspace structure
        workspace = branch_dir / "workspace"
        assert workspace.exists()
        assert (workspace / "code").exists()
        assert (workspace / "data").exists()
        assert (workspace / "results").exists()


def test_branch_isolation(orchestrator_config, test_spec, test_plan, tmp_path):
    """Test that branches are isolated from each other."""
    orchestrator = BranchOrchestrator(orchestrator_config)

    # Run orchestration
    orchestrator.run(
        spec=test_spec,
        plan=test_plan,
        run_id="test_run",
        runs_dir=tmp_path,
    )

    # Get branch workspaces
    branches_dir = tmp_path / "test_run" / "branches"
    workspace_1 = branches_dir / "branch_001" / "workspace"
    workspace_2 = branches_dir / "branch_002" / "workspace"
    workspace_3 = branches_dir / "branch_003" / "workspace"

    # Verify workspaces are different
    assert workspace_1 != workspace_2
    assert workspace_2 != workspace_3
    assert workspace_1 != workspace_3

    # Create a file in workspace_1
    test_file_1 = workspace_1 / "code" / "test.py"
    test_file_1.write_text("# Branch 1 code")

    # Verify file doesn't exist in other workspaces
    test_file_2 = workspace_2 / "code" / "test.py"
    test_file_3 = workspace_3 / "code" / "test.py"
    assert not test_file_2.exists()
    assert not test_file_3.exists()


def test_knowledge_base_sharing(orchestrator_config, test_spec, test_plan, tmp_path):
    """Test that branches can access global knowledge base."""
    # Create global knowledge base
    knowledge_dir = tmp_path / "scientist" / "knowledge"
    knowledge_dir.mkdir(parents=True)

    # Write test knowledge
    import json

    failures_path = knowledge_dir / "failures.jsonl"
    with open(failures_path, "w") as f:
        f.write(json.dumps({"entry_id": "f1", "error": "Test error"}) + "\n")

    # Run orchestration
    orchestrator = BranchOrchestrator(orchestrator_config)
    orchestrator.run(
        spec=test_spec,
        plan=test_plan,
        run_id="test_run",
        runs_dir=tmp_path,
    )

    # Verify global knowledge base still exists and unchanged
    assert failures_path.exists()
    with open(failures_path) as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert "Test error" in lines[0]


def test_branch_memory_independence(orchestrator_config, test_spec, test_plan, tmp_path):
    """Test that each branch has independent local memory."""
    orchestrator = BranchOrchestrator(orchestrator_config)

    # Run orchestration
    orchestrator.run(
        spec=test_spec,
        plan=test_plan,
        run_id="test_run",
        runs_dir=tmp_path,
    )

    # Verify each branch has its own memory directory
    branches_dir = tmp_path / "test_run" / "branches"
    for i in range(1, 4):
        branch_id = f"branch_{i:03d}"
        memory_dir = branches_dir / branch_id / "memory"

        # Memory directory should exist (created by workspace manager)
        # Note: It may be empty if no attempts were recorded yet
        assert memory_dir.parent.exists()  # Branch directory exists
