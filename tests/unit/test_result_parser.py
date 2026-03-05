"""Unit tests for ResultParser."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.integrations.ai_scientist.result_parser import ResultParser
from src.schemas.experiment_result import ExperimentResult


@pytest.fixture
def temp_result_dir(tmp_path):
    """Create temporary result directory with sample data."""
    result_dir = tmp_path / "results" / "test_template"
    idea_dir = result_dir / "idea_001"
    idea_dir.mkdir(parents=True)

    # Create report.md
    (idea_dir / "report.md").write_text("# Test Report\n\nThis is a test report.")

    # Create final_info.json
    final_info = {
        "accuracy": 0.85,
        "loss": 0.15,
        "experiment": {"means": {"accuracy": 0.85}},
    }
    (idea_dir / "final_info.json").write_text(json.dumps(final_info))

    # Create plots directory
    plots_dir = idea_dir / "plots"
    plots_dir.mkdir()
    (plots_dir / "plot1.png").write_text("fake png data")

    # Create code directory
    code_dir = idea_dir / "code"
    code_dir.mkdir()
    (code_dir / "experiment.py").write_text("# Test code")

    return result_dir


def test_result_parser_initialization(temp_result_dir):
    """Test ResultParser initialization."""
    parser = ResultParser(temp_result_dir)
    assert parser.result_dir == temp_result_dir


def test_parse_result_dir(temp_result_dir):
    """Test parsing result directory."""
    parser = ResultParser(temp_result_dir)
    result = parser.parse_result_dir()

    assert result is not None
    assert result["idea_name"] == "idea_001"
    assert "report" in result
    assert "final_info" in result
    assert len(result["plots"]) == 1
    assert len(result["code"]) == 1


def test_extract_report(temp_result_dir):
    """Test extracting report content."""
    parser = ResultParser(temp_result_dir)
    result = parser.parse_result_dir()

    assert result["report"] is not None
    assert "Test Report" in result["report"]


def test_extract_final_info(temp_result_dir):
    """Test extracting final_info.json."""
    parser = ResultParser(temp_result_dir)
    result = parser.parse_result_dir()

    assert result["final_info"] is not None
    assert result["final_info"]["accuracy"] == 0.85


def test_extract_plots(temp_result_dir):
    """Test extracting plot files."""
    parser = ResultParser(temp_result_dir)
    result = parser.parse_result_dir()

    assert len(result["plots"]) == 1
    assert "plot1.png" in result["plots"][0]


def test_extract_code(temp_result_dir):
    """Test extracting code files."""
    parser = ResultParser(temp_result_dir)
    result = parser.parse_result_dir()

    assert len(result["code"]) == 1
    assert "experiment.py" in result["code"][0]


def test_extract_artifacts(temp_result_dir):
    """Test extracting all artifacts."""
    parser = ResultParser(temp_result_dir)
    artifacts = parser.extract_artifacts()

    assert len(artifacts) > 0
    assert any("report.md" in a for a in artifacts)


def test_to_experiment_result(temp_result_dir):
    """Test converting to ExperimentResult."""
    parser = ResultParser(temp_result_dir)
    start_time = datetime.now()
    end_time = datetime.now()

    result = parser.to_experiment_result(
        run_id="test_run",
        job_id="test_job",
        template_name="test_template",
        start_time=start_time,
        end_time=end_time,
    )

    assert result is not None
    assert result.run_id == "test_run"
    assert result.engine == "ai-scientist"
    assert result.status == "success"
    assert len(result.metrics) > 0


def test_parse_empty_directory(tmp_path):
    """Test parsing empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    parser = ResultParser(empty_dir)
    result = parser.parse_result_dir()

    assert result is None


def test_to_experiment_result_no_results(tmp_path):
    """Test converting when no results exist."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    parser = ResultParser(empty_dir)
    result = parser.to_experiment_result(
        run_id="test_run",
        job_id="test_job",
        template_name="test_template",
        start_time=datetime.now(),
        end_time=datetime.now(),
    )

    assert result is None


def test_copy_artifacts_to_run_dir(temp_result_dir, tmp_path):
    """Test copying artifacts to run directory."""
    parser = ResultParser(temp_result_dir)
    runs_dir = tmp_path / "runs"

    artifacts_dir = parser.copy_artifacts_to_run_dir(
        run_id="test_run",
        job_id="test_job",
        runs_dir=runs_dir,
    )

    assert artifacts_dir.exists()
    assert (artifacts_dir / "report.md").exists()
    assert (artifacts_dir / "final_info.json").exists()
    assert (artifacts_dir / "plots").exists()
    assert (artifacts_dir / "code").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
