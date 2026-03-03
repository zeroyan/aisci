"""Unit tests for FailureReportGenerator."""


import pytest

from src.orchestrator.failure_report import FailureReportGenerator
from src.schemas import PlanStep
from src.schemas.orchestrator import CriticFeedback, MemoryEntry, PlannerOutput
from src.schemas.research_spec import ExperimentPlan


@pytest.fixture
def test_plan():
    """Create test experiment plan."""
    return ExperimentPlan(
        plan_id="test_plan_123",
        spec_id="test_spec",
        title="Test Experiment Plan",
        steps=[
            PlanStep(
                step_id="step_1",
                description="Test step",
                expected_output="Test output",
            )
        ],
        method_summary="Test method summary",
        evaluation_protocol="Test evaluation protocol",
    )


@pytest.fixture
def memory_entries():
    """Create test memory entries."""
    return [
        MemoryEntry(
            iteration=1,
            planner_output=PlannerOutput(
                reasoning="First attempt",
                tool_calls=[{"tool": "write_code", "args": {}}],
                expected_improvement="Baseline",
            ),
            execution_result={"status": "executed"},
            critic_feedback=CriticFeedback(
                status="needs_improvement",
                feedback="Accuracy too low",
                suggestions=["Try different approach"],
                score=40.0,
            ),
        ),
        MemoryEntry(
            iteration=2,
            planner_output=PlannerOutput(
                reasoning="Second attempt",
                tool_calls=[{"tool": "tune_params", "args": {}}],
                expected_improvement="Better params",
            ),
            execution_result={"status": "executed"},
            critic_feedback=CriticFeedback(
                status="needs_improvement",
                feedback="Still not good enough",
                suggestions=["Try another method"],
                score=45.0,
            ),
        ),
    ]


@pytest.fixture
def final_feedback():
    """Create final feedback."""
    return CriticFeedback(
        status="failed",
        feedback="Early stop: No improvement for 2 consecutive iterations",
        suggestions=["Review experiment design", "Check baseline"],
        score=45.0,
    )


def test_generate_report_creates_file(test_plan, memory_entries, final_feedback, tmp_path):
    """Test that report file is created."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    assert output_path.exists()


def test_generate_report_contains_plan_info(
    test_plan, memory_entries, final_feedback, tmp_path
):
    """Test that report contains plan information."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    content = output_path.read_text()
    assert "test_plan_123" in content
    assert "Test Experiment Plan" in content


def test_generate_report_contains_summary(
    test_plan, memory_entries, final_feedback, tmp_path
):
    """Test that report contains summary section."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    content = output_path.read_text()
    assert "## Summary" in content
    assert "failed" in content
    assert "45.00" in content
    assert "2" in content  # Total iterations


def test_generate_report_contains_attempt_history(
    test_plan, memory_entries, final_feedback, tmp_path
):
    """Test that report contains attempt history."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    content = output_path.read_text()
    assert "## Attempt History" in content
    assert "### Iteration 1" in content
    assert "### Iteration 2" in content
    assert "First attempt" in content
    assert "Second attempt" in content


def test_generate_report_contains_suggestions(
    test_plan, memory_entries, final_feedback, tmp_path
):
    """Test that report contains suggestions."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    content = output_path.read_text()
    assert "Try different approach" in content
    assert "Try another method" in content
    assert "Review experiment design" in content


def test_generate_report_contains_recommendations(
    test_plan, memory_entries, final_feedback, tmp_path
):
    """Test that report contains recommendations section."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    content = output_path.read_text()
    assert "## Recommendations" in content
    assert "Review experiment design" in content
    assert "Check baseline" in content


def test_generate_report_creates_parent_directory(
    test_plan, memory_entries, final_feedback, tmp_path
):
    """Test that parent directory is created if it doesn't exist."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "nested" / "dir" / "failure_report.md"

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    assert output_path.exists()
    assert output_path.parent.exists()


def test_generate_report_empty_suggestions(test_plan, memory_entries, tmp_path):
    """Test report generation with empty suggestions."""
    generator = FailureReportGenerator()
    output_path = tmp_path / "failure_report.md"

    final_feedback = CriticFeedback(
        status="failed",
        feedback="Failed",
        suggestions=[],
        score=0.0,
    )

    generator.generate_report(test_plan, memory_entries, final_feedback, output_path)

    content = output_path.read_text()
    # Should have default recommendations
    assert "Review experiment plan" in content
    assert "Consider alternative approaches" in content
