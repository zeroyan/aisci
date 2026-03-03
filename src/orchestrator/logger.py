"""Structured logging for orchestrator using structlog."""

import logging
import sys
from typing import Any

import structlog


def setup_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure structured logging for the orchestrator.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON format; otherwise human-readable
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def log_branch_start(logger: structlog.stdlib.BoundLogger, branch_id: str, **kwargs: Any) -> None:
    """Log branch execution start with context.

    Args:
        logger: Structured logger
        branch_id: Branch identifier
        **kwargs: Additional context fields
    """
    logger.info("branch_started", branch_id=branch_id, **kwargs)


def log_branch_complete(
    logger: structlog.stdlib.BoundLogger,
    branch_id: str,
    status: str,
    **kwargs: Any,
) -> None:
    """Log branch execution completion with context.

    Args:
        logger: Structured logger
        branch_id: Branch identifier
        status: Final status (success/failed)
        **kwargs: Additional context fields
    """
    logger.info("branch_completed", branch_id=branch_id, status=status, **kwargs)


def log_iteration(
    logger: structlog.stdlib.BoundLogger,
    branch_id: str,
    iteration: int,
    score: float,
    **kwargs: Any,
) -> None:
    """Log PEC loop iteration with context.

    Args:
        logger: Structured logger
        branch_id: Branch identifier
        iteration: Iteration number
        score: Critic score
        **kwargs: Additional context fields
    """
    logger.info(
        "iteration_completed",
        branch_id=branch_id,
        iteration=iteration,
        score=score,
        **kwargs,
    )
