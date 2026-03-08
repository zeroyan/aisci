"""Intake Agent for parsing and analyzing research ideas."""

import uuid
from datetime import datetime
from typing import Optional

from src.llm.client import LLMClient
from src.schemas.project_generator import IdeaRecord


class IntakeAgent:
    """Parse research ideas and extract key entities."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize IntakeAgent.

        Args:
            llm_client: LLM client for idea parsing (optional, creates default if None)
        """
        self.llm_client = llm_client or LLMClient()

    def intake(self, raw_idea: str, constraints: Optional[dict] = None) -> IdeaRecord:
        """Parse raw idea into structured IdeaRecord.

        Args:
            raw_idea: Natural language research idea (1-1000 characters)
            constraints: Optional user-provided constraints

        Returns:
            IdeaRecord with extracted entities and missing info
        """
        # Validate input
        if not raw_idea or len(raw_idea) < 1 or len(raw_idea) > 1000:
            raise ValueError("Idea must be 1-1000 characters")

        # Generate unique ID
        idea_id = f"idea_{uuid.uuid4().hex[:8]}"

        # Extract entities using LLM
        entities = self._extract_entities(raw_idea)

        # Classify idea type
        idea_type = self._classify_idea_type(raw_idea, entities)

        # Identify missing information
        missing_info = self._identify_missing_info(entities, constraints)

        return IdeaRecord(
            idea_id=idea_id,
            raw_text=raw_idea,
            idea_type=idea_type,
            entities=entities,
            missing_info=missing_info,
            constraints=constraints,
            created_at=datetime.now(),
        )

    def _extract_entities(self, raw_idea: str) -> dict[str, str]:
        """Extract key entities from raw idea using LLM.

        Args:
            raw_idea: Natural language research idea

        Returns:
            Dictionary of extracted entities (task, model, dataset, metric, method)
        """
        prompt = f"""Extract key entities from this research idea:

Idea: "{raw_idea}"

Extract the following entities if present:
- task: The research task or problem (e.g., "long_text_processing", "image_classification")
- model: The model or architecture mentioned (e.g., "Transformer", "BERT", "ResNet")
- dataset: The dataset mentioned (e.g., "ImageNet", "GLUE", "custom")
- metric: The evaluation metric (e.g., "accuracy", "speed", "F1")
- method: The method or technique (e.g., "attention", "fine-tuning", "pruning")

Return ONLY a JSON object with the extracted entities. If an entity is not mentioned, omit it.
Example: {{"task": "text_classification", "model": "BERT", "metric": "accuracy"}}
"""

        try:
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            # Parse JSON response
            import json
            content = response.choices[0].message.content.strip()
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            entities = json.loads(content)
            return entities

        except Exception:
            # Fallback to simple keyword extraction
            return self._fallback_entity_extraction(raw_idea)

    def _fallback_entity_extraction(self, raw_idea: str) -> dict[str, str]:
        """Fallback entity extraction using simple keyword matching.

        Args:
            raw_idea: Natural language research idea

        Returns:
            Dictionary of extracted entities
        """
        entities = {}

        # Common model names
        models = ["transformer", "bert", "gpt", "resnet", "vit", "llama", "t5"]
        for model in models:
            if model.lower() in raw_idea.lower():
                entities["model"] = model.capitalize()
                break

        # Common metrics
        metrics = ["accuracy", "speed", "latency", "throughput", "f1", "precision", "recall"]
        for metric in metrics:
            if metric.lower() in raw_idea.lower():
                entities["metric"] = metric
                break

        # Common tasks (from keywords)
        if any(word in raw_idea.lower() for word in ["classify", "classification"]):
            entities["task"] = "classification"
        elif any(word in raw_idea.lower() for word in ["generate", "generation"]):
            entities["task"] = "generation"
        elif any(word in raw_idea.lower() for word in ["translate", "translation"]):
            entities["task"] = "translation"

        return entities

    def _classify_idea_type(self, raw_idea: str, entities: dict) -> str:
        """Classify idea type based on content.

        Args:
            raw_idea: Natural language research idea
            entities: Extracted entities

        Returns:
            Idea type: performance_improvement, new_method, problem_solving, or constraint_driven
        """
        raw_lower = raw_idea.lower()

        # Performance improvement keywords
        if any(word in raw_lower for word in ["improve", "faster", "optimize", "reduce", "increase", "speed up"]):
            return "performance_improvement"

        # New method keywords
        if any(word in raw_lower for word in ["new", "novel", "propose", "introduce", "develop"]):
            return "new_method"

        # Problem solving keywords
        if any(word in raw_lower for word in ["solve", "fix", "address", "handle", "deal with"]):
            return "problem_solving"

        # Constraint driven keywords
        if any(word in raw_lower for word in ["budget", "time", "resource", "constraint", "limit"]):
            return "constraint_driven"

        # Default to performance improvement
        return "performance_improvement"

    def _identify_missing_info(self, entities: dict, constraints: Optional[dict]) -> list[str]:
        """Identify missing critical information.

        Args:
            entities: Extracted entities
            constraints: User-provided constraints

        Returns:
            List of missing information keys
        """
        missing = []

        # Check for missing entities
        if "task" not in entities:
            missing.append("objective")

        if "metric" not in entities:
            missing.append("metric")

        # Baseline is almost always missing from initial idea
        missing.append("baseline")

        # Dataset is often missing
        if "dataset" not in entities:
            missing.append("dataset")

        # Check constraints
        if not constraints:
            missing.append("constraints")

        return missing
