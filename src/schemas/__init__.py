"""Shared Pydantic v2 value objects for AiSci."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "CostUsage",
    "ResourceUsage",
    "Metric",
    "Constraints",
    "PlanStep",
    "Baseline",
    "BestResult",
    "FailedAttempt",
    "EvidenceEntry",
]


# -- Cost & Resource tracking -------------------------------------------------


class CostUsage(BaseModel):
    # Mutable on purpose: supports __add__ for accumulation.
    model_config = ConfigDict(frozen=False)

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = Field(default=0.0, ge=0)

    @field_validator("estimated_cost_usd", mode="after")
    @classmethod
    def _round_cost(cls, v: float) -> float:
        return round(v, 6)

    def __add__(self, other: CostUsage) -> CostUsage:
        return CostUsage(
            llm_calls=self.llm_calls + other.llm_calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            estimated_cost_usd=self.estimated_cost_usd + other.estimated_cost_usd,
        )


class ResourceUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    wall_time_sec: float = 0.0
    gpu_hours: float = 0.0
    peak_memory_mb: float = 0.0


# -- Experiment definition -----------------------------------------------------


class Metric(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    direction: Literal["maximize", "minimize"]
    target: float | None = None
    minimum_acceptable: float | None = None


class Constraints(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_budget_usd: float = Field(gt=0)
    max_runtime_hours: float = Field(gt=0)
    max_iterations: int = Field(gt=0)
    compute: Literal["cpu", "single_gpu", "multi_gpu"] = "cpu"


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    description: str
    expected_output: str


# -- Experiment results --------------------------------------------------------


class Baseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pending", "passed", "failed"]
    repo: str | None = None
    result_summary: str | None = None
    failure_reason: str | None = None


class BestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    iteration_id: str
    metrics: dict[str, float]


class FailedAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    iteration_id: str
    reason: str


# -- Paper / evidence ----------------------------------------------------------


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim: str
    evidence_paths: list[str] = Field(min_length=1)
