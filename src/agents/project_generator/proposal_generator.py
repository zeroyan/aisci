"""Proposal Generator for creating multiple candidate proposals."""

import uuid
from typing import Optional

from src.llm.client import LLMClient
from src.schemas.project_generator import EvidencePackage, IdeaRecord, ResearchProposal


class ProposalGenerator:
    """Generate multiple candidate research proposals."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize ProposalGenerator.

        Args:
            llm_client: LLM client for proposal generation
        """
        self.llm_client = llm_client or LLMClient()

    def generate_proposals(
        self,
        idea: IdeaRecord,
        evidence: EvidencePackage,
        num_proposals: int = 3,
    ) -> list[ResearchProposal]:
        """Generate multiple candidate proposals.

        Args:
            idea: Research idea
            evidence: Evidence package
            num_proposals: Number of proposals to generate (default 3)

        Returns:
            List of ResearchProposal objects
        """
        if num_proposals < 1:
            raise ValueError("num_proposals must be >= 1")

        proposals = []

        # Generate conservative proposal
        if num_proposals >= 1:
            proposals.append(self._generate_conservative(idea, evidence))

        # Generate balanced proposal
        if num_proposals >= 2:
            proposals.append(self._generate_balanced(idea, evidence))

        # Generate aggressive proposal
        if num_proposals >= 3:
            proposals.append(self._generate_aggressive(idea, evidence))

        return proposals[:num_proposals]

    def _generate_conservative(
        self, idea: IdeaRecord, evidence: EvidencePackage
    ) -> ResearchProposal:
        """Generate conservative (low-risk) proposal.

        Args:
            idea: Research idea
            evidence: Evidence package

        Returns:
            Conservative ResearchProposal
        """
        proposal_id = f"proposal_{uuid.uuid4().hex[:8]}"

        # Use first baseline if available
        baseline = (
            evidence.baselines[0].method_name
            if evidence.baselines
            else "Standard baseline"
        )

        title = f"Conservative: Reproduce {baseline} with minor improvements"
        objective = f"Replicate {baseline} and achieve incremental improvements on {idea.entities.get('task', 'the task')}"
        approach = f"Follow the methodology from {baseline}, make small targeted optimizations, validate against published results."

        return ResearchProposal(
            proposal_id=proposal_id,
            risk_profile="conservative",
            title=title,
            objective=objective,
            approach=approach,
            baseline_method=baseline,
            expected_metrics={"improvement": 1.05},  # 5% improvement
            risks=["Limited novelty", "Incremental contribution"],
            estimated_cost=30.0,
            estimated_time="2-3 days",
            evidence_support=self._build_evidence_support(evidence, limit=2),
        )

    def _generate_balanced(
        self, idea: IdeaRecord, evidence: EvidencePackage
    ) -> ResearchProposal:
        """Generate balanced (moderate-risk) proposal.

        Args:
            idea: Research idea
            evidence: Evidence package

        Returns:
            Balanced ResearchProposal
        """
        proposal_id = f"proposal_{uuid.uuid4().hex[:8]}"

        # Combine multiple baselines if available
        baselines = [b.method_name for b in evidence.baselines[:2]]
        baseline_str = " + ".join(baselines) if baselines else "Hybrid approach"

        title = f"Balanced: Combine {baseline_str}"
        objective = (
            f"Integrate strengths of {baseline_str} to achieve significant improvements"
        )
        approach = f"Combine techniques from {baseline_str}, conduct ablation studies, optimize hyperparameters."

        return ResearchProposal(
            proposal_id=proposal_id,
            risk_profile="balanced",
            title=title,
            objective=objective,
            approach=approach,
            baseline_method=baselines[0] if baselines else "Standard baseline",
            expected_metrics={"improvement": 1.15},  # 15% improvement
            risks=["Integration complexity", "Hyperparameter tuning required"],
            estimated_cost=60.0,
            estimated_time="4-5 days",
            evidence_support=self._build_evidence_support(evidence, limit=3),
        )

    def _generate_aggressive(
        self, idea: IdeaRecord, evidence: EvidencePackage
    ) -> ResearchProposal:
        """Generate aggressive (high-risk) proposal.

        Args:
            idea: Research idea
            evidence: Evidence package

        Returns:
            Aggressive ResearchProposal
        """
        proposal_id = f"proposal_{uuid.uuid4().hex[:8]}"

        baseline = (
            evidence.baselines[0].method_name if evidence.baselines else "Current SOTA"
        )

        title = f"Aggressive: Novel approach beyond {baseline}"
        objective = f"Explore novel techniques that go beyond {baseline} to achieve breakthrough results"
        approach = f"Investigate unexplored directions, test novel architectures, push boundaries of {baseline}."

        return ResearchProposal(
            proposal_id=proposal_id,
            risk_profile="aggressive",
            title=title,
            objective=objective,
            approach=approach,
            baseline_method=baseline,
            expected_metrics={"improvement": 1.30},  # 30% improvement
            risks=[
                "High failure risk",
                "May not converge",
                "Requires significant compute",
            ],
            estimated_cost=100.0,
            estimated_time="7-10 days",
            evidence_support=self._build_evidence_support(evidence, limit=5),
        )

    def _build_evidence_support(
        self, evidence: EvidencePackage, limit: int
    ) -> list[str]:
        """Build non-empty evidence support list for proposal validation."""
        paper_ids = [p.paper_id for p in evidence.papers[:limit] if p.paper_id]
        if paper_ids:
            return paper_ids

        baseline_refs = [
            b.paper_reference for b in evidence.baselines[:limit] if b.paper_reference
        ]
        if baseline_refs:
            return baseline_refs

        return ["evidence_unavailable"]
