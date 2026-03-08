"""Tests for ReadinessChecker."""

from datetime import datetime

import pytest

from src.agents.project_generator.readiness_checker import ReadinessChecker
from src.schemas.research_spec import Constraints, Metric, ResearchSpec


@pytest.fixture
def valid_spec():
    """Create a valid ResearchSpec for testing."""
    return ResearchSpec(
        spec_id="test_spec_001",
        title="Test Research Spec",
        objective="Test objective",
        hypothesis=["Test hypothesis"],
        metrics=[
            Metric(name="accuracy", direction="maximize", target=0.9),
            Metric(name="latency", direction="minimize", target=100.0),
        ],
        constraints=Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=24.0,
            max_iterations=10,
            compute_type="cpu",
        ),
        status="draft",
        created_at=datetime.now(),
        evidence_metadata={
            "baseline_method": "Test Baseline",
            "baseline_reference": "https://example.com/paper",
            "required_packages": ["numpy", "torch"],
            "failure_criteria": ["accuracy < 0.5"],
        },
    )


def test_check_valid_spec(valid_spec):
    """Test validation of a valid spec."""
    checker = ReadinessChecker()
    report = checker.check(valid_spec)

    assert report.is_ready
    assert len([i for i in report.issues if i.severity == "error"]) == 0


def test_check_vague_metrics():
    """Test warning for vague metric names."""
    spec = ResearchSpec(
        spec_id="test_spec_003",
        title="Test",
        objective="Test",
        metrics=[
            Metric(name="better_performance", direction="maximize", target=1.0),
        ],
        constraints=Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=24.0,
            max_iterations=10,
            compute_type="cpu",
        ),
        status="draft",
    )

    checker = ReadinessChecker()
    report = checker.check(spec)

    assert report.is_ready  # Warnings don't block
    assert any(
        i.category == "metrics"
        and i.severity == "warning"
        and "vague" in i.message.lower()
        for i in report.issues
    )


def test_check_no_baseline(valid_spec):
    """Test warning when no baseline specified."""
    spec = valid_spec.model_copy(update={"evidence_metadata": {}})

    checker = ReadinessChecker()
    report = checker.check(spec)

    assert report.is_ready  # Warnings don't block
    # No baseline warning expected since evidence_metadata is empty


def test_check_low_budget(valid_spec):
    """Test warning for unrealistically low budget."""
    spec = valid_spec.model_copy(
        update={
            "constraints": valid_spec.constraints.model_copy(
                update={"max_budget_usd": 0.5}
            )
        }
    )

    checker = ReadinessChecker()
    report = checker.check(spec)

    assert report.is_ready  # Warnings don't block
    assert any(
        i.category == "budget"
        and i.severity == "warning"
        and "too low" in i.message.lower()
        for i in report.issues
    )


def test_check_high_budget(valid_spec):
    """Test warning for very high budget."""
    spec = valid_spec.model_copy(
        update={
            "constraints": valid_spec.constraints.model_copy(
                update={"max_budget_usd": 15000.0}
            )
        }
    )

    checker = ReadinessChecker()
    report = checker.check(spec)

    assert report.is_ready  # Warnings don't block
    assert any(
        i.category == "budget"
        and i.severity == "warning"
        and "very high" in i.message.lower()
        for i in report.issues
    )


def test_check_no_failure_criteria(valid_spec):
    """Test warning when no failure criteria defined."""
    metadata = valid_spec.evidence_metadata.copy()
    metadata.pop("failure_criteria")
    spec = valid_spec.model_copy(update={"evidence_metadata": metadata})

    checker = ReadinessChecker()
    report = checker.check(spec)

    assert report.is_ready  # Warnings don't block
    assert any(
        i.category == "failure_criteria" and i.severity == "warning"
        for i in report.issues
    )


def test_check_baseline_from_project_generator_metadata_aliases():
    """baseline_references/baseline_paper_references should be recognized."""
    spec = ResearchSpec(
        spec_id="test_spec_004",
        title="Test",
        objective="Test",
        metrics=[Metric(name="accuracy", direction="maximize", target=0.8)],
        constraints=Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=24.0,
            max_iterations=10,
            compute_type="cpu",
        ),
        status="draft",
        evidence_metadata={
            "baseline_references": ["BERT-base"],
            "baseline_paper_references": ["arxiv:1810.04805"],
            "failure_criteria": ["accuracy < 0.5"],
        },
    )

    checker = ReadinessChecker()
    report = checker.check(spec)

    assert not any(i.category == "baseline" for i in report.issues)
