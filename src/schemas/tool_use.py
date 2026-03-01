"""Tool-use agent schemas for experiment execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# -- Tool call & result --------------------------------------------------------


class ToolCall(BaseModel):
    """A single tool invocation request from the LLM."""

    model_config = ConfigDict(frozen=True)

    tool_name: Literal["write_file", "run_bash", "read_file", "finish"]
    arguments: dict[str, Any]
    call_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])


class ToolResult(BaseModel):
    """Result of executing a tool call in the sandbox."""

    call_id: str
    tool_name: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: str | None = None  # Dispatch layer exception (not sandbox error)


# -- Tool turn -----------------------------------------------------------------


class ToolTurn(BaseModel):
    """One LLM reasoning + tool calls + results cycle."""

    turn_index: int = Field(ge=1)
    calls: list[ToolCall]
    results: list[ToolResult]
    llm_reasoning: str | None = None  # LLM text output before tool calls


# -- Finish result -------------------------------------------------------------


class FinishResult(BaseModel):
    """Final outcome when the agent calls the 'finish' tool."""

    model_config = ConfigDict(frozen=True)

    summary: str  # Experiment conclusion summary
    artifacts: list[str] = Field(default_factory=list)  # Output file paths
    success: bool = True
    failure_reason: str | None = None


# -- Tool iteration record -----------------------------------------------------


class ToolIterationRecord(BaseModel):
    """Complete record of one tool-use iteration (replaces IterationRecord)."""

    run_id: str
    iteration_index: int = Field(ge=1)
    turns: list[ToolTurn] = Field(default_factory=list)
    finish_result: FinishResult | None = None
    total_turns: int = 0
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "finished", "failed", "timeout"] = "running"
