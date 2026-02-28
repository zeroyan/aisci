"""Code generation agent: uses LLM to produce experiment code."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.schemas.errors import AiSciError, AiSciException, ErrorCode
from src.schemas.experiment import ExperimentIteration
from src.schemas.research_spec import ExperimentPlan, ResearchSpec
from src.schemas.sandbox_io import CodeSnapshot
from src.llm.client import LLMClient

logger = logging.getLogger(__name__)

CODEGEN_PROMPT_PATH = Path("prompts/codegen_system.md")


class CodegenAgent:
    """Generate or modify experiment code based on spec, plan, and history."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        if CODEGEN_PROMPT_PATH.exists():
            return CODEGEN_PROMPT_PATH.read_text(encoding="utf-8")
        return "You are an expert AI research engineer. Generate experiment code."

    def generate(
        self,
        spec: ResearchSpec,
        plan: ExperimentPlan,
        history: list[ExperimentIteration] | None = None,
    ) -> CodeSnapshot:
        """Ask LLM to generate a code snapshot for the next iteration."""
        user_message = self._build_user_message(spec, plan, history or [])

        content, _cost = self.llm.complete(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=self._system_prompt,
        )

        return self._parse_response(content)

    def _build_user_message(
        self,
        spec: ResearchSpec,
        plan: ExperimentPlan,
        history: list[ExperimentIteration],
    ) -> str:
        parts = [
            "## ResearchSpec",
            json.dumps(spec.model_dump(mode="json"), indent=2),
            "\n## ExperimentPlan",
            json.dumps(plan.model_dump(mode="json"), indent=2),
        ]

        if history:
            parts.append("\n## Previous Iterations")
            for it in history:
                parts.append(f"### Iteration {it.index} (status: {it.status})")
                if it.metrics:
                    parts.append(f"Metrics: {json.dumps(it.metrics)}")
                if it.error_summary:
                    parts.append(f"Error: {it.error_summary}")
                if it.code_change_summary:
                    parts.append(f"Changes: {it.code_change_summary}")

        parts.append(
            "\nGenerate the next experiment code. "
            "Return ONLY a valid JSON object with 'files' and 'entrypoint' keys."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> CodeSnapshot:
        """Extract CodeSnapshot from LLM response."""
        # Try to find JSON in the response
        try:
            # Strip markdown code fences if present
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [line for line in lines[1:] if line.strip() != "```"]
                cleaned = "\n".join(lines)

            data = json.loads(cleaned)
            return CodeSnapshot(
                files=data["files"],
                entrypoint=data["entrypoint"],
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise AiSciException(
                AiSciError(
                    code=ErrorCode.llm_timeout,
                    message=f"Failed to parse codegen LLM response: {e}",
                    retryable=True,
                    details={"raw_response": content[:500]},
                )
            ) from e
