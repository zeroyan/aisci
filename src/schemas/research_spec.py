"""Pydantic models for research specifications and experiment plans."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schemas import Baseline, Constraints, Metric, PlanStep


class ResearchSpec(BaseModel):
    """Immutable research specification describing what to investigate."""

    model_config = ConfigDict(frozen=True)

    spec_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    hypothesis: list[str] = []
    metrics: list[Metric] = Field(min_length=1)
    constraints: Constraints
    dataset_refs: list[str] = []
    risk_notes: list[str] = []
    non_goals: list[str] = []
    status: Literal["draft", "confirmed"]
    created_by: Literal["user", "agent"] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExperimentPlan(BaseModel):
    """Immutable experiment plan tied to a research spec."""

    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(min_length=1)
    spec_id: str = Field(min_length=1)
    method_summary: str = Field(min_length=1)
    evaluation_protocol: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)
    baseline: Baseline | None = None
    created_at: datetime | None = None
