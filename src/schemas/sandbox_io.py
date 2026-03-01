"""Agent-Sandbox interaction schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.schemas import ResourceUsage


# -- Sandbox request -----------------------------------------------------------


class CodeSnapshot(BaseModel):
    """Filename-to-content mapping with an entrypoint command."""

    model_config = ConfigDict(frozen=True)

    files: dict[str, str] = Field(min_length=1)
    entrypoint: str = Field(min_length=1)


class ResourceLimits(BaseModel):
    """Hardware constraints for a sandbox execution."""

    model_config = ConfigDict(frozen=True)

    max_memory_mb: int = 8192
    gpu_required: bool = False


class SandboxRequest(BaseModel):
    """Payload sent from the agent to the sandbox runner."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    iteration_index: int = Field(ge=1)
    action: Literal["execute"] = "execute"
    code_snapshot: CodeSnapshot
    timeout_sec: int = Field(default=1800, gt=0)
    resource_limits: ResourceLimits = ResourceLimits()

    @model_validator(mode="before")
    @classmethod
    def _coerce_timeout(cls, data: dict) -> dict:
        if isinstance(data, dict) and "timeout_sec" in data:
            try:
                data["timeout_sec"] = int(float(data["timeout_sec"]))
            except (ValueError, TypeError):
                pass
        return data


# -- Sandbox response ----------------------------------------------------------


class SandboxStatus(StrEnum):
    """Possible outcomes of a sandbox execution."""

    succeeded = "succeeded"
    failed = "failed"
    timeout = "timeout"
    oom = "oom"


class SandboxResponse(BaseModel):
    """Result returned from the sandbox runner to the agent."""

    request_id: str
    status: SandboxStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    output_files: dict[str, str] = {}
    resource_usage: ResourceUsage = ResourceUsage()
    started_at: datetime | None = None
    ended_at: datetime | None = None


# -- Agent decision ------------------------------------------------------------


class NextAction(BaseModel):
    """Describes the next step the agent intends to take."""

    model_config = ConfigDict(frozen=True)

    strategy: str
    rationale: str


class AgentDecision(BaseModel):
    """Agent's post-iteration decision on whether to continue the loop."""

    model_config = ConfigDict(frozen=True)

    iteration_id: str
    run_id: str
    decision: Literal["continue", "stop", "request_human"]
    stop_reason: (
        Literal["goal_met", "max_iterations", "no_progress", "fatal_error"] | None
    ) = None
    analysis_summary: str | None = None
    next_action: NextAction | None = None

    @model_validator(mode="before")
    @classmethod
    def _fix_literal_nulls(cls, data: dict) -> dict:
        """Handle LLM hallucinating 'null' string instead of actual null."""
        if isinstance(data, dict):
            if data.get("stop_reason") == "null":
                data["stop_reason"] = None
        return data

    @model_validator(mode="after")
    def _check_decision_fields(self) -> "AgentDecision":
        if self.decision == "stop" and self.stop_reason is None:
            raise ValueError("stop_reason is required when decision is 'stop'")
        if self.decision == "continue" and self.next_action is None:
            raise ValueError("next_action is required when decision is 'continue'")
        return self
