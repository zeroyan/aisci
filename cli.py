"""AiSci CLI: experiment run management."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
import yaml

from src.llm.client import LLMClient, LLMConfig
from src.service.run_service import RunService
from src.storage.artifact import ArtifactStore
from src.agents.plan.plan_agent import PlanAgent
from src.agents.plan.revision_agent import RevisionAgent
from src.knowledge.store import KnowledgeStore
from src.schemas.plan_serializer import PlanSerializer
from src.schemas.research_spec import ResearchSpec

app = typer.Typer(name="aisci", help="AiSci: AI-driven autonomous experiment runner")
run_app = typer.Typer(help="Manage experiment runs")
plan_app = typer.Typer(help="Manage experiment plans")
app.add_typer(run_app, name="run")
app.add_typer(plan_app, name="plan")


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


# --- Plan Commands -----------------------------------------------------------


@plan_app.command("generate")
def plan_generate(
    spec: str = typer.Argument(help="Path to ResearchSpec JSON file"),
    run_id: str | None = typer.Option(None, "--run-id", "-r", help="Optional run ID for knowledge lookup"),
    out: str | None = typer.Option(None, "--out", "-o", help="Output file path (default: runs/<run_id>/plan.md)"),
    config: str | None = config_option,
) -> None:
    """Generate experiment plan from research specification."""
    cfg = _load_config(config)

    # Load spec
    spec_path = Path(spec)
    if not spec_path.exists():
        typer.echo(f"Error: Spec file not found: {spec}", err=True)
        raise typer.Exit(1)

    try:
        spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
        research_spec = ResearchSpec(**spec_data)
    except Exception as e:
        typer.echo(f"Error loading spec: {e}", err=True)
        raise typer.Exit(1)

    # Initialize components
    llm_cfg = cfg.get("llm", {})
    llm_config = LLMConfig(
        default_model=llm_cfg.get("default_model", "claude-sonnet-4-6"),
        fallback_model=llm_cfg.get("fallback_model", "gpt-4o-mini"),
        api_base=llm_cfg.get("api_base"),
        temperature=llm_cfg.get("temperature", 0.2),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        timeout_retries=llm_cfg.get("retry", {}).get("timeout_retries", 2),
        rate_limit_retries=llm_cfg.get("retry", {}).get("rate_limit_retries", 3),
    )
    llm_client = LLMClient(config=llm_config)

    knowledge_cfg = cfg.get("knowledge", {})
    knowledge_store = KnowledgeStore(
        scientist_dir=knowledge_cfg.get("scientist_dir", "scientist"),
        runs_dir=cfg.get("storage", {}).get("runs_dir", "runs"),
    )

    # Generate plan
    typer.echo("Generating experiment plan...")
    plan_agent = PlanAgent(llm_client=llm_client, knowledge_store=knowledge_store)

    try:
        plan = plan_agent.generate(spec=research_spec, run_id=run_id)

        # Serialize to markdown
        md_content = PlanSerializer.to_markdown(plan)

        # Determine output path
        if out:
            output_path = Path(out)
        else:
            # Default: runs/<run_id>/plan.md or runs/<plan_id>/plan.md
            target_run_id = run_id or plan.plan_id
            runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))
            output_path = runs_dir / target_run_id / "plan.md"

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        output_path.write_text(md_content, encoding="utf-8")

        typer.echo(f"✓ Plan generated: {output_path}")
        typer.echo(
            json.dumps(
                {
                    "plan_id": plan.plan_id,
                    "spec_id": plan.spec_id,
                    "version": plan.version,
                    "output_path": str(output_path),
                },
                indent=2,
            )
        )
    except Exception as e:
        typer.echo(f"Error generating plan: {e}", err=True)
        raise typer.Exit(1)


@plan_app.command("show")
def plan_show(
    run_id: str = typer.Argument(help="Run ID to show plan for"),
    config: str | None = config_option,
) -> None:
    """Show experiment plan for a run."""
    cfg = _load_config(config)
    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))
    plan_path = runs_dir / run_id / "plan.md"

    if not plan_path.exists():
        typer.echo(f"Error: Plan not found: {plan_path}", err=True)
        raise typer.Exit(1)

    try:
        # Load and parse plan
        md_content = plan_path.read_text(encoding="utf-8")
        plan = PlanSerializer.from_markdown(md_content)

        # Display plan info
        typer.echo(f"\n{'='*60}")
        typer.echo(f"Plan: {plan.title or 'Untitled'}")
        typer.echo(f"{'='*60}\n")
        typer.echo(f"Plan ID: {plan.plan_id}")
        typer.echo(f"Spec ID: {plan.spec_id}")
        typer.echo(f"Version: {plan.version}")
        typer.echo(f"Created: {plan.created_at.strftime('%Y-%m-%d %H:%M') if plan.created_at else 'N/A'}")
        typer.echo(f"Updated: {plan.updated_at.strftime('%Y-%m-%d %H:%M') if plan.updated_at else 'N/A'}")
        typer.echo(f"\nMethod Summary:\n{plan.method_summary}\n")

        if plan.technical_approach:
            typer.echo(f"Framework: {plan.technical_approach.framework}")
            if plan.technical_approach.baseline_methods:
                typer.echo(f"Baselines: {', '.join(plan.technical_approach.baseline_methods)}")

        typer.echo(f"\nSteps: {len(plan.steps)}")
        for i, step in enumerate(plan.steps, 1):
            typer.echo(f"  {i}. {step.description[:60]}...")

        if plan.revision_history:
            typer.echo(f"\nRevision History: {len(plan.revision_history)} revisions")
            for rev in plan.revision_history:
                typer.echo(f"  v{rev.version} ({rev.revised_at.strftime('%Y-%m-%d')}): {rev.summary}")

        typer.echo(f"\nFull plan: {plan_path}\n")

    except Exception as e:
        typer.echo(f"Error loading plan: {e}", err=True)
        raise typer.Exit(1)


@plan_app.command("revise")
def plan_revise(
    run_id: str = typer.Argument(help="Run ID to revise plan for"),
    report: str | None = typer.Option(None, "--report", "-r", help="Path to experiment report (default: runs/<run_id>/report.md)"),
    apply: bool = typer.Option(False, "--apply", "-a", help="Apply revisions and increment version (default: only append suggestions)"),
    config: str | None = config_option,
) -> None:
    """Generate revision suggestions for experiment plan based on results."""
    cfg = _load_config(config)
    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))

    # Determine paths
    plan_path = runs_dir / run_id / "plan.md"
    if report:
        report_path = Path(report)
    else:
        # Try report.md first, then report.json
        report_path = runs_dir / run_id / "report.md"
        if not report_path.exists():
            report_path = runs_dir / run_id / "report.json"

    # Validate paths
    if not plan_path.exists():
        typer.echo(f"Error: Plan not found: {plan_path}", err=True)
        raise typer.Exit(1)

    if not report_path.exists():
        typer.echo(f"Error: Report not found: {report_path}", err=True)
        raise typer.Exit(1)

    # Initialize LLM
    llm_cfg = cfg.get("llm", {})
    llm_config = LLMConfig(
        default_model=llm_cfg.get("default_model", "claude-sonnet-4-6"),
        fallback_model=llm_cfg.get("fallback_model", "gpt-4o-mini"),
        api_base=llm_cfg.get("api_base"),
        temperature=llm_cfg.get("temperature", 0.2),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        timeout_retries=llm_cfg.get("retry", {}).get("timeout_retries", 2),
        rate_limit_retries=llm_cfg.get("retry", {}).get("rate_limit_retries", 3),
    )
    llm_client = LLMClient(config=llm_config)

    # Create revision agent
    revision_agent = RevisionAgent(llm_client=llm_client)

    try:
        typer.echo(f"Generating revision suggestions for {run_id}...")

        if apply:
            # Load plan, generate suggestions, apply revisions, save
            md_content = plan_path.read_text(encoding="utf-8")
            plan = PlanSerializer.from_markdown(md_content)

            suggestions = revision_agent.suggest_revisions(plan, report_path)

            # Apply revisions
            updated_plan = revision_agent.apply_revisions(
                plan=plan,
                revision_summary=suggestions[:200],  # Use first 200 chars as summary
                revised_by="ai",
            )

            # Save updated plan
            updated_md = PlanSerializer.to_markdown(updated_plan)
            plan_path.write_text(updated_md, encoding="utf-8")

            typer.echo(f"✓ Plan revised and saved (version {updated_plan.version})")
            typer.echo(f"\nRevision Summary:\n{suggestions}\n")

        else:
            # Just append suggestions to plan.md
            plan = revision_agent.revise_plan_file(
                plan_path=plan_path,
                report_path=report_path,
                append_suggestions=True,
            )

            typer.echo(f"✓ Revision suggestions appended to {plan_path}")
            typer.echo(f"\nNext steps:")
            typer.echo(f"  1. Review suggestions in {plan_path}")
            typer.echo(f"  2. Edit plan manually if needed")
            typer.echo(f"  3. Run 'plan revise {run_id} --apply' to increment version\n")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
