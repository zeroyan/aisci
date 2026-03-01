"""AiSci CLI: experiment run management."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
import yaml

from src.llm.client import LLMConfig
from src.service.run_service import RunService
from src.storage.artifact import ArtifactStore

app = typer.Typer(name="aisci", help="AiSci: AI-driven autonomous experiment runner")
run_app = typer.Typer(help="Manage experiment runs")
app.add_typer(run_app, name="run")


def _load_config(config_path: str | None = None) -> dict:
    """Load YAML config, falling back to default."""
    path = Path(config_path) if config_path else Path("configs/default.yaml")
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def _build_service(config: dict) -> RunService:
    """Build RunService from config dict."""
    llm_cfg = config.get("llm", {})
    exp_cfg = config.get("experiment", {})
    storage_cfg = config.get("storage", {})

    llm_config = LLMConfig(
        default_model=llm_cfg.get("default_model", "claude-sonnet-4-6"),
        fallback_model=llm_cfg.get("fallback_model", "gpt-4o-mini"),
        api_base=llm_cfg.get("api_base"),
        temperature=llm_cfg.get("temperature", 0.2),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        timeout_retries=llm_cfg.get("retry", {}).get("timeout_retries", 2),
        rate_limit_retries=llm_cfg.get("retry", {}).get("rate_limit_retries", 3),
        rate_limit_base_delay_sec=llm_cfg.get("retry", {}).get(
            "rate_limit_base_delay_sec", 1.0
        ),
    )

    store = ArtifactStore(runs_dir=storage_cfg.get("runs_dir", "runs"))

    return RunService(
        store=store,
        llm_config=llm_config,
        consecutive_failure_limit=exp_cfg.get("consecutive_failure_limit", 3),
    )


# --- Commands ----------------------------------------------------------------

config_option = typer.Option(None, "--config", "-c", help="Path to YAML config file")


@run_app.command("create")
def run_create(
    spec: str = typer.Option(..., "--spec", "-s", help="Path to ResearchSpec JSON"),
    plan: str | None = typer.Option(
        None, "--plan", "-p", help="Path to ExperimentPlan JSON"
    ),
    config: str | None = config_option,
) -> None:
    """Create a new experiment run."""
    cfg = _load_config(config)
    svc = _build_service(cfg)

    try:
        run = svc.create_run(spec, plan)
        typer.echo(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "spec_id": run.spec_id,
                    "plan_id": run.plan_id,
                    "status": run.status,
                },
                indent=2,
            )
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@run_app.command("start")
def run_start(
    run_id: str = typer.Argument(help="Run ID to start"),
    config: str | None = config_option,
) -> None:
    """Start an experiment run (blocking)."""
    cfg = _load_config(config)
    svc = _build_service(cfg)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    try:
        run = svc.start_run(run_id)
        typer.echo(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "status": str(run.status),
                    "stop_reason": str(run.stop_reason) if run.stop_reason else None,
                    "iteration_count": run.iteration_count,
                    "cost_usd": run.cost_usage.estimated_cost_usd,
                },
                indent=2,
            )
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@run_app.command("stop")
def run_stop(
    run_id: str = typer.Argument(help="Run ID to stop"),
    config: str | None = config_option,
) -> None:
    """Stop a running experiment."""
    cfg = _load_config(config)
    svc = _build_service(cfg)

    try:
        run = svc.control_run(run_id, "stop")
        typer.echo(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "status": str(run.status),
                    "stop_reason": str(run.stop_reason) if run.stop_reason else None,
                },
                indent=2,
            )
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@run_app.command("status")
def run_status(
    run_id: str = typer.Argument(help="Run ID to check"),
    config: str | None = config_option,
) -> None:
    """Show current status of a run."""
    cfg = _load_config(config)
    svc = _build_service(cfg)

    try:
        run = svc.get_run(run_id)
        typer.echo(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "spec_id": run.spec_id,
                    "status": str(run.status),
                    "stop_reason": str(run.stop_reason) if run.stop_reason else None,
                    "iteration_count": run.iteration_count,
                    "cost_usd": run.cost_usage.estimated_cost_usd,
                    "created_at": run.created_at.isoformat()
                    if run.created_at
                    else None,
                    "updated_at": run.updated_at.isoformat()
                    if run.updated_at
                    else None,
                },
                indent=2,
            )
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@run_app.command("report")
def run_report(
    run_id: str = typer.Argument(help="Run ID to get report for"),
    out: str | None = typer.Option(None, "--out", "-o", help="Output file path"),
    config: str | None = config_option,
) -> None:
    """Get or generate experiment report."""
    cfg = _load_config(config)
    svc = _build_service(cfg)

    try:
        report = svc.get_run_report(run_id)
        report_json = json.dumps(report.model_dump(mode="json"), indent=2)

        if out:
            Path(out).write_text(report_json, encoding="utf-8")
            typer.echo(f"Report saved to {out}")
        else:
            typer.echo(report_json)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
