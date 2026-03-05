"""Unit tests for SpecMapper."""

import json
from pathlib import Path

import pytest

from src.integrations.ai_scientist.spec_mapper import SpecMapper
from src.schemas.ai_scientist import TemplatePackage
from src.schemas.research_spec import ResearchSpec, Metric
from src.schemas import Constraints


@pytest.fixture
def sample_spec():
    """Create sample research spec."""
    return ResearchSpec(
        spec_id="test_spec_001",
        title="Test Research",
        objective="Test the AI-Scientist integration",
        metrics=[
            Metric(
                name="accuracy",
                description="Model accuracy",
                direction="maximize",
                target=0.9,
            ),
            Metric(
                name="loss",
                description="Model loss",
                direction="minimize",
                target=0.1,
            ),
        ],
        constraints=Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=1.0,
            max_iterations=10,
            compute="cpu",
        ),
        status="confirmed",
    )


@pytest.fixture
def temp_template_dir(tmp_path):
    """Create temporary template directory."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # Create generic template
    generic_dir = template_dir / "ai_toy_research_cn"
    generic_dir.mkdir()
    (generic_dir / "experiment.py").write_text("# Generic experiment")
    (generic_dir / "plot.py").write_text("# Generic plot")

    return template_dir


def test_spec_mapper_initialization(temp_template_dir):
    """Test SpecMapper initialization."""
    mapper = SpecMapper(temp_template_dir)
    assert mapper.template_dir == temp_template_dir


def test_map_to_template_package(temp_template_dir, sample_spec):
    """Test mapping ResearchSpec to TemplatePackage."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(
        spec=sample_spec,
        num_ideas=3,
        model="deepseek-chat",
        writeup="md",
    )

    assert isinstance(package, TemplatePackage)
    assert package.template_name == "dynamic_test_spec_001"
    assert package.prompt_json["task"] == sample_spec.objective
    assert len(package.seed_ideas_json) == 3
    assert package.runtime_args["model"] == "deepseek-chat"
    assert package.runtime_args["num_ideas"] == 3


def test_prompt_json_generation(temp_template_dir, sample_spec):
    """Test prompt.json generation from spec."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(sample_spec)

    prompt = package.prompt_json
    assert "system" in prompt
    assert "task" in prompt
    assert prompt["task"] == sample_spec.objective
    assert "metrics" in prompt
    assert "accuracy" in prompt["metrics"]
    assert "loss" in prompt["metrics"]


def test_seed_ideas_generation(temp_template_dir, sample_spec):
    """Test seed_ideas.json generation from spec."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(sample_spec, num_ideas=2)

    ideas = package.seed_ideas_json
    assert len(ideas) == 2
    assert ideas[0]["Name"] == "idea_1"
    assert ideas[0]["Title"] == "Test Research - Idea 1"
    assert ideas[0]["Experiment"] == sample_spec.objective


def test_generate_dynamic_template(temp_template_dir, sample_spec):
    """Test generating dynamic template directory."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(sample_spec)

    template_path = mapper.generate_dynamic_template(package)

    assert template_path.exists()
    assert (template_path / "prompt.json").exists()
    assert (template_path / "seed_ideas.json").exists()
    assert (template_path / "experiment.py").exists()
    assert (template_path / "plot.py").exists()


def test_generate_template_with_baseline(temp_template_dir, sample_spec):
    """Test generating template with baseline info."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(sample_spec)

    baseline_info = {
        "toy_ai_regression": {
            "means": {"accuracy": 0.75, "loss": 0.25}
        }
    }

    template_path = mapper.generate_dynamic_template(
        package,
        baseline_info=baseline_info,
    )

    assert (template_path / "run_0").exists()
    assert (template_path / "run_0" / "final_info.json").exists()

    # Verify baseline content
    baseline_content = json.loads(
        (template_path / "run_0" / "final_info.json").read_text()
    )
    assert baseline_content == baseline_info


def test_template_name_generation(temp_template_dir, sample_spec):
    """Test template name generation."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(sample_spec)

    assert package.template_name == f"dynamic_{sample_spec.spec_id}"


def test_runtime_args(temp_template_dir, sample_spec):
    """Test runtime arguments."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(
        sample_spec,
        num_ideas=5,
        model="ollama/qwen3",
        writeup="latex",
    )

    args = package.runtime_args
    assert args["model"] == "ollama/qwen3"
    assert args["writeup"] == "latex"
    assert args["num_ideas"] == 5


def test_template_cleanup(temp_template_dir, sample_spec):
    """Test template cleanup on regeneration."""
    mapper = SpecMapper(temp_template_dir)
    package = mapper.map_to_template_package(sample_spec)

    # Generate first time
    template_path1 = mapper.generate_dynamic_template(package)
    (template_path1 / "custom_file.txt").write_text("custom")

    # Generate again (should clean old files)
    template_path2 = mapper.generate_dynamic_template(package)

    assert template_path1 == template_path2
    assert not (template_path2 / "custom_file.txt").exists()


def test_fallback_to_generic_template(tmp_path, sample_spec):
    """Test fallback when ai_toy_research_cn doesn't exist."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # Create only generic_ai_research_cn
    generic_dir = template_dir / "generic_ai_research_cn"
    generic_dir.mkdir()
    (generic_dir / "experiment.py").write_text("# Generic")
    (generic_dir / "plot.py").write_text("# Plot")

    mapper = SpecMapper(template_dir)
    package = mapper.map_to_template_package(sample_spec)
    template_path = mapper.generate_dynamic_template(package)

    assert (template_path / "experiment.py").exists()
    assert (template_path / "plot.py").exists()


def test_placeholder_creation(tmp_path, sample_spec):
    """Test placeholder creation when no generic template exists."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    mapper = SpecMapper(template_dir)
    package = mapper.map_to_template_package(sample_spec)
    template_path = mapper.generate_dynamic_template(package)

    # Should create placeholders
    assert (template_path / "experiment.py").exists()
    assert (template_path / "plot.py").exists()
    assert "placeholder" in (template_path / "experiment.py").read_text()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
