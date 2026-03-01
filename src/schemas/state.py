"""ExperimentRun state machine: statuses, stop reasons, and transition rules."""

from __future__ import annotations

from enum import StrEnum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RunStatus(StrEnum):
    """Lifecycle status of an experiment run."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"


class StopReason(StrEnum):
    """Why a run reached a terminal status."""

    GOAL_MET = "goal_met"
    MAX_ITERATIONS = "max_iterations"
    NO_PROGRESS = "no_progress"
    FATAL_ERROR = "fatal_error"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"
    USER_STOPPED = "user_stopped"


# ---------------------------------------------------------------------------
# Terminal statuses & transition rules
# ---------------------------------------------------------------------------

TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.STOPPED,
        RunStatus.BUDGET_EXHAUSTED,
        RunStatus.TIMEOUT,
    }
)

ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.PAUSED,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.STOPPED,
            RunStatus.BUDGET_EXHAUSTED,
            RunStatus.TIMEOUT,
        }
    ),
    RunStatus.PAUSED: frozenset({RunStatus.RUNNING, RunStatus.STOPPED}),
    # Terminal states have no outgoing transitions.
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.STOPPED: frozenset(),
    RunStatus.BUDGET_EXHAUSTED: frozenset(),
    RunStatus.TIMEOUT: frozenset(),
}


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def validate_transition(current: RunStatus, target: RunStatus) -> None:
    """Raise ``ValueError`` if *current* -> *target* is not a valid transition."""
    allowed = ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise ValueError(
            f"Invalid transition: {current.value!r} -> {target.value!r}. "
            f"Allowed targets from {current.value!r}: "
            f"{{{', '.join(sorted(s.value for s in allowed))}}}."
        )
