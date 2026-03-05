"""ExperimentPlan MD serialization: YAML front-matter + PLAN_JSON."""

from __future__ import annotations

import json
import re
from datetime import datetime

import frontmatter

from src.schemas.research_spec import ExperimentPlan, TechnicalApproach, RevisionEntry
from src.schemas import PlanStep


class PlanSerializer:
    """Serialize/deserialize ExperimentPlan to/from MD format."""

    @staticmethod
    def to_markdown(plan: ExperimentPlan) -> str:
        """Convert ExperimentPlan to MD with YAML front-matter + PLAN_JSON."""
        # Build front-matter
        meta = {
            "plan_id": plan.plan_id,
            "spec_id": plan.spec_id,
            "version": plan.version,
            "title": plan.title or "Experiment Plan",
            "created_at": plan.created_at.isoformat() if plan.created_at else datetime.now().isoformat(),
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else datetime.now().isoformat(),
        }

        # Build body
        body = f"# 实验方案：{plan.title or 'Untitled'}\n\n"
        body += f"## 方法摘要\n\n{plan.method_summary}\n\n"

        if plan.technical_approach:
            body += "## 技术路线\n\n"
            body += f"- **框架**: {plan.technical_approach.framework}\n"
            if plan.technical_approach.baseline_methods:
                body += f"- **Baseline 方法**: {', '.join(plan.technical_approach.baseline_methods)}\n"
            if plan.technical_approach.key_references:
                body += "- **关键参考**:\n"
                for ref in plan.technical_approach.key_references:
                    body += f"  - {ref}\n"
            if plan.technical_approach.implementation_notes:
                body += f"- **实现要点**: {plan.technical_approach.implementation_notes}\n"
            body += "\n"

        body += f"## 评估指标\n\n{plan.evaluation_protocol}\n\n"

        body += "## 实验步骤\n\n"
        for i, step in enumerate(plan.steps, 1):
            body += f"### 步骤 {i}：{step.description[:50]}...\n\n"
            if step.depends_on:
                body += f"**依赖**: {', '.join(step.depends_on)}\n\n"
            if step.estimated_minutes:
                body += f"**预估耗时**: {step.estimated_minutes} 分钟\n\n"
            body += f"{step.description}\n\n"

        if plan.revision_history:
            body += "## 修订历史\n\n"
            body += "| 版本 | 时间 | 修订者 | 摘要 |\n"
            body += "|------|------|--------|------|\n"
            for rev in plan.revision_history:
                body += f"| {rev.version} | {rev.revised_at.strftime('%Y-%m-%d')} | {rev.revised_by} | {rev.summary} |\n"
            body += "\n"

        # Append PLAN_JSON comment
        plan_json = plan.model_dump(mode="json")
        body += f"<!-- PLAN_JSON\n{json.dumps(plan_json, ensure_ascii=False, indent=2)}\n-->"

        # Create frontmatter post
        post = frontmatter.Post(body, **meta)
        return frontmatter.dumps(post)

    @staticmethod
    def from_markdown(md: str) -> ExperimentPlan:
        """Parse MD with PLAN_JSON comment back to ExperimentPlan."""
        post = frontmatter.loads(md)

        # Extract PLAN_JSON from HTML comment
        match = re.search(r"<!-- PLAN_JSON\n(.*?)\n-->", post.content, re.DOTALL)
        if not match:
            raise ValueError("PLAN_JSON comment not found in markdown")

        plan_json = json.loads(match.group(1))

        # Parse nested objects
        if plan_json.get("technical_approach"):
            plan_json["technical_approach"] = TechnicalApproach(**plan_json["technical_approach"])

        if plan_json.get("revision_history"):
            plan_json["revision_history"] = [
                RevisionEntry(**rev) for rev in plan_json["revision_history"]
            ]

        plan_json["steps"] = [PlanStep(**step) for step in plan_json["steps"]]

        # Parse datetime strings
        if plan_json.get("created_at"):
            plan_json["created_at"] = datetime.fromisoformat(plan_json["created_at"])
        if plan_json.get("updated_at"):
            plan_json["updated_at"] = datetime.fromisoformat(plan_json["updated_at"])

        return ExperimentPlan(**plan_json)

    @staticmethod
    def load(path) -> ExperimentPlan:
        """Load ExperimentPlan from file.

        Args:
            path: Path to plan file (supports .md or .json)

        Returns:
            ExperimentPlan instance
        """
        from pathlib import Path

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")

        content = path.read_text()

        # Try JSON first
        if path.suffix == ".json":
            plan_json = json.loads(content)

            # Parse nested objects
            if plan_json.get("technical_approach"):
                plan_json["technical_approach"] = TechnicalApproach(**plan_json["technical_approach"])

            if plan_json.get("revision_history"):
                plan_json["revision_history"] = [
                    RevisionEntry(**rev) for rev in plan_json["revision_history"]
                ]

            plan_json["steps"] = [PlanStep(**step) for step in plan_json["steps"]]

            # Parse datetime strings
            if plan_json.get("created_at"):
                plan_json["created_at"] = datetime.fromisoformat(plan_json["created_at"])
            if plan_json.get("updated_at"):
                plan_json["updated_at"] = datetime.fromisoformat(plan_json["updated_at"])

            return ExperimentPlan(**plan_json)

        # Otherwise try markdown
        return PlanSerializer.from_markdown(content)
