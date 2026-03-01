"""Immutable experiment report schema."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.schemas import BestResult, EvidenceEntry, FailedAttempt


class ExperimentReport(BaseModel):
    """Structured report generated after an experiment run completes."""

    model_config = ConfigDict(frozen=True)

    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    best_result: BestResult
    key_findings: list[str] = []
    failed_attempts: list[FailedAttempt] = []
    evidence_map: list[EvidenceEntry] = Field(min_length=1)
    next_actions: list[str] = []
    generated_at: datetime
