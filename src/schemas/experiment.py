"""Pydantic models for experiment iterations and run state."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.schemas import CostUsage, ResourceUsage
from src.schemas.state import RunStatus, StopReason, validate_transition


class IterationStatus(StrEnum):
    """Execution status for a single iteration."""

    succeeded = "succeeded"
    failed = "failed"
    stopped = "stopped"


class ExperimentIteration(BaseModel):
    """Record of one plan->codegen->execute->analyze iteration."""

    model_config = ConfigDict(frozen=False)

    iteration_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    index: int = Field(ge=1)
    code_change_summary: str | None = None
    commands: list[str] = Field(min_length=1)
    params: dict[str, Any] | None = None
    metrics: dict[str, float] | None = None
    resource_usage: ResourceUsage = ResourceUsage()
    cost_usage: CostUsage
    status: IterationStatus
    error_summary: str | None = None
    artifact_dir: str = Field(min_length=1)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class ExperimentRun(BaseModel):
    """Top-level run state tracked across all iterations."""

    model_config = ConfigDict(frozen=False)

    run_id: str = Field(min_length=1)
    spec_id: str = Field(min_length=1)
    plan_id: str | None = None
    status: RunStatus = RunStatus.QUEUED
    stop_reason: StopReason | None = None
    iteration_count: int = Field(default=0, ge=0)
    best_iteration_id: str | None = None
    cost_usage: CostUsage = CostUsage()
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def transition_to(self, target: RunStatus) -> None:
        """Validate and apply a RunStatus transition."""
        validate_transition(self.status, target)
        self.status = target

