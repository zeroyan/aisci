"""Pydantic models for experiment iterations and runs."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.schemas import CostUsage, ResourceUsage
from src.schemas.state import RunStatus, StopReason, validate_transition


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IterationStatus(StrEnum):
    """Outcome of a single experiment iteration."""

    succeeded = "succeeded"
    failed = "failed"
    stopped = "stopped"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ExperimentIteration(BaseModel):
    """Snapshot of one iteration inside an experiment run."""

    model_config = ConfigDict(frozen=True)

    iteration_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    index: int = Field(ge=1)

    code_change_summary: str | None = None
    commands: list[str] = Field(min_length=1)
    params: dict | None = None
    metrics: dict[str, float] | None = None

    resource_usage: ResourceUsage | None = None
    cost_usage: CostUsage
    status: IterationStatus
    error_summary: str | None = None

    artifact_dir: str

    started_at: datetime | None = None
    ended_at: datetime | None = None


class ExperimentRun(BaseModel):
    """Top-level experiment run — mutable during execution."""

    # NOT frozen: status, cost, timestamps are updated in-place.
    model_config = ConfigDict(frozen=False)

    run_id: str = Field(min_length=1)
    spec_id: str = Field(min_length=1)
    plan_id: str | None = None

    status: RunStatus = RunStatus.QUEUED
    stop_reason: StopReason | None = None
    iteration_count: int = Field(default=0, ge=0)
    best_iteration_id: str | None = None

    cost_usage: CostUsage = Field(default_factory=CostUsage)

    created_at: datetime | None = None
    updated_at: datetime | None = None

    def transition_to(self, new_status: RunStatus) -> None:
        """Advance run status via the state machine; raises on invalid move."""
        validate_transition(self.status, new_status)
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
