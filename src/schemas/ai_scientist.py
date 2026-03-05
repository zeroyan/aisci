"""Data models for AI-Scientist integration.

This module defines the data structures used for managing AI-Scientist
async jobs, template packages, and job status.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"  # Queued, waiting for concurrent slot
    RUNNING = "running"  # Subprocess is running
    COMPLETED = "completed"  # Subprocess exited normally, result exists
    FAILED = "failed"  # Subprocess crashed, timeout, or error


class JobRecord(BaseModel):
    """Job record for AI-Scientist async tasks."""

    job_id: str = Field(..., description="Unique job identifier (UUID)")
    run_id: str = Field(..., description="Associated experiment run_id")
    pid: int | None = Field(None, description="Subprocess PID (None if pending)")
    status: JobStatus = Field(..., description="Job status")
    log_path: str = Field(..., description="Log file path")
    start_time: datetime = Field(..., description="Job start time")
    end_time: datetime | None = Field(None, description="Job end time")
    error: str | None = Field(None, description="Error message if failed")
    template_name: str = Field(..., description="Template name used")
    num_ideas: int = Field(..., ge=1, le=10, description="Number of ideas to generate")
    model: str = Field(..., description="Model to use (e.g., deepseek-chat)")
    writeup: str = Field(..., description="Writeup format (latex or md)")

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, v, info):
        """Validate end_time is after start_time."""
        if v is not None and "start_time" in info.data:
            if v < info.data["start_time"]:
                raise ValueError("end_time must be after start_time")
        return v


class TemplatePackage(BaseModel):
    """Template package for AI-Scientist."""

    template_name: str = Field(..., description="Template name")
    prompt_json: dict = Field(..., description="prompt.json content")
    seed_ideas_json: list[dict] = Field(..., description="seed_ideas.json content")
    runtime_args: dict = Field(..., description="Runtime arguments")

    @field_validator("seed_ideas_json")
    @classmethod
    def validate_ideas_count(cls, v):
        """Validate seed_ideas contains 1-10 ideas."""
        if not (1 <= len(v) <= 10):
            raise ValueError("seed_ideas must contain 1-10 ideas")
        return v

    @field_validator("prompt_json")
    @classmethod
    def validate_prompt_structure(cls, v):
        """Validate prompt_json contains required keys."""
        required_keys = {"system", "task"}
        if not required_keys.issubset(v.keys()):
            raise ValueError(f"prompt_json must contain keys: {required_keys}")
        return v
