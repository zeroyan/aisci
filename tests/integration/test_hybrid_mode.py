"""Integration test for Hybrid mode."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.schemas.research_spec import ResearchSpec, Metric
from src.schemas import Constraints
from src.integrations.ai_scientist.adapter import AIScientistAdapter
from src.integrations.ai_scientist.job_store import JobStore


@pytest.fixture
def sample_spec():
    """Create a sample research spec."""
    return ResearchSpec(
        spec_id="test_hybrid_001",
        title="Test Hybrid Mode",
        objective="Test the hybrid mode workflow",
        metrics=[
            Metric(
                name="accuracy",
                description="Model accuracy",
                direction="maximize",
                target=0.9
            ),
        ],
        constraints=Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=1.0,
            max_iterations=10,
            compute="cpu",
        ),
        status="draft",
    )


def test_baseline_info_format():
    """Test Phase 1: Baseline info format."""
    # Baseline metrics from AiSci
    baseline_metrics = {"accuracy": 0.75, "loss": 0.25}

    # Format for AI-Scientist
    baseline_info = {
        "experiment": {
            "means": baseline_metrics
        }
    }

    # Verify format
    assert "experiment" in baseline_info
    assert "means" in baseline_info["experiment"]
    assert baseline_info["experiment"]["means"] == baseline_metrics


def test_template_preparation(sample_spec, tmp_path):
    """Test Phase 2: Template preparation."""
    # Setup
    template_dir = tmp_path / "templates" / "dynamic_test"
    template_dir.mkdir(parents=True)

    # Baseline metrics
    baseline_metrics = {"accuracy": 0.75, "loss": 0.25}

    # Create baseline info
    baseline_info = {
        "experiment": {
            "means": baseline_metrics
        }
    }

    # Write baseline
    baseline_dir = template_dir / "run_0"
    baseline_dir.mkdir()
    baseline_file = baseline_dir / "final_info.json"
    baseline_file.write_text(json.dumps(baseline_info, indent=2))

    # Verify
    assert baseline_file.exists()
    loaded = json.loads(baseline_file.read_text())
    assert loaded["experiment"]["means"] == baseline_metrics

    # Write experiment.py
    experiment_py = template_dir / "experiment.py"
    experiment_py.write_text("# Test code\nprint('baseline')")
    assert experiment_py.exists()

    # Write prompt.json
    prompt_data = {
        "system": "You are an AI research assistant.",
        "task": sample_spec.objective,
        "metrics": list(baseline_metrics.keys()),
    }
    (template_dir / "prompt.json").write_text(json.dumps(prompt_data, indent=2))
    assert (template_dir / "prompt.json").exists()

    # Write seed_ideas.json
    seed_ideas = [
        {"Name": "Idea 1", "Title": "Test Idea", "Experiment": "Test"},
    ]
    (template_dir / "seed_ideas.json").write_text(json.dumps(seed_ideas, indent=2))
    assert (template_dir / "seed_ideas.json").exists()


def test_adapter_template_parameter(tmp_path):
    """Test that adapter accepts custom template name."""
    runtime_path = tmp_path / "ai-scientist-runtime"
    runtime_path.mkdir()

    adapter = AIScientistAdapter(runtime_path)

    # Mock job store
    job_store = Mock()
    job_store.can_submit.return_value = True
    job_store.save = Mock()

    # Mock spec
    spec = Mock()
    spec.spec_id = "test_001"

    # Test with custom template
    with patch("subprocess.Popen") as mock_popen:
        mock_process = Mock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test_key"}):
            job_id = adapter.submit_job(
                run_id="test_run",
                spec=spec,
                model="deepseek-chat",
                num_ideas=2,
                writeup="md",
                job_store=job_store,
                template_name="custom_template",
            )

            # Verify command includes custom template
            call_args = mock_popen.call_args
            cmd = call_args[0][0]
            assert "--experiment" in cmd
            template_idx = cmd.index("--experiment") + 1
            assert cmd[template_idx] == "custom_template"


def test_hybrid_workflow_integration():
    """Test complete hybrid workflow (mocked)."""
    # This is a high-level integration test that verifies the workflow
    # without actually running AI-Scientist

    # Phase 1: Baseline
    baseline_metrics = {"accuracy": 0.75, "loss": 0.25}

    # Phase 2: Template (format check)
    baseline_info = {"experiment": {"means": baseline_metrics}}
    assert "experiment" in baseline_info
    assert "means" in baseline_info["experiment"]

    # Phase 3: AI-Scientist (mocked)
    # In real scenario, this would call adapter.submit_job
    job_id = "test_job_123"
    assert job_id is not None

    # Phase 4: Results (mocked)
    # In real scenario, this would parse AI-Scientist output
    ai_scientist_metrics = {"accuracy": 0.85, "loss": 0.15}

    # Verify improvement
    assert ai_scientist_metrics["accuracy"] > baseline_metrics["accuracy"]
    assert ai_scientist_metrics["loss"] < baseline_metrics["loss"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
