"""Formalization Agent for converting ideas to ResearchSpec."""

import uuid
from typing import Optional

from src.llm.client import LLMClient
from src.schemas.project_generator import EvidencePackage, IdeaRecord
from src.schemas.research_spec import Constraints, Metric, ResearchSpec


class FormalizationAgent:
    """Convert ideas and evidence into formal ResearchSpec."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize FormalizationAgent.

        Args:
            llm_client: LLM client for spec generation
        """
        self.llm_client = llm_client or LLMClient()

    def formalize(
        self,
        idea: IdeaRecord,
        evidence: EvidencePackage,
    ) -> ResearchSpec:
        """Generate ResearchSpec from idea and evidence.

        Args:
            idea: Parsed research idea
            evidence: Evidence package from search

        Returns:
            ResearchSpec ready for execution
        """
        spec_id = f"proj_{uuid.uuid4().hex[:8]}"

        # Generate title
        title = self._generate_title(idea, evidence)

        # Generate objective
        objective = self._generate_objective(idea, evidence)

        # Generate metrics
        metrics = self._generate_metrics(idea, evidence)

        # Generate constraints
        constraints = self._generate_constraints(idea)

        # Add evidence metadata
        primary_baseline = evidence.baselines[0] if evidence.baselines else None
        evidence_metadata = {
            "source_papers": [p.paper_id for p in evidence.papers[:5]],
            "baseline_method": primary_baseline.method_name
            if primary_baseline
            else None,
            "baseline_reference": primary_baseline.paper_reference
            if primary_baseline
            else None,
            "baseline_references": [b.method_name for b in evidence.baselines],
            "baseline_paper_references": [
                b.paper_reference for b in evidence.baselines if b.paper_reference
            ],
            "risk_assessment": "moderate" if len(evidence.papers) >= 5 else "high",
            "generated_from_idea": idea.raw_text,
        }

        return ResearchSpec(
            spec_id=spec_id,
            title=title,
            objective=objective,
            metrics=metrics,
            constraints=constraints,
            status="confirmed",
            evidence_metadata=evidence_metadata,
        )

    def _generate_title(self, idea: IdeaRecord, evidence: EvidencePackage) -> str:
        """Generate research title.

        Args:
            idea: Research idea
            evidence: Evidence package

        Returns:
            Research title
        """
        # Extract key terms
        task = idea.entities.get("task", "research")
        model = idea.entities.get("model", "model")
        metric = idea.entities.get("metric", "performance")

        # Use baseline if available
        if evidence.baselines:
            baseline = evidence.baselines[0].method_name
            return f"Improving {model} {metric} on {task} using {baseline}"

        return f"{model} Optimization for {task}"

    def _generate_objective(self, idea: IdeaRecord, evidence: EvidencePackage) -> str:
        """Generate research objective.

        Args:
            idea: Research idea
            evidence: Evidence package

        Returns:
            Research objective
        """
        objective = idea.raw_text

        # Add baseline context if available
        if evidence.baselines:
            baseline = evidence.baselines[0].method_name
            objective += f" Building on {baseline} as baseline."

        # Add evidence context
        if evidence.papers:
            objective += f" Informed by {len(evidence.papers)} recent papers."

        return objective

    def _generate_metrics(
        self, idea: IdeaRecord, evidence: EvidencePackage
    ) -> list[Metric]:
        """Generate evaluation metrics.

        Args:
            idea: Research idea
            evidence: Evidence package

        Returns:
            List of Metric objects
        """
        metrics = []

        # Primary metric from idea
        metric_name = idea.entities.get("metric", "accuracy").lower().strip()
        metric_aliases = {
            "f1 score": "f1",
            "f1-score": "f1",
            "speed/latency": "latency",
            "speed": "latency",
            "time": "latency",
            "memory usage": "memory",
            "size": "memory",
        }
        metric_name = metric_aliases.get(metric_name, metric_name)

        if metric_name in ["accuracy", "f1", "precision", "recall"]:
            metrics.append(
                Metric(
                    name=metric_name,
                    description=f"Model {metric_name}",
                    direction="maximize",
                    target=0.85,
                )
            )
        elif metric_name in ["speed", "latency", "time"]:
            metrics.append(
                Metric(
                    name="latency",
                    description="Inference latency",
                    direction="minimize",
                    target=100.0,  # ms
                )
            )
        elif metric_name in ["memory", "size"]:
            metrics.append(
                Metric(
                    name="memory",
                    description="Memory usage",
                    direction="minimize",
                    target=1000.0,  # MB
                )
            )
        else:
            # Default metric
            metrics.append(
                Metric(
                    name="performance",
                    description="Overall performance",
                    direction="maximize",
                    target=0.8,
                )
            )

        # Add cost metric
        metrics.append(
            Metric(
                name="cost",
                description="Experiment cost",
                direction="minimize",
                target=50.0,
            )
        )

        return metrics

    def _generate_constraints(self, idea: IdeaRecord) -> Constraints:
        """Generate experiment constraints.

        Args:
            idea: Research idea

        Returns:
            Constraints object
        """
        # Use user-provided constraints or defaults
        if idea.constraints:
            return Constraints(
                max_budget_usd=idea.constraints.get("max_budget_usd", 100.0),
                max_runtime_hours=idea.constraints.get("max_runtime_hours", 24.0),
                max_iterations=idea.constraints.get("max_iterations", 10),
                compute=idea.constraints.get("compute", "cpu"),
            )

        # Default constraints
        return Constraints(
            max_budget_usd=100.0,
            max_runtime_hours=24.0,
            max_iterations=10,
            compute="cpu",
        )
