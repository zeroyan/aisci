"""PlanAgent: Generate ExperimentPlan from ResearchSpec + knowledge."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from src.knowledge.store import KnowledgeStore
from src.llm.client import LLMClient
from src.schemas.research_spec import ExperimentPlan, ResearchSpec, TechnicalApproach
from src.schemas import PlanStep

logger = logging.getLogger(__name__)


class PlanAgent:
    """Generate structured ExperimentPlan from ResearchSpec."""

    def __init__(self, llm_client: LLMClient, knowledge_store: KnowledgeStore) -> None:
        self.llm = llm_client
        self.knowledge = knowledge_store

    def generate(
        self,
        spec: ResearchSpec,
        run_id: str | None = None,
    ) -> ExperimentPlan:
        """Generate ExperimentPlan from ResearchSpec.

        Args:
            spec: Research specification
            run_id: Optional run ID for knowledge lookup

        Returns:
            Generated ExperimentPlan
        """
        # Search knowledge base for relevant materials
        keywords = spec.title.split() + spec.objective.split()[:5]
        knowledge_entries = self.knowledge.search(keywords, run_id=run_id)

        # Build prompt with knowledge context
        knowledge_context = "\n\n".join(
            f"**{entry.meta.title}**\n{entry.summary}"
            for entry in knowledge_entries[:3]
        )

        prompt = f"""Generate an experiment plan for the following research specification.

**Research Objective**: {spec.objective}

**Metrics**: {', '.join(m.name for m in spec.metrics)}

**Relevant Knowledge**:
{knowledge_context if knowledge_context else "No prior knowledge found."}

Generate a structured experiment plan with:
1. Method summary (2-3 sentences)
2. Technical approach (framework, baseline methods, key references)
3. Evaluation protocol
4. Implementation steps (3-5 steps)

Output as JSON with keys: method_summary, framework, baseline_methods, key_references, evaluation_protocol, steps (array of {{step_id, description, expected_output}})
"""

        # Call LLM
        response, _ = self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response (simplified - should use structured output)
        import json
        try:
            # Try to extract JSON from response
            json_match = response[response.find("{"):response.rfind("}")+1]
            data = json.loads(json_match)
        except:
            # Fallback: create minimal plan
            data = {
                "method_summary": "Implement baseline experiment",
                "framework": "Python",
                "evaluation_protocol": "Measure metrics",
                "steps": [
                    {"step_id": "step-01", "description": "Setup environment", "expected_output": "Environment ready"},
                    {"step_id": "step-02", "description": "Run experiment", "expected_output": "metrics.json"},
                ]
            }

        # Build ExperimentPlan
        plan = ExperimentPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:12]}",
            spec_id=spec.spec_id,
            version=1,
            title=spec.title,
            method_summary=data["method_summary"],
            technical_approach=TechnicalApproach(
                framework=data.get("framework", "Python"),
                baseline_methods=data.get("baseline_methods", []),
                key_references=data.get("key_references", []),
            ),
            evaluation_protocol=data.get("evaluation_protocol", "Measure metrics"),
            steps=[PlanStep(**step) for step in data["steps"]],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        return plan
