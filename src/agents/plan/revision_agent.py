"""RevisionAgent: Generate plan revision suggestions from experiment report."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.llm.client import LLMClient
from src.schemas.research_spec import ExperimentPlan, RevisionEntry
from src.schemas.plan_serializer import PlanSerializer

logger = logging.getLogger(__name__)


class RevisionAgent:
    """Generate revision suggestions for ExperimentPlan based on experiment results."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def suggest_revisions(
        self,
        plan: ExperimentPlan,
        report_path: Path,
    ) -> str:
        """Generate revision suggestions based on experiment report.

        Args:
            plan: Current experiment plan
            report_path: Path to experiment report (report.md or report.json)

        Returns:
            Markdown text with revision suggestions
        """
        # Load report
        if not report_path.exists():
            raise FileNotFoundError(f"Report not found: {report_path}")

        report_content = report_path.read_text(encoding="utf-8")

        # Build prompt
        prompt = f"""Review the following experiment plan and results, then suggest revisions.

**Current Plan**:
- Method: {plan.method_summary}
- Framework: {plan.technical_approach.framework if plan.technical_approach else "N/A"}
- Steps: {len(plan.steps)} steps

**Experiment Report**:
{report_content[:2000]}  # Truncate to avoid token limits

Based on the results, suggest specific revisions to improve the experiment plan:
1. What worked well and should be kept?
2. What failed or underperformed and needs revision?
3. What new approaches or techniques should be added?
4. What steps should be modified or removed?

Provide 3-5 concrete, actionable revision suggestions in markdown format.
"""

        # Call LLM
        response, _ = self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
        )

        return response

    def apply_revisions(
        self,
        plan: ExperimentPlan,
        revision_summary: str,
        revised_by: str = "ai",
    ) -> ExperimentPlan:
        """Apply revisions to plan and increment version.

        Args:
            plan: Current experiment plan
            revision_summary: Summary of revisions made
            revised_by: Who made the revisions ("human" or "ai")

        Returns:
            Updated ExperimentPlan with incremented version
        """
        # Validate revised_by
        if revised_by not in ("human", "ai"):
            raise ValueError(f"revised_by must be 'human' or 'ai', got: {revised_by}")

        # Create revision entry
        revision = RevisionEntry(
            version=plan.version + 1,
            revised_at=datetime.now(),
            revised_by=revised_by,  # type: ignore
            summary=revision_summary,
        )

        # Create updated plan (ExperimentPlan is frozen, must use model_copy)
        revision_history = list(plan.revision_history) if plan.revision_history else []
        revision_history.append(revision)

        updated_plan = plan.model_copy(
            update={
                "version": plan.version + 1,
                "updated_at": datetime.now(),
                "revision_history": revision_history,
            }
        )

        return updated_plan

    def revise_plan_file(
        self,
        plan_path: Path,
        report_path: Path,
        append_suggestions: bool = True,
    ) -> ExperimentPlan:
        """Load plan, generate suggestions, optionally append to file, return updated plan.

        Args:
            plan_path: Path to plan.md file
            report_path: Path to report file
            append_suggestions: If True, append suggestions to plan.md

        Returns:
            Updated ExperimentPlan (not yet saved if append_suggestions=True)
        """
        # Load existing plan
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan not found: {plan_path}")

        md_content = plan_path.read_text(encoding="utf-8")
        plan = PlanSerializer.from_markdown(md_content)

        # Generate suggestions
        suggestions = self.suggest_revisions(plan, report_path)

        if append_suggestions:
            # Append suggestions to plan.md
            updated_content = md_content.rstrip()
            updated_content += f"\n\n## 修订建议\n\n{suggestions}\n"
            plan_path.write_text(updated_content, encoding="utf-8")
            logger.info(f"Appended revision suggestions to {plan_path}")

        return plan
