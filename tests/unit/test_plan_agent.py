"""Unit tests for PlanAgent with mocked LLM and knowledge store."""

from __future__ import annotations

from unittest.mock import Mock

from src.agents.plan.plan_agent import PlanAgent
from src.knowledge.store import KnowledgeStore
from src.llm.client import LLMClient, LLMConfig
from src.schemas import CostUsage, Metric, Constraints
from src.schemas.knowledge import KnowledgeEntry, KnowledgeEntryMeta
from src.schemas.research_spec import ResearchSpec
from src.schemas.plan_serializer import PlanSerializer


def test_plan_agent_generates_valid_plan() -> None:
    """PlanAgent generates a valid ExperimentPlan from ResearchSpec."""
    # Mock LLM
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()

    # Mock LLM response with valid JSON
    llm_response = """{
        "method_summary": "Implement contrastive learning baseline",
        "framework": "PyTorch",
        "baseline_methods": ["SimCLR", "MoCo"],
        "key_references": ["Chen et al. 2020"],
        "evaluation_protocol": "Measure accuracy on test set",
        "steps": [
            {"step_id": "step-01", "description": "Setup environment", "expected_output": "Environment ready"},
            {"step_id": "step-02", "description": "Implement model", "expected_output": "model.py"},
            {"step_id": "step-03", "description": "Run training", "expected_output": "metrics.json"}
        ]
    }"""
    mock_llm.complete = Mock(return_value=(llm_response, CostUsage()))

    # Mock knowledge store
    mock_knowledge = Mock(spec=KnowledgeStore)
    mock_knowledge.search = Mock(return_value=[
        KnowledgeEntry(
            meta=KnowledgeEntryMeta(
                type="web_article",
                title="Contrastive Learning Overview",
                source_url="https://example.com",
                keywords=["contrastive", "learning"],
                status="ok",
                layer="global",
            ),
            summary="Contrastive learning is a self-supervised learning technique...",
        )
    ])

    # Create agent
    agent = PlanAgent(llm_client=mock_llm, knowledge_store=mock_knowledge)

    # Create test spec
    spec = ResearchSpec(
        spec_id="test_spec",
        title="Contrastive Learning Experiment",
        objective="Implement and evaluate contrastive learning baseline",
        metrics=[Metric(name="accuracy", direction="maximize", target=0.9)],
        constraints=Constraints(
            max_budget_usd=10.0,
            max_runtime_hours=1.0,
            max_iterations=5,
        ),
        status="confirmed",
    )

    # Generate plan
    plan = agent.generate(spec, run_id="test_run")

    # Assertions
    assert plan.spec_id == "test_spec"
    assert plan.version == 1
    assert "contrastive learning" in plan.method_summary.lower()
    assert plan.technical_approach.framework == "PyTorch"
    assert "SimCLR" in plan.technical_approach.baseline_methods
    assert len(plan.steps) == 3
    assert plan.steps[0].step_id == "step-01"

    # Verify knowledge store was called
    mock_knowledge.search.assert_called_once()

    # Verify LLM was called with knowledge context
    call_args = mock_llm.complete.call_args
    assert call_args is not None
    prompt = call_args[1]["messages"][0]["content"]
    assert "Contrastive Learning Overview" in prompt


def test_plan_serializer_roundtrip() -> None:
    """PlanSerializer can serialize and deserialize ExperimentPlan."""
    # Mock LLM and knowledge
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()
    llm_response = """{
        "method_summary": "Test method",
        "framework": "Python",
        "evaluation_protocol": "Test eval",
        "steps": [
            {"step_id": "s1", "description": "Step 1", "expected_output": "output1"}
        ]
    }"""
    mock_llm.complete = Mock(return_value=(llm_response, CostUsage()))

    mock_knowledge = Mock(spec=KnowledgeStore)
    mock_knowledge.search = Mock(return_value=[])

    agent = PlanAgent(llm_client=mock_llm, knowledge_store=mock_knowledge)

    spec = ResearchSpec(
        spec_id="test_spec",
        title="Test",
        objective="Test objective",
        metrics=[Metric(name="accuracy", direction="maximize", target=0.9)],
        constraints=Constraints(
            max_budget_usd=10.0,
            max_runtime_hours=1.0,
            max_iterations=5,
        ),
        status="confirmed",
    )

    # Generate plan
    original_plan = agent.generate(spec)

    # Serialize to markdown
    md_content = PlanSerializer.to_markdown(original_plan)

    # Verify markdown structure
    assert "---" in md_content  # YAML front-matter
    assert "plan_id:" in md_content
    assert "# 实验方案" in md_content
    assert "## 方法摘要" in md_content
    assert "## 技术路线" in md_content
    assert "## 评估指标" in md_content
    assert "## 实验步骤" in md_content
    assert "<!-- PLAN_JSON" in md_content

    # Deserialize back
    restored_plan = PlanSerializer.from_markdown(md_content)

    # Verify roundtrip
    assert restored_plan.plan_id == original_plan.plan_id
    assert restored_plan.spec_id == original_plan.spec_id
    assert restored_plan.version == original_plan.version
    assert restored_plan.method_summary == original_plan.method_summary
    assert len(restored_plan.steps) == len(original_plan.steps)


def test_plan_agent_handles_llm_parse_error() -> None:
    """PlanAgent handles LLM response parse errors gracefully."""
    # Mock LLM with invalid JSON response
    mock_llm = Mock(spec=LLMClient)
    mock_llm.config = LLMConfig()
    mock_llm.complete = Mock(return_value=("Invalid JSON response", CostUsage()))

    mock_knowledge = Mock(spec=KnowledgeStore)
    mock_knowledge.search = Mock(return_value=[])

    agent = PlanAgent(llm_client=mock_llm, knowledge_store=mock_knowledge)

    spec = ResearchSpec(
        spec_id="test_spec",
        title="Test",
        objective="Test objective",
        metrics=[Metric(name="accuracy", direction="maximize", target=0.9)],
        constraints=Constraints(
            max_budget_usd=10.0,
            max_runtime_hours=1.0,
            max_iterations=5,
        ),
        status="confirmed",
    )

    # Should not raise, should return fallback plan
    plan = agent.generate(spec)

    assert plan.spec_id == "test_spec"
    assert plan.method_summary == "Implement baseline experiment"
    assert len(plan.steps) >= 2  # Fallback has at least 2 steps
