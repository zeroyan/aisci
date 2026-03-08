"""Clarification Agent for generating targeted questions."""

from typing import Optional

from src.llm.client import LLMClient
from src.schemas.project_generator import ClarificationQuestion, IdeaRecord


class ClarificationAgent:
    """Generate clarifying questions for incomplete ideas."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize ClarificationAgent.

        Args:
            llm_client: LLM client for question generation
        """
        self.llm_client = llm_client or LLMClient()

    def generate_questions(
        self, idea: IdeaRecord, max_questions: int = 5
    ) -> list[ClarificationQuestion]:
        """Generate clarifying questions for missing information.

        Args:
            idea: IdeaRecord with missing information
            max_questions: Maximum number of questions to generate

        Returns:
            List of ClarificationQuestion objects
        """
        if not idea.missing_info:
            return []

        questions = []

        # Generate questions for each missing piece of information
        for missing_key in idea.missing_info[:max_questions]:
            question = self._generate_question_for_key(idea, missing_key)
            if question:
                questions.append(question)

        return questions[:max_questions]

    def _generate_question_for_key(
        self, idea: IdeaRecord, missing_key: str
    ) -> Optional[ClarificationQuestion]:
        """Generate a specific question for a missing information key.

        Args:
            idea: IdeaRecord
            missing_key: Key of missing information

        Returns:
            ClarificationQuestion or None
        """
        question_id = missing_key

        # Template-based questions for common missing info
        if missing_key == "metric":
            return ClarificationQuestion(
                question_id=question_id,
                question_text="What metric do you want to optimize?",
                question_type="multiple_choice",
                options=[
                    "Accuracy",
                    "Speed/Latency",
                    "Memory Usage",
                    "Cost",
                    "F1 Score",
                ],
                default_answer="Accuracy",
                required=True,
                context="Need to define success criteria for the experiment",
            )

        elif missing_key == "baseline":
            return ClarificationQuestion(
                question_id=question_id,
                question_text="Do you have a specific baseline method in mind?",
                question_type="short_answer",
                default_answer="Use best available baseline from literature",
                required=False,
                context="Baseline helps establish performance comparison",
            )

        elif missing_key == "dataset":
            return ClarificationQuestion(
                question_id=question_id,
                question_text="What dataset will you use?",
                question_type="multiple_choice",
                options=[
                    "Standard benchmark",
                    "Custom dataset",
                    "Synthetic data",
                    "Not sure yet",
                ],
                default_answer="Standard benchmark",
                required=True,
                context="Dataset determines experiment feasibility",
            )

        elif missing_key == "constraints":
            return ClarificationQuestion(
                question_id=question_id,
                question_text="What is your budget constraint?",
                question_type="multiple_choice",
                options=["$50", "$100", "$200", "$500", "No strict limit"],
                default_answer="$100",
                required=False,
                context="Budget helps scope the experiment appropriately",
            )

        elif missing_key == "objective":
            return ClarificationQuestion(
                question_id=question_id,
                question_text=f"Can you clarify the main objective of your research? Current idea: '{idea.raw_text}'",
                question_type="short_answer",
                default_answer=idea.raw_text,
                required=True,
                context="Clear objective is essential for experiment design",
            )

        return None

    def update_idea(self, idea: IdeaRecord, answers: dict[str, str]) -> IdeaRecord:
        """Update IdeaRecord with user answers.

        Args:
            idea: Original IdeaRecord
            answers: Dictionary mapping question_id to answer

        Returns:
            Updated IdeaRecord
        """
        # Update entities based on answers
        updated_entities = idea.entities.copy()
        updated_missing = idea.missing_info.copy()
        updated_constraints = idea.constraints.copy() if idea.constraints else {}
        updated_raw_text = idea.raw_text

        for question_id, answer in answers.items():
            answer_text = answer.strip()
            key = question_id.lower()

            if key == "metric":
                normalized_metric = self._normalize_metric(answer_text)
                updated_entities["metric"] = normalized_metric
                if "metric" in updated_missing:
                    updated_missing.remove("metric")
                continue

            if key == "baseline":
                updated_entities["baseline"] = answer_text
                if "baseline" in updated_missing:
                    updated_missing.remove("baseline")
                continue

            if key == "dataset":
                updated_entities["dataset"] = answer_text
                if "dataset" in updated_missing:
                    updated_missing.remove("dataset")
                continue

            if key == "constraints":
                import re

                budget_match = re.search(r"\$?(\d+)", answer_text)
                if budget_match:
                    updated_constraints["max_budget_usd"] = float(budget_match.group(1))
                if "constraints" in updated_missing:
                    updated_missing.remove("constraints")
                continue

            if key == "objective":
                if answer_text and answer_text != idea.raw_text:
                    updated_entities["clarified_objective"] = answer_text
                    updated_raw_text = answer_text
                if "objective" in updated_missing:
                    updated_missing.remove("objective")
                continue

            # Map answers to entity updates
            if "metric" in key or any(
                m in answer_text.lower()
                for m in ["accuracy", "speed", "latency", "f1", "precision", "recall"]
            ):
                updated_entities["metric"] = self._normalize_metric(answer_text)
                if "metric" in updated_missing:
                    updated_missing.remove("metric")

            elif "baseline" in key:
                updated_entities["baseline"] = answer_text
                if "baseline" in updated_missing:
                    updated_missing.remove("baseline")

            elif "dataset" in key:
                updated_entities["dataset"] = answer_text
                if "dataset" in updated_missing:
                    updated_missing.remove("dataset")

            elif "budget" in key or "$" in answer_text:
                # Extract budget value
                import re

                budget_match = re.search(r"\$?(\d+)", answer_text)
                if budget_match:
                    updated_constraints["max_budget_usd"] = float(budget_match.group(1))
                if "constraints" in updated_missing:
                    updated_missing.remove("constraints")

            elif "objective" in key:
                # Update raw text with clarified objective
                if answer_text and answer_text != idea.raw_text:
                    updated_entities["clarified_objective"] = answer_text
                    updated_raw_text = answer_text
                if "objective" in updated_missing:
                    updated_missing.remove("objective")

        return idea.model_copy(
            update={
                "raw_text": updated_raw_text,
                "entities": updated_entities,
                "missing_info": updated_missing,
                "constraints": updated_constraints if updated_constraints else None,
            }
        )

    def _normalize_metric(self, metric: str) -> str:
        """Normalize user-provided metric text to canonical internal labels."""
        metric_lower = metric.lower().strip()

        aliases = {
            "f1 score": "f1",
            "f1-score": "f1",
            "f1": "f1",
            "speed/latency": "latency",
            "speed": "latency",
            "latency": "latency",
            "memory usage": "memory",
            "memory": "memory",
            "accuracy": "accuracy",
            "precision": "precision",
            "recall": "recall",
            "cost": "cost",
        }

        return aliases.get(metric_lower, metric_lower)
