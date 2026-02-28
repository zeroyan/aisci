"""Result analysis agent: uses LLM to analyze execution results and decide next action."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.schemas.errors import AiSciError, AiSciException, ErrorCode
from src.schemas.experiment import ExperimentIteration
from src.schemas.research_spec import ResearchSpec
from src.schemas.sandbox_io import AgentDecision, NextAction, SandboxResponse
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

ANALYZER_PROMPT_PATH = Path("prompts/analyzer_system.md")


class AnalyzerAgent:
    """Analyze experiment results and decide whether to continue, stop, or request human."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        if ANALYZER_PROMPT_PATH.exists():
            return ANALYZER_PROMPT_PATH.read_text(encoding="utf-8")
        return "You are an expert AI research analyst. Analyze experiment results."

    def analyze(
        self,
        spec: ResearchSpec,
        iteration: ExperimentIteration,
        response: SandboxResponse,
    ) -> AgentDecision:
        """Ask LLM to analyze the iteration result and produce a decision."""
        user_message = self._build_user_message(spec, iteration, response)

        content, _cost = self.llm.complete(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=self._system_prompt,
        )

        return self._parse_response(content, iteration)

    def _build_user_message(
        self,
        spec: ResearchSpec,
        iteration: ExperimentIteration,
        response: SandboxResponse,
    ) -> str:
        parts = [
            "## ResearchSpec",
            json.dumps(
                {
                    "objective": spec.objective,
                    "metrics": [m.model_dump() for m in spec.metrics],
                    "constraints": spec.constraints.model_dump(),
                },
                indent=2,
            ),
            "\n## Current Iteration",
            f"Index: {iteration.index}",
            f"Status: {iteration.status}",
        ]

        if iteration.metrics:
            parts.append(f"Metrics: {json.dumps(iteration.metrics)}")
        if iteration.error_summary:
            parts.append(f"Error: {iteration.error_summary}")

        parts.extend(
            [
                "\n## Sandbox Execution Result",
                f"Status: {response.status}",
                f"Exit code: {response.exit_code}",
            ]
        )

        if response.stdout:
            stdout_preview = response.stdout[:2000]
            parts.append(f"Stdout (preview):\n{stdout_preview}")
        if response.stderr:
            stderr_preview = response.stderr[:2000]
            parts.append(f"Stderr (preview):\n{stderr_preview}")

        if response.output_files.get("metrics.json"):
            parts.append(f"Metrics output: {response.output_files['metrics.json']}")

        parts.append(
            "\nAnalyze the results and decide the next action. "
            "Return ONLY a valid JSON object with 'decision', 'stop_reason', "
            "'analysis_summary', and 'next_action' keys."
        )
        return "\n".join(parts)

    def _parse_response(
        self, content: str, iteration: ExperimentIteration
    ) -> AgentDecision:
        """Extract AgentDecision from LLM response."""
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [line for line in lines[1:] if line.strip() != "```"]
                cleaned = "\n".join(lines)

            data = json.loads(cleaned)

            next_action = None
            if data.get("next_action"):
                next_action = NextAction(
                    strategy=data["next_action"].get("strategy", ""),
                    rationale=data["next_action"].get("rationale", ""),
                )

            return AgentDecision(
                iteration_id=iteration.iteration_id,
                run_id=iteration.run_id,
                decision=data["decision"],
                stop_reason=data.get("stop_reason"),
                analysis_summary=data.get("analysis_summary", ""),
                next_action=next_action,
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise AiSciException(
                AiSciError(
                    code=ErrorCode.llm_timeout,
                    message=f"Failed to parse analyzer LLM response: {e}",
                    retryable=True,
                    details={"raw_response": content[:500]},
                )
            ) from e
