"""Planner-Executor-Critic loop implementation."""

from src.agents.planner.critic_agent import CriticAgent
from src.agents.planner.early_stop_detector import EarlyStopDetector
from src.agents.planner.planner_agent import PlannerAgent
from src.llm.client import LLMClient
from src.memory.experiment_memory import ExperimentMemory
from src.schemas.orchestrator import CriticFeedback, MemoryEntry
from src.schemas.research_spec import ExperimentPlan


class PECLoop:
    """Planner-Executor-Critic loop.

    Iteratively:
    1. Planner generates action plan
    2. Executor executes the plan
    3. Critic evaluates results and provides feedback
    4. Repeat until success or early stop
    """

    def __init__(
        self,
        llm_client: LLMClient,
        max_iterations: int = 5,
        early_stop_threshold: int = 2,
        memory: ExperimentMemory | None = None,
    ) -> None:
        """Initialize PEC loop.

        Args:
            llm_client: LLM client for agents
            max_iterations: Maximum number of iterations
            early_stop_threshold: Consecutive no-improvement threshold
            memory: Optional experiment memory for planner
        """
        self.planner = PlannerAgent(llm_client, memory)
        self.critic = CriticAgent(llm_client)
        self.early_stop_detector = EarlyStopDetector(early_stop_threshold)
        self.max_iterations = max_iterations

    def run(
        self,
        plan: ExperimentPlan,
        executor_fn: callable,
        initial_state: dict,
    ) -> tuple[list[MemoryEntry], CriticFeedback]:
        """Run PEC loop until success or early stop.

        Args:
            plan: Experiment plan
            executor_fn: Function to execute planner output
                Signature: (PlannerOutput, dict) -> dict
            initial_state: Initial experiment state

        Returns:
            Tuple of (memory_entries, final_feedback)
        """
        memory_entries: list[MemoryEntry] = []
        current_state = initial_state
        previous_feedback = None

        for iteration in range(1, self.max_iterations + 1):
            # 1. Planner generates plan
            planner_output = self.planner.generate_plan(
                plan, current_state, previous_feedback
            )

            # 2. Executor executes plan
            execution_result = executor_fn(planner_output, current_state)

            # 3. Critic evaluates result
            critic_feedback = self.critic.evaluate(
                plan, execution_result, [e.model_dump() for e in memory_entries]
            )

            # Record to memory
            memory_entry = MemoryEntry(
                iteration=iteration,
                planner_output=planner_output,
                execution_result=execution_result,
                critic_feedback=critic_feedback,
            )
            memory_entries.append(memory_entry)

            # Check for success
            if critic_feedback.status == "success":
                return memory_entries, critic_feedback

            # Check for failure
            if critic_feedback.status == "failed":
                return memory_entries, critic_feedback

            # Check early stop
            should_stop, reason = self.early_stop_detector.should_stop(
                critic_feedback.score, self.max_iterations, iteration
            )
            if should_stop:
                # Create final feedback with early stop reason
                final_feedback = CriticFeedback(
                    status="failed",
                    feedback=f"Early stop: {reason}",
                    suggestions=critic_feedback.suggestions,
                    score=critic_feedback.score,
                )
                return memory_entries, final_feedback

            # Update state for next iteration
            current_state = execution_result
            previous_feedback = critic_feedback.feedback

        # Max iterations reached
        final_feedback = CriticFeedback(
            status="failed",
            feedback=f"Reached maximum iterations ({self.max_iterations})",
            suggestions=[],
            score=memory_entries[-1].critic_feedback.score if memory_entries else 0.0,
        )
        return memory_entries, final_feedback
