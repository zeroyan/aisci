"""Critic agent for evaluating experiment results."""

from src.llm.client import LLMClient
from src.schemas.orchestrator import CriticFeedback
from src.schemas.research_spec import ExperimentPlan


class CriticAgent:
    """Agent responsible for evaluating experiment results.

    The Critic analyzes execution results and provides feedback
    on whether the experiment succeeded, failed, or needs improvement.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize critic agent.

        Args:
            llm_client: LLM client for generating feedback
        """
        self.llm_client = llm_client

    def evaluate(
        self,
        plan: ExperimentPlan,
        execution_result: dict,
        previous_attempts: list[dict] | None = None,
    ) -> CriticFeedback:
        """Evaluate execution result and provide feedback.

        Args:
            plan: Experiment plan
            execution_result: Result from executing planner's actions
            previous_attempts: History of previous attempts (if any)

        Returns:
            CriticFeedback with status and suggestions
        """
        # Build prompt for critic
        prompt = self._build_critic_prompt(plan, execution_result, previous_attempts)

        # Call LLM to generate feedback (use default model from config)
        response = self.llm_client.call(
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response into CriticFeedback
        return self._parse_critic_response(response)

    def _build_critic_prompt(
        self,
        plan: ExperimentPlan,
        execution_result: dict,
        previous_attempts: list[dict] | None,
    ) -> str:
        """Build prompt for critic LLM.

        Args:
            plan: Experiment plan
            execution_result: Execution result
            previous_attempts: Previous attempts

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "You are an experiment critic. Evaluate the execution result.",
            f"\n## Experiment Goal\n{plan.method_summary}",
            f"\n## Execution Result\n{execution_result}",
        ]

        if previous_attempts:
            prompt_parts.append(
                f"\n## Previous Attempts\n{len(previous_attempts)} attempts made"
            )

        prompt_parts.append(
            "\n## Task\nGenerate a JSON object with:\n"
            '- "status": "success", "failed", or "needs_improvement"\n'
            '- "feedback": Detailed feedback on what worked/failed\n'
            '- "suggestions": Specific suggestions for next iteration\n'
            '- "score": Numeric score 0-100 (higher is better)'
        )

        return "\n".join(prompt_parts)

    def _parse_critic_response(self, response: str) -> CriticFeedback:
        """Parse LLM response into CriticFeedback.

        Args:
            response: LLM response string

        Returns:
            Parsed CriticFeedback
        """
        import json

        try:
            data = json.loads(response)
            return CriticFeedback(
                status=data.get("status", "needs_improvement"),
                feedback=data.get("feedback", ""),
                suggestions=data.get("suggestions", []),
                score=data.get("score", 0.0),
            )
        except json.JSONDecodeError:
            # Fallback: return needs_improvement
            return CriticFeedback(
                status="needs_improvement",
                feedback="Failed to parse critic response",
                suggestions=[],
                score=0.0,
            )
