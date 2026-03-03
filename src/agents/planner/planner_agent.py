"""Planner agent for generating experiment plans."""

from src.llm.client import LLMClient
from src.memory.experiment_memory import ExperimentMemory
from src.schemas.orchestrator import PlannerOutput
from src.schemas.research_spec import ExperimentPlan


class PlannerAgent:
    """Agent responsible for generating action plans.

    The Planner analyzes the current experiment state and generates
    a sequence of actions (tool calls) to execute next.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        memory: ExperimentMemory | None = None,
    ) -> None:
        """Initialize planner agent.

        Args:
            llm_client: LLM client for generating plans
            memory: Optional experiment memory for retrieving similar cases
        """
        self.llm_client = llm_client
        self.memory = memory

    def generate_plan(
        self,
        plan: ExperimentPlan,
        current_state: dict,
        previous_feedback: str | None = None,
    ) -> PlannerOutput:
        """Generate action plan based on current state.

        Args:
            plan: Experiment plan
            current_state: Current experiment state (code, metrics, etc.)
            previous_feedback: Feedback from previous iteration (if any)

        Returns:
            PlannerOutput with tool calls and reasoning
        """
        # Build prompt for planner
        prompt = self._build_planner_prompt(plan, current_state, previous_feedback)

        # Call LLM to generate plan (use default model from config)
        response = self.llm_client.call(
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response into PlannerOutput
        return self._parse_planner_response(response)

    def _build_planner_prompt(
        self,
        plan: ExperimentPlan,
        current_state: dict,
        previous_feedback: str | None,
    ) -> str:
        """Build prompt for planner LLM.

        Args:
            plan: Experiment plan
            current_state: Current state
            previous_feedback: Previous feedback

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "You are an experiment planner. Generate a sequence of actions to improve the experiment.",
            f"\n## Experiment Plan\n{plan.method_summary}",
            f"\n## Current State\n{current_state}",
        ]

        if previous_feedback:
            prompt_parts.append(f"\n## Previous Feedback\n{previous_feedback}")

        # Add similar failures from memory if available
        if self.memory and previous_feedback:
            similar_failures = self.memory.find_similar_failures(
                previous_feedback, top_k=3, threshold=0.7
            )
            if similar_failures:
                prompt_parts.append("\n## Similar Past Failures")
                for i, (entry, score) in enumerate(similar_failures, 1):
                    prompt_parts.append(
                        f"\n{i}. (Similarity: {score:.2f})\n"
                        f"   Reasoning: {entry.planner_output.reasoning}\n"
                        f"   Feedback: {entry.critic_feedback.feedback}\n"
                        f"   Suggestions: {', '.join(entry.critic_feedback.suggestions)}"
                    )

        prompt_parts.append(
            "\n## Task\nGenerate a JSON object with:\n"
            '- "reasoning": Your analysis of what to do next\n'
            '- "tool_calls": List of tool calls to execute\n'
            '- "expected_improvement": What improvement you expect'
        )

        return "\n".join(prompt_parts)

    def _parse_planner_response(self, response: str) -> PlannerOutput:
        """Parse LLM response into PlannerOutput.

        Args:
            response: LLM response string

        Returns:
            Parsed PlannerOutput
        """
        import json

        # Simple JSON parsing (production would need robust error handling)
        try:
            data = json.loads(response)
            return PlannerOutput(
                reasoning=data.get("reasoning", ""),
                tool_calls=data.get("tool_calls", []),
                expected_improvement=data.get("expected_improvement", ""),
            )
        except json.JSONDecodeError:
            # Fallback: return empty plan
            return PlannerOutput(
                reasoning="Failed to parse response",
                tool_calls=[],
                expected_improvement="",
            )
