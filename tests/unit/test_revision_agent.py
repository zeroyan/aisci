"""Unit tests for RevisionAgent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

from src.agents.plan.revision_agent import RevisionAgent
from src.llm.client import LLMClient, LLMConfig
from src.schemas import CostUsage, PlanStep
from src.schemas.research_spec import ExperimentPlan, TechnicalApproach
from src.schemas.plan_serializer import PlanSerializer


def test_revision_agent_generates_suggestions(tmp_path: Path) -> None:
    """RevisionAgent generates revision suggestions from report."""
    # Mock LLM
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()

    suggestions = """## Revision Suggestions

1. **Keep**: The contrastive learning approach showed promising results
2. **Revise**: Increase batch size from 32 to 128 for better convergence
3. **Add**: Implement data augmentation strategies
4. **Remove**: Step 2 (manual feature engineering) is no longer needed
"""
    mock_llm.complete = Mock(return_value=(suggestions, CostUsage()))

    # Create test plan
    plan = ExperimentPlan(
        plan_id="plan-test",
        spec_id="spec-test",
        version=1,
        title="Test Plan",
        method_summary="Test method",
        technical_approach=TechnicalApproach(framework="PyTorch"),
        evaluation_protocol="Test eval",
        steps=[
            PlanStep(step_id="s1", description="Step 1", expected_output="output1"),
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # Create test report
    report_path = tmp_path / "report.md"
    report_path.write_text("# Experiment Report\n\nResults: accuracy=0.85")

    # Create agent and generate suggestions
    agent = RevisionAgent(llm_client=mock_llm)
    result = agent.suggest_revisions(plan, report_path)

    # Assertions
    assert "Revision Suggestions" in result
    assert "Keep" in result or "Revise" in result or "Add" in result
    mock_llm.complete.assert_called_once()


def test_revision_agent_applies_revisions() -> None:
    """RevisionAgent applies revisions and increments version."""
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()

    plan = ExperimentPlan(
        plan_id="plan-test",
        spec_id="spec-test",
        version=1,
        title="Test Plan",
        method_summary="Test method",
        technical_approach=TechnicalApproach(framework="PyTorch"),
        evaluation_protocol="Test eval",
        steps=[
            PlanStep(step_id="s1", description="Step 1", expected_output="output1"),
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    agent = RevisionAgent(llm_client=mock_llm)

    # Apply revisions
    updated_plan = agent.apply_revisions(
        plan=plan,
        revision_summary="Increased batch size to 128",
        revised_by="human",
    )

    # Assertions
    assert updated_plan.version == 2
    assert len(updated_plan.revision_history) == 1
    assert updated_plan.revision_history[0].version == 2
    assert updated_plan.revision_history[0].revised_by == "human"
    assert "batch size" in updated_plan.revision_history[0].summary


def test_revision_agent_appends_to_plan_file(tmp_path: Path) -> None:
    """RevisionAgent appends suggestions to plan.md file."""
    # Mock LLM
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()

    suggestions = "## Suggestions\n\n1. Improve data preprocessing"
    mock_llm.complete = Mock(return_value=(suggestions, CostUsage()))

    # Create test plan
    plan = ExperimentPlan(
        plan_id="plan-test",
        spec_id="spec-test",
        version=1,
        title="Test Plan",
        method_summary="Test method",
        technical_approach=TechnicalApproach(framework="PyTorch"),
        evaluation_protocol="Test eval",
        steps=[
            PlanStep(step_id="s1", description="Step 1", expected_output="output1"),
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # Save plan to file
    plan_path = tmp_path / "plan.md"
    md_content = PlanSerializer.to_markdown(plan)
    plan_path.write_text(md_content)

    # Create report
    report_path = tmp_path / "report.md"
    report_path.write_text("# Report\n\nResults: good")

    # Create agent and revise
    agent = RevisionAgent(llm_client=mock_llm)
    agent.revise_plan_file(
        plan_path=plan_path,
        report_path=report_path,
        append_suggestions=True,
    )

    # Verify suggestions were appended
    updated_content = plan_path.read_text()
    assert "## 修订建议" in updated_content
    assert "Improve data preprocessing" in updated_content


def test_plan_serializer_preserves_revision_history() -> None:
    """PlanSerializer correctly serializes and deserializes revision history."""
    plan = ExperimentPlan(
        plan_id="plan-test",
        spec_id="spec-test",
        version=3,
        title="Test Plan",
        method_summary="Test method",
        technical_approach=TechnicalApproach(framework="PyTorch"),
        evaluation_protocol="Test eval",
        steps=[
            PlanStep(step_id="s1", description="Step 1", expected_output="output1"),
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        revision_history=[
            {
                "version": 2,
                "revised_at": datetime(2026, 3, 1, 10, 0, 0),
                "revised_by": "human",
                "summary": "First revision",
            },
            {
                "version": 3,
                "revised_at": datetime(2026, 3, 2, 10, 0, 0),
                "revised_by": "ai",
                "summary": "Second revision",
            },
        ],
    )

    # Serialize
    md_content = PlanSerializer.to_markdown(plan)

    # Verify revision history in markdown
    assert "## 修订历史" in md_content
    assert "human" in md_content
    assert "ai" in md_content
    assert "First revision" in md_content
    assert "Second revision" in md_content

    # Deserialize
    restored_plan = PlanSerializer.from_markdown(md_content)

    # Verify revision history preserved
    assert restored_plan.version == 3
    assert len(restored_plan.revision_history) == 2
    assert restored_plan.revision_history[0].version == 2
    assert restored_plan.revision_history[0].revised_by == "human"
    assert restored_plan.revision_history[1].version == 3
    assert restored_plan.revision_history[1].revised_by == "ai"
