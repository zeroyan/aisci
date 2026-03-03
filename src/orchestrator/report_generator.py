"""Generate branch and final reports."""

from datetime import datetime
from pathlib import Path

from src.memory.experiment_memory import ExperimentMemory
from src.schemas.orchestrator import BranchResult


class ReportGenerator:
    """Generate Markdown reports for branches and final results."""

    def __init__(self, memory: ExperimentMemory | None = None) -> None:
        """Initialize report generator.

        Args:
            memory: Optional experiment memory for referencing past cases
        """
        self.memory = memory

    def generate_branch_report(
        self,
        branch_result: BranchResult,
        workspace_path: Path,
        memory_entries: list[dict] | None = None,
    ) -> str:
        """Generate Markdown report for a single branch.

        Args:
            branch_result: Branch execution result
            workspace_path: Path to branch workspace
            memory_entries: Optional list of memory entries

        Returns:
            Markdown report content
        """
        report = f"""# Branch Report: {branch_result.branch_id}

**Status**: {branch_result.status}
**Iterations**: {branch_result.iterations}
**Cost**: ${branch_result.cost_usd:.2f}
**Time**: {branch_result.time_seconds:.1f}s

---

## Results

"""

        if branch_result.status == "success":
            report += f"""### Success ✅

**Best Code**: `{branch_result.best_code_path or 'N/A'}`

**Metrics**:
"""
            for metric_name, metric_value in branch_result.metrics.items():
                report += f"- {metric_name}: {metric_value:.4f}\n"

        elif branch_result.status == "failed":
            report += """### Failed ❌

The branch failed to produce a successful result. See execution history below for details.

"""

        elif branch_result.status == "timeout":
            report += """### Timeout ⏱️

The branch exceeded the allocated time budget.

"""

        # Add execution history if available
        if memory_entries:
            report += f"""
---

## Execution History

Total attempts: {len(memory_entries)}

"""
            for i, entry in enumerate(memory_entries, 1):
                status_emoji = {
                    "success": "✅",
                    "failed": "❌",
                    "needs_improvement": "⚠️",
                }.get(entry.get("status", "unknown"), "❓")

                report += f"""### Iteration {i} {status_emoji}

**Feedback**: {entry.get('feedback', 'N/A')}

"""

        report += f"""
---

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        return report

    def generate_final_report(
        self,
        branch_results: list[BranchResult],
        run_id: str,
        total_cost: float,
        total_time: float,
    ) -> str:
        """Generate final summary report across all branches.

        Args:
            branch_results: Results from all branches
            run_id: Run identifier
            total_cost: Total cost across all branches
            total_time: Total time across all branches

        Returns:
            Markdown report content
        """
        successful_branches = [b for b in branch_results if b.status == "success"]
        failed_branches = [b for b in branch_results if b.status == "failed"]
        timeout_branches = [b for b in branch_results if b.status == "timeout"]

        report = f"""# Final Report: {run_id}

**Total Branches**: {len(branch_results)}
**Successful**: {len(successful_branches)} ✅
**Failed**: {len(failed_branches)} ❌
**Timeout**: {len(timeout_branches)} ⏱️

**Total Cost**: ${total_cost:.2f}
**Total Time**: {total_time:.1f}s

---

## Branch Summary

"""

        for branch in branch_results:
            status_emoji = {
                "success": "✅",
                "failed": "❌",
                "timeout": "⏱️",
            }.get(branch.status, "❓")

            report += f"""### {branch.branch_id} {status_emoji}

- **Status**: {branch.status}
- **Iterations**: {branch.iterations}
- **Cost**: ${branch.cost_usd:.2f}
- **Time**: {branch.time_seconds:.1f}s
- **Report**: `{branch.report_path}`

"""

        # Best result section
        if successful_branches:
            # Select best branch by primary metric
            # If no metrics, fall back to lowest cost
            if successful_branches[0].metrics:
                # Get first metric name
                first_metric = next(iter(successful_branches[0].metrics.keys()))

                # Determine direction: check if metric name suggests "lower is better"
                # Common patterns: loss, error, mse, mae, rmse, latency, time
                lower_is_better_keywords = ["loss", "error", "mse", "mae", "rmse", "latency", "time", "cost"]
                is_lower_better = any(keyword in first_metric.lower() for keyword in lower_is_better_keywords)

                if is_lower_better:
                    # Lower is better (loss, error, etc.)
                    best_branch = min(successful_branches, key=lambda b: b.metrics.get(first_metric, float("inf")))
                else:
                    # Higher is better (accuracy, f1, etc.)
                    best_branch = max(successful_branches, key=lambda b: b.metrics.get(first_metric, 0.0))
            else:
                # No metrics, select by lowest cost
                best_branch = min(successful_branches, key=lambda b: b.cost_usd)

            report += f"""
---

## Best Result

**Branch**: {best_branch.branch_id}
**Code**: `{best_branch.best_code_path or 'N/A'}`

**Metrics**:
"""
            for metric_name, metric_value in best_branch.metrics.items():
                report += f"- {metric_name}: {metric_value:.4f}\n"

        else:
            report += """
---

## Best Result

No successful branches. All branches failed or timed out.

"""

        report += f"""
---

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        return report
