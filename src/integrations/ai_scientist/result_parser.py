"""Result parser for AI-Scientist output."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.schemas.experiment_result import ExperimentResult


class ResultParser:
    """Parses AI-Scientist output into standardized format."""

    def __init__(self, result_dir: Path):
        """Initialize parser.

        Args:
            result_dir: Path to AI-Scientist results directory
        """
        self.result_dir = result_dir

    def parse_result_dir(self) -> Optional[dict]:
        """Parse result directory and extract artifacts.

        Returns:
            Parsed result dict or None if no results
        """
        if not self.result_dir.exists():
            return None

        # Find latest idea directory
        idea_dirs = [d for d in self.result_dir.iterdir() if d.is_dir()]
        if not idea_dirs:
            return None

        latest_idea = max(idea_dirs, key=lambda d: d.stat().st_mtime)

        result = {
            "idea_name": latest_idea.name,
            "idea_dir": str(latest_idea),
            "report": self._extract_report(latest_idea),
            "final_info": self._extract_final_info(latest_idea),
            "plots": self._extract_plots(latest_idea),
            "code": self._extract_code(latest_idea),
        }

        return result

    def _extract_report(self, idea_dir: Path) -> Optional[str]:
        """Extract report.md content."""
        report_path = idea_dir / "report.md"
        if report_path.exists():
            return report_path.read_text()
        return None

    def _extract_final_info(self, idea_dir: Path) -> Optional[dict]:
        """Extract final_info.json content."""
        info_path = idea_dir / "final_info.json"
        if info_path.exists():
            return json.loads(info_path.read_text())
        return None

    def _extract_plots(self, idea_dir: Path) -> list[str]:
        """Extract plot file paths."""
        plots_dir = idea_dir / "plots"
        if not plots_dir.exists():
            return []
        return [str(p) for p in plots_dir.glob("*.png")]

    def _extract_code(self, idea_dir: Path) -> list[str]:
        """Extract code file paths."""
        code_dir = idea_dir / "code"
        if not code_dir.exists():
            return []
        return [str(p) for p in code_dir.glob("*.py")]

    def extract_artifacts(self) -> list[str]:
        """Extract all artifact paths.

        Returns:
            List of artifact file paths
        """
        result = self.parse_result_dir()
        if not result:
            return []

        artifacts = []
        if result["report"]:
            artifacts.append(str(self.result_dir / result["idea_name"] / "report.md"))
        artifacts.extend(result["plots"])
        artifacts.extend(result["code"])

        return artifacts

    def to_experiment_result(
        self,
        run_id: str,
        job_id: str,
        template_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[ExperimentResult]:
        """Convert AI-Scientist output to ExperimentResult format.

        Args:
            run_id: Experiment run ID
            job_id: Job ID
            template_name: Template name used
            start_time: Job start time
            end_time: Job end time

        Returns:
            ExperimentResult or None if no results
        """
        result = self.parse_result_dir()
        if not result:
            return None

        # Extract metrics from final_info.json
        metrics = {}
        if result["final_info"]:
            # AI-Scientist may store metrics in final_info
            for key, value in result["final_info"].items():
                if isinstance(value, (int, float)):
                    metrics[key] = float(value)

        # Calculate execution time
        total_time = (end_time - start_time).total_seconds()

        # Determine status
        status = "success" if result["report"] else "failed"

        # Create ExperimentResult
        return ExperimentResult(
            run_id=run_id,
            engine="ai-scientist",
            status=status,
            best_code_path=result["code"][0] if result["code"] else None,
            metrics=metrics,
            artifacts=self.extract_artifacts(),
            total_cost_usd=0.0,  # AI-Scientist doesn't track cost
            total_time_seconds=total_time,
            iterations=1,  # One idea execution
            paper_latex=None,  # Not using LaTeX in our setup
            paper_pdf=None,
            created_at=end_time,
            engine_version="ai-scientist-0.1.0",
        )

    def copy_artifacts_to_run_dir(
        self,
        run_id: str,
        job_id: str,
        runs_dir: Path,
    ) -> Path:
        """Copy artifacts to run directory.

        Args:
            run_id: Experiment run ID
            job_id: Job ID
            runs_dir: Runs directory path

        Returns:
            Path to artifacts directory
        """
        result = self.parse_result_dir()
        if not result:
            raise ValueError("No results to copy")

        # Create artifacts directory
        artifacts_dir = runs_dir / run_id / "external" / "ai_scientist" / "artifacts" / job_id
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Copy report
        if result["report"]:
            report_src = Path(result["idea_dir"]) / "report.md"
            report_dst = artifacts_dir / "report.md"
            shutil.copy2(report_src, report_dst)

        # Copy plots
        if result["plots"]:
            plots_dst = artifacts_dir / "plots"
            plots_dst.mkdir(exist_ok=True)
            for plot_path in result["plots"]:
                plot_src = Path(plot_path)
                shutil.copy2(plot_src, plots_dst / plot_src.name)

        # Copy code
        if result["code"]:
            code_dst = artifacts_dir / "code"
            code_dst.mkdir(exist_ok=True)
            for code_path in result["code"]:
                code_src = Path(code_path)
                shutil.copy2(code_src, code_dst / code_src.name)

        # Copy final_info.json
        if result["final_info"]:
            info_src = Path(result["idea_dir"]) / "final_info.json"
            info_dst = artifacts_dir / "final_info.json"
            shutil.copy2(info_src, info_dst)

        return artifacts_dir
