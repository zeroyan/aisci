"""Error types for the AiSci project."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    """Categorized error codes for AiSci operations."""

    llm_timeout = "llm_timeout"
    llm_rate_limit = "llm_rate_limit"
    sandbox_timeout = "sandbox_timeout"
    sandbox_oom = "sandbox_oom"
    sandbox_crash = "sandbox_crash"
    budget_exhausted = "budget_exhausted"
    schema_validation = "schema_validation"
    unknown = "unknown"


class AiSciError(BaseModel):
    """Structured error payload."""

    code: ErrorCode
    message: str
    retryable: bool
    details: dict | None = None


class ErrorResponse(BaseModel):
    """Top-level error response returned to callers."""

    error: AiSciError
    timestamp: datetime
    trace_id: str


class AiSciException(Exception):
    """Exception wrapper around AiSciError for raising in application code."""

    def __init__(self, error: AiSciError) -> None:
        self.error = error
        super().__init__(error.message)
