"""Pydantic models for research specifications and experiment plans."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.schemas import Baseline, Constraints, Metric, PlanStep


# -- Technical approach --------------------------------------------------------


class TechnicalApproach(BaseModel):
    """Technical implementation details for an experiment plan."""

    model_config = ConfigDict(frozen=True)

    framework: str  # Main framework/library (e.g., "PyTorch", "scikit-learn")
    baseline_methods: list[str] = Field(default_factory=list)
    key_references: list[str] = Field(default_factory=list)  # Paper URLs or arxiv IDs
    implementation_notes: str = ""


class RevisionEntry(BaseModel):
    """Record of a plan revision."""

    model_config = ConfigDict(frozen=True)

    version: int
    revised_at: datetime
    revised_by: Literal["human", "ai"]
    summary: str  # Revision summary
    trigger: str | None = None  # Trigger reason (e.g., run_id or manual note)


# -- Research spec -------------------------------------------------------------


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
    version: int = 1  # Revision version number
    title: str = ""  # Plan title
    method_summary: str = Field(min_length=1)
    technical_approach: TechnicalApproach | None = None  # New field
    evaluation_protocol: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)
    baseline: Baseline | None = None
    revision_history: list[RevisionEntry] = Field(default_factory=list)  # New field
    created_at: datetime | None = None
    updated_at: datetime | None = None  # New field
