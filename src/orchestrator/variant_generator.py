"""Generate branch variants from ExperimentPlan."""

from typing import Any

from src.schemas.research_spec import ExperimentPlan


class BranchVariantGenerator:
    """Generate up to 3 branch variants from an ExperimentPlan.

    Each variant represents a different exploration direction:
    - Different hyperparameter combinations
    - Different implementation methods
    - Different baseline comparisons
    """

    def generate_variants(
        self, plan: ExperimentPlan, num_branches: int = 3
    ) -> list[dict[str, Any]]:
        """Generate branch variants from experiment plan.

        Args:
            plan: Experiment plan to generate variants from
            num_branches: Number of variants to generate (max 3)

        Returns:
            List of variant parameter dictionaries

        Raises:
            ValueError: If num_branches > 3
        """
        if num_branches > 3:
            raise ValueError(f"num_branches must be <= 3, got {num_branches}")

        variants = []

        # Variant 1: Baseline approach (always included)
        variants.append(self._generate_baseline_variant(plan))

        # Variant 2: Alternative method (if num_branches >= 2)
        if num_branches >= 2:
            variants.append(self._generate_alternative_variant(plan))

        # Variant 3: Aggressive exploration (if num_branches == 3)
        if num_branches == 3:
            variants.append(self._generate_aggressive_variant(plan))

        return variants[:num_branches]

    def _generate_baseline_variant(self, plan: ExperimentPlan) -> dict[str, Any]:
        """Generate baseline variant (conservative approach).

        Args:
            plan: Experiment plan

        Returns:
            Variant parameters for baseline approach
        """
        return {
            "variant_name": "baseline",
            "description": "Conservative baseline approach",
            "approach": (
                plan.technical_approach.framework
                if plan.technical_approach
                else "default"
            ),
            "exploration_strategy": "conservative",
            "risk_tolerance": "low",
        }

    def _generate_alternative_variant(self, plan: ExperimentPlan) -> dict[str, Any]:
        """Generate alternative variant (balanced approach).

        Args:
            plan: Experiment plan

        Returns:
            Variant parameters for alternative approach
        """
        return {
            "variant_name": "alternative",
            "description": "Balanced alternative approach",
            "approach": (
                plan.technical_approach.framework
                if plan.technical_approach
                else "default"
            ),
            "exploration_strategy": "balanced",
            "risk_tolerance": "medium",
        }

    def _generate_aggressive_variant(self, plan: ExperimentPlan) -> dict[str, Any]:
        """Generate aggressive variant (exploratory approach).

        Args:
            plan: Experiment plan

        Returns:
            Variant parameters for aggressive approach
        """
        return {
            "variant_name": "aggressive",
            "description": "Aggressive exploratory approach",
            "approach": (
                plan.technical_approach.framework
                if plan.technical_approach
                else "default"
            ),
            "exploration_strategy": "aggressive",
            "risk_tolerance": "high",
        }
