"""Maps ResearchSpec to AI-Scientist template package."""

from pathlib import Path
from typing import Optional

from src.schemas.ai_scientist import TemplatePackage
from src.schemas.research_spec import ResearchSpec


class SpecMapper:
    """Maps ResearchSpec to AI-Scientist TemplatePackage."""

    def __init__(self, template_dir: Path):
        """Initialize mapper.

        Args:
            template_dir: Path to templates directory
        """
        self.template_dir = template_dir

    def map_to_template_package(
        self,
        spec: ResearchSpec,
        num_ideas: int = 2,
        model: str = "ollama/qwen3",
        writeup: str = "md",
    ) -> TemplatePackage:
        """Map ResearchSpec to TemplatePackage.

        Args:
            spec: Research specification
            num_ideas: Number of ideas to generate
            model: Model to use
            writeup: Writeup format

        Returns:
            Template package
        """
        template_name = f"dynamic_{spec.spec_id}"

        # Build prompt from spec
        prompt_json = {
            "system": "You are an AI research assistant helping to conduct scientific experiments.",
            "task": spec.objective,
            "task_description": spec.objective,
            "constraints": spec.constraints.model_dump(mode="json") if spec.constraints else {},
            "metrics": [m.name for m in spec.metrics] if spec.metrics else [],
        }

        # Generate seed ideas from spec
        seed_ideas_json = []
        for i in range(num_ideas):
            idea = {
                "Name": f"idea_{i+1}",
                "Title": f"{spec.title} - Idea {i+1}" if spec.title else f"Idea {i+1}",
                "Experiment": spec.objective,
                "Interestingness": 6,
                "Feasibility": 7,
                "Novelty": 5,
            }
            seed_ideas_json.append(idea)

        runtime_args = {
            "model": model,
            "writeup": writeup,
            "num_ideas": num_ideas
        }

        return TemplatePackage(
            template_name=template_name,
            prompt_json=prompt_json,
            seed_ideas_json=seed_ideas_json,
            runtime_args=runtime_args
        )

    def generate_dynamic_template(
        self,
        package: TemplatePackage,
        baseline_info: Optional[dict] = None,
    ) -> Path:
        """Generate dynamic template directory.

        Args:
            package: Template package
            baseline_info: Optional baseline info for run_0/final_info.json

        Returns:
            Path to generated template directory
        """
        import json
        import shutil

        template_path = self.template_dir / package.template_name

        # Clean existing template if present
        if template_path.exists():
            shutil.rmtree(template_path)

        template_path.mkdir(parents=True, exist_ok=True)

        # Write prompt.json
        (template_path / "prompt.json").write_text(
            json.dumps(package.prompt_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Write seed_ideas.json
        (template_path / "seed_ideas.json").write_text(
            json.dumps(package.seed_ideas_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Copy generic files from template
        generic_template = self.template_dir / "ai_toy_research_cn"
        if not generic_template.exists():
            generic_template = self.template_dir / "generic_ai_research_cn"

        for file in ["experiment.py", "plot.py"]:
            src = generic_template / file
            dst = template_path / file
            if src.exists():
                shutil.copy2(src, dst)
            else:
                # Create placeholder
                dst.write_text(
                    f"# Auto-generated placeholder for {file}\n",
                    encoding="utf-8",
                )

        # Write baseline info if provided
        if baseline_info:
            run0_dir = template_path / "run_0"
            run0_dir.mkdir(exist_ok=True)
            (run0_dir / "final_info.json").write_text(
                json.dumps(baseline_info, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        return template_path
