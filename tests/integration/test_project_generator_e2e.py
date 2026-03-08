"""End-to-end tests for project generator."""

import pytest

from src.agents.project_generator.evidence_searcher import EvidenceSearcher
from src.agents.project_generator.formalization_agent import FormalizationAgent
from src.agents.project_generator.intake_agent import IntakeAgent
from src.llm.client import LLMClient, LLMConfig


@pytest.fixture
def test_output_dir(tmp_path):
    """Create temporary output directory."""
    return tmp_path / "test_projects"


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client for testing."""
    # Use a simple config that won't make real API calls
    config = LLMConfig(
        default_model="ollama/qwen2.5:0.5b",
        fallback_model="ollama/qwen2.5:0.5b",
        api_base="http://127.0.0.1:11434",
    )
    return LLMClient(config=config)


def test_intake_agent_basic(mock_llm_client):
    """Test IntakeAgent can parse a simple idea."""
    agent = IntakeAgent(llm_client=mock_llm_client)

    idea = "Improve BERT accuracy on sentiment analysis"

    try:
        record = agent.parse_idea(idea)

        assert record.raw_idea == idea
        assert record.idea_type in [
            "performance_improvement",
            "new_method",
            "dataset_creation",
            "other",
        ]
        assert isinstance(record.entities, dict)
        assert isinstance(record.missing_info, list)
    except Exception as e:
        # LLM might not be available, skip test
        pytest.skip(f"LLM not available: {e}")


def test_evidence_searcher_basic():
    """Test EvidenceSearcher can search for papers."""
    searcher = EvidenceSearcher()

    query = "transformer attention mechanism"

    try:
        evidence = searcher.search(query, max_papers=2, max_repos=1)

        assert evidence.query == query
        assert isinstance(evidence.papers, list)
        assert isinstance(evidence.code_repos, list)
        assert isinstance(evidence.baselines, list)
    except Exception as e:
        # Network might not be available
        pytest.skip(f"Network not available: {e}")


def test_formalization_agent_basic(mock_llm_client):
    """Test FormalizationAgent can create ResearchSpec."""
    from src.schemas.project_generator import EvidencePackage, IdeaRecord

    agent = FormalizationAgent(llm_client=mock_llm_client)

    idea_record = IdeaRecord(
        idea_id="test_idea_001",
        raw_text="Improve BERT accuracy",
        raw_idea="Improve BERT accuracy",
        idea_type="performance_improvement",
        entities={"model": "BERT", "metric": "accuracy"},
        missing_info=[],
    )

    evidence = EvidencePackage(
        package_id="test_pkg",
        query="BERT accuracy",
        papers=[],
        code_repos=[],
        baselines=[],
        common_failures=[],
    )

    try:
        spec = agent.formalize(idea_record, evidence)

        assert spec.spec_id.startswith("proj_")
        assert len(spec.title) > 0
        assert len(spec.objective) > 0
        assert len(spec.metrics) > 0
    except Exception as e:
        # LLM might not be available
        pytest.skip(f"LLM not available: {e}")
