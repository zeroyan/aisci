"""Failure report generator for failed experiments."""

from datetime import datetime
from pathlib import Path

from src.schemas.orchestrator import CriticFeedback, MemoryEntry
from src.schemas.research_spec import ExperimentPlan


class FailureReportGenerator:
    """Generate detailed failure reports for failed experiments."""

    def generate_report(
        self,
        plan: ExperimentPlan,
        memory_entries: list[MemoryEntry],
        final_feedback: CriticFeedback,
        output_path: Path,
    ) -> None:
        """Generate failure report and save to file.

        Args:
            plan: Experiment plan
            memory_entries: History of attempts
            final_feedback: Final critic feedback
            output_path: Path to save report
        """
        report_lines = [
            "# Experiment Failure Report",
            f"\n**Generated**: {datetime.now().isoformat()}",
            f"\n**Plan ID**: {plan.plan_id}",
            f"\n**Plan Title**: {plan.title}",
            "\n---",
            "\n## Summary",
            f"\n**Status**: {final_feedback.status}",
            f"\n**Final Score**: {final_feedback.score:.2f}",
            f"\n**Total Iterations**: {len(memory_entries)}",
            f"\n**Failure Reason**: {final_feedback.feedback}",
            "\n---",
            "\n## Attempt History",
        ]

        # Add each attempt
        for entry in memory_entries:
            report_lines.extend(
                [
                    f"\n### Iteration {entry.iteration}",
                    f"\n**Planner Reasoning**: {entry.planner_output.reasoning}",
                    f"\n**Tool Calls**: {len(entry.planner_output.tool_calls)} calls",
                    f"\n**Critic Status**: {entry.critic_feedback.status}",
                    f"\n**Score**: {entry.critic_feedback.score:.2f}",
                    f"\n**Feedback**: {entry.critic_feedback.feedback}",
                ]
            )

            if entry.critic_feedback.suggestions:
                report_lines.append("\n**Suggestions**:")
                for suggestion in entry.critic_feedback.suggestions:
                    report_lines.append(f"- {suggestion}")

        # Add final recommendations
        report_lines.extend(
            [
                "\n---",
                "\n## Recommendations",
            ]
        )

        if final_feedback.suggestions:
            for suggestion in final_feedback.suggestions:
                report_lines.append(f"- {suggestion}")
        else:
            report_lines.append("- Review experiment plan and constraints")
            report_lines.append("- Consider alternative approaches")
            report_lines.append("- Check if baseline is achievable")

        # Write report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(report_lines))
