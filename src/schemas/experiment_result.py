"""Unified experiment result schema for all execution engines."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExperimentResult(BaseModel):
    """Unified experiment result format for all execution engines."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    engine: Literal["aisci", "ai-scientist"]
    status: Literal["success", "failed", "timeout"]

    # Core results
    best_code_path: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)

    # Execution info
    total_cost_usd: float = Field(ge=0.0)
    total_time_seconds: float = Field(ge=0.0)
    iterations: int = Field(ge=0)

    # Optional: paper (AI-Scientist specific)
    paper_latex: str | None = None
    paper_pdf: str | None = None

    # Metadata
    created_at: datetime
    engine_version: str = Field(min_length=1)
