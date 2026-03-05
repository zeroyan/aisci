"""Report synthesizer: Integrate results from multiple engines into unified report."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.llm.client import LLMClient
from src.schemas.experiment import ExperimentRun, ExperimentIteration
from src.schemas.experiment_result import ExperimentResult
from src.schemas.report import ExperimentReport
from src.schemas import BestResult, EvidenceEntry

logger = logging.getLogger(__name__)


class ReportSynthesizer:
    """Synthesize unified report from multiple engine results."""

    def __init__(self, llm_client: LLMClient):
        """Initialize synthesizer.

        Args:
            llm_client: LLM client for generating synthesis
        """
        self.llm = llm_client

    def synthesize_hybrid_report(
        self,
        run_id: str,
        baseline_run: ExperimentRun,
        baseline_metrics: dict[str, float],
        ai_scientist_result: ExperimentResult,
        runs_dir: Path,
    ) -> ExperimentReport:
        """Synthesize unified report from hybrid mode results.

        Args:
            run_id: Main run ID
            baseline_run: Baseline run from AiSci
            baseline_metrics: Baseline metrics
            ai_scientist_result: AI-Scientist result
            runs_dir: Runs directory path

        Returns:
            Unified ExperimentReport
        """
        # Extract AI-Scientist metrics
        ai_scientist_metrics = ai_scientist_result.metrics or {}

        # Build comparison summary
        comparison = self._build_comparison(
            baseline_metrics,
            ai_scientist_metrics,
        )

        # Generate synthesis using LLM
        synthesis = self._generate_synthesis(
            baseline_metrics=baseline_metrics,
            ai_scientist_metrics=ai_scientist_metrics,
            comparison=comparison,
        )

        # Build evidence map
        evidence_entries = self._build_evidence_map(
            run_id=run_id,
            baseline_run=baseline_run,
            ai_scientist_result=ai_scientist_result,
        )

        # Determine best result
        best_metrics = ai_scientist_metrics if comparison["improved"] else baseline_metrics
        best_source = "ai-scientist" if comparison["improved"] else "baseline"

        # Create unified report
        import uuid
        report = ExperimentReport(
            report_id=f"report_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            summary=synthesis["summary"],
            best_result=BestResult(
                iteration_id=f"{best_source}:final",
                metrics=best_metrics,
            ),
            key_findings=synthesis["key_findings"],
            failed_attempts=[],
            evidence_map=evidence_entries,
            next_actions=synthesis["next_actions"],
            generated_at=datetime.now(timezone.utc),
        )

        return report

    def _build_comparison(
        self,
        baseline_metrics: dict[str, float],
        ai_scientist_metrics: dict[str, float],
    ) -> dict:
        """Build comparison between baseline and AI-Scientist results.

        Args:
            baseline_metrics: Baseline metrics
            ai_scientist_metrics: AI-Scientist metrics

        Returns:
            Comparison dict with improvements and changes
        """
        comparison = {
            "baseline": baseline_metrics,
            "ai_scientist": ai_scientist_metrics,
            "improvements": {},
            "regressions": {},
            "improved": False,
        }

        # Compare common metrics
        common_keys = set(baseline_metrics.keys()) & set(ai_scientist_metrics.keys())
        for key in common_keys:
            baseline_val = baseline_metrics[key]
            ai_val = ai_scientist_metrics[key]
            delta = ai_val - baseline_val
            pct_change = (delta / baseline_val * 100) if baseline_val != 0 else 0

            if delta > 0:
                comparison["improvements"][key] = {
                    "baseline": baseline_val,
                    "ai_scientist": ai_val,
                    "delta": delta,
                    "pct_change": pct_change,
                }
            elif delta < 0:
                comparison["regressions"][key] = {
                    "baseline": baseline_val,
                    "ai_scientist": ai_val,
                    "delta": delta,
                    "pct_change": pct_change,
                }

        # Overall improvement if more improvements than regressions
        comparison["improved"] = len(comparison["improvements"]) > len(comparison["regressions"])

        return comparison

    def _generate_synthesis(
        self,
        baseline_metrics: dict[str, float],
        ai_scientist_metrics: dict[str, float],
        comparison: dict,
    ) -> dict:
        """Generate synthesis using LLM.

        Args:
            baseline_metrics: Baseline metrics
            ai_scientist_metrics: AI-Scientist metrics
            comparison: Comparison dict

        Returns:
            Synthesis dict with summary, key_findings, next_actions
        """
        # Build prompt
        prompt = f"""Analyze the following experiment results from two approaches:

**Baseline (AiSci)**:
{json.dumps(baseline_metrics, indent=2)}

**AI-Scientist**:
{json.dumps(ai_scientist_metrics, indent=2)}

**Comparison**:
- Improvements: {len(comparison['improvements'])} metrics
- Regressions: {len(comparison['regressions'])} metrics
- Overall: {"Improved" if comparison['improved'] else "No improvement"}

Generate a synthesis report with:
1. Summary (2-3 sentences): Overall assessment of results
2. Key Findings (3-5 points): Most important insights
3. Next Actions (2-3 points): Recommended next steps

Format as JSON:
{{
  "summary": "...",
  "key_findings": ["...", "..."],
  "next_actions": ["...", "..."]
}}
"""

        try:
            response, _ = self.llm.complete(
                messages=[{"role": "user", "content": prompt}],
            )

            # Try to parse JSON response
            synthesis = json.loads(response)
            return synthesis
        except Exception as e:
            logger.warning(f"Failed to generate LLM synthesis: {e}, using fallback")
            return self._fallback_synthesis(comparison)

    def _fallback_synthesis(self, comparison: dict) -> dict:
        """Generate fallback synthesis without LLM.

        Args:
            comparison: Comparison dict

        Returns:
            Synthesis dict
        """
        improvements = comparison["improvements"]
        regressions = comparison["regressions"]

        summary = (
            f"Hybrid mode completed with {len(improvements)} improvements "
            f"and {len(regressions)} regressions compared to baseline."
        )

        key_findings = []
        if improvements:
            key_findings.append(
                f"Improved metrics: {', '.join(improvements.keys())}"
            )
        if regressions:
            key_findings.append(
                f"Regressed metrics: {', '.join(regressions.keys())}"
            )
        if not improvements and not regressions:
            key_findings.append("No significant changes from baseline")

        next_actions = [
            "Review detailed results in artifacts directory",
            "Consider running additional iterations with refined parameters",
        ]

        return {
            "summary": summary,
            "key_findings": key_findings,
            "next_actions": next_actions,
        }

    def _build_evidence_map(
        self,
        run_id: str,
        baseline_run: ExperimentRun,
        ai_scientist_result: ExperimentResult,
    ) -> list[EvidenceEntry]:
        """Build evidence map from both results.

        Args:
            run_id: Main run ID
            baseline_run: Baseline run
            ai_scientist_result: AI-Scientist result

        Returns:
            List of evidence entries
        """
        evidence_entries = []

        # Baseline evidence
        evidence_entries.append(
            EvidenceEntry(
                claim=f"Baseline run completed with {baseline_run.iteration_count} iterations",
                evidence_paths=[
                    f"hybrid_baseline_runs/{baseline_run.run_id}/run.json",
                    f"hybrid_baseline_runs/{baseline_run.run_id}/iterations/it_0001/iteration.json",
                ],
            )
        )

        # AI-Scientist evidence
        evidence_entries.append(
            EvidenceEntry(
                claim=f"AI-Scientist execution: {ai_scientist_result.status}",
                evidence_paths=ai_scientist_result.artifacts[:5] if ai_scientist_result.artifacts else [],
            )
        )

        return evidence_entries

    def generate_comparison_report(
        self,
        run_id: str,
        baseline_metrics: dict[str, float],
        ai_scientist_metrics: dict[str, float],
        output_path: Path,
    ) -> None:
        """Generate markdown comparison report.

        Args:
            run_id: Run ID
            baseline_metrics: Baseline metrics
            ai_scientist_metrics: AI-Scientist metrics
            output_path: Output file path
        """
        comparison = self._build_comparison(baseline_metrics, ai_scientist_metrics)

        # Build markdown
        md = f"""# Hybrid Mode Comparison Report

**Run ID**: {run_id}
**Generated**: {datetime.now(timezone.utc).isoformat()}

---

## Baseline (AiSci)

```json
{json.dumps(baseline_metrics, indent=2)}
```

---

## AI-Scientist

```json
{json.dumps(ai_scientist_metrics, indent=2)}
```

---

## Comparison

### Improvements

"""

        if comparison["improvements"]:
            md += "| Metric | Baseline | AI-Scientist | Delta | Change % |\n"
            md += "|--------|----------|--------------|-------|----------|\n"
            for key, data in comparison["improvements"].items():
                md += f"| {key} | {data['baseline']:.4f} | {data['ai_scientist']:.4f} | +{data['delta']:.4f} | +{data['pct_change']:.2f}% |\n"
        else:
            md += "No improvements found.\n"

        md += "\n### Regressions\n\n"

        if comparison["regressions"]:
            md += "| Metric | Baseline | AI-Scientist | Delta | Change % |\n"
            md += "|--------|----------|--------------|-------|----------|\n"
            for key, data in comparison["regressions"].items():
                md += f"| {key} | {data['baseline']:.4f} | {data['ai_scientist']:.4f} | {data['delta']:.4f} | {data['pct_change']:.2f}% |\n"
        else:
            md += "No regressions found.\n"

        md += f"\n---\n\n**Overall**: {'✅ Improved' if comparison['improved'] else '⚠️ No improvement'}\n"

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        logger.info(f"Comparison report saved to {output_path}")
