"""Pydantic schemas for orchestrator components."""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BudgetAllocation(BaseModel):
    """Budget allocation for a branch."""

    model_config = ConfigDict(frozen=True)

    max_cost_usd: float = Field(gt=0)
    max_time_hours: float = Field(gt=0)
    max_iterations: int = Field(gt=0)


class BranchConfig(BaseModel):
    """Configuration for a single branch."""

    model_config = ConfigDict(frozen=True)

    branch_id: str = Field(min_length=1)
    variant_params: dict[str, Any] = Field(default_factory=dict)
    initial_budget: BudgetAllocation
    workspace_path: Path


class PlannerOutput(BaseModel):
    """Output from Planner agent."""

    model_config = ConfigDict(frozen=True)

    reasoning: str = Field(min_length=1)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    expected_improvement: str = ""


class CriticFeedback(BaseModel):
    """Feedback from Critic agent."""

    model_config = ConfigDict(frozen=True)

    status: Literal["success", "failed", "needs_improvement"]
    feedback: str = Field(min_length=1)
    suggestions: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=100.0)  # 0-100 scale


class BranchResult(BaseModel):
    """Result from a single branch execution."""

    model_config = ConfigDict(frozen=True)

    branch_id: str
    status: Literal["success", "failed", "timeout"]
    iterations: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    time_seconds: float = Field(ge=0.0)
    best_code_path: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    report_path: str


class MemoryEntry(BaseModel):
    """Single memory entry for PEC loop history."""

    model_config = ConfigDict(frozen=True)

    iteration: int = Field(ge=1)
    planner_output: PlannerOutput
    execution_result: dict[str, Any]
    critic_feedback: CriticFeedback
    timestamp: datetime = Field(default_factory=datetime.now)
