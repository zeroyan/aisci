"""AiSci CLI: experiment run management."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from src.llm.client import LLMClient, LLMConfig
from src.service.run_service import RunService
from src.storage.artifact import ArtifactStore
from src.agents.plan.plan_agent import PlanAgent
from src.agents.plan.revision_agent import RevisionAgent
from src.agents.experiment.loop import ExperimentLoop
from src.knowledge.store import KnowledgeStore
from src.schemas.experiment import ExperimentRun, ExperimentIteration, IterationStatus
from src.schemas.experiment_result import ExperimentResult
from src.schemas.plan_serializer import PlanSerializer
from src.schemas.research_spec import ResearchSpec
from src.schemas.state import RunStatus, StopReason
from src.sandbox.subprocess_sandbox import SubprocessSandbox

app = typer.Typer(name="aisci", help="AiSci: AI-driven autonomous experiment runner")
run_app = typer.Typer(help="Manage experiment runs")
plan_app = typer.Typer(help="Manage experiment plans")
app.add_typer(run_app, name="run")
app.add_typer(plan_app, name="plan")

# Import and register project commands (Spec 005)
from src.agents.project_generator.cli_commands import project_app
app.add_typer(project_app, name="project")


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


def _build_llm_client(config: dict) -> LLMClient:
    """Build LLM client from shared config."""
    llm_cfg = config.get("llm", {})
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
    return LLMClient(config=llm_config)


def _persist_orchestrator_result(run_id: str, cfg: dict, result: ExperimentResult) -> None:
    """Persist orchestrator summary into run.json for status/report commands."""
    runs_dir = cfg.get("storage", {}).get("runs_dir", "runs")
    store = ArtifactStore(runs_dir=runs_dir)
    run_data = store.load_json(run_id, "run.json")
    run = ExperimentRun(**run_data)

    final_status = RunStatus.SUCCEEDED if result.status == "success" else RunStatus.FAILED

    try:
        if run.status == RunStatus.QUEUED:
            run.transition_to(RunStatus.RUNNING)
        if run.status == RunStatus.RUNNING:
            run.transition_to(final_status)
        else:
            run.status = final_status
    except ValueError:
        run.status = final_status

    run.iteration_count = result.iterations
    run.cost_usage.estimated_cost_usd = result.total_cost_usd
    run.updated_at = datetime.now(timezone.utc)
    run.stop_reason = StopReason.FATAL_ERROR if final_status == RunStatus.FAILED else None
    store.save_json(run_id, "run.json", run)


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
    enable_docker: bool = typer.Option(
        False, "--enable-docker", help="Use Docker sandbox for isolation"
    ),
    enable_orchestrator: bool = typer.Option(
        False, "--enable-orchestrator", help="Use multi-branch orchestrator"
    ),
    num_branches: int = typer.Option(
        3, "--num-branches", help="Number of parallel branches (1-3)"
    ),
    engine: str = typer.Option(
        "aisci", "--engine", help="Execution engine: aisci, ai-scientist, or hybrid"
    ),
    num_ideas: int = typer.Option(
        2, "--num-ideas", help="Number of ideas for ai-scientist engine (1-10)"
    ),
    writeup: str = typer.Option(
        "md", "--writeup", help="Writeup format for ai-scientist: latex or md"
    ),
    model: str = typer.Option(
        "deepseek-chat", "--model", help="Model for ai-scientist engine"
    ),
) -> None:
    """Start an experiment run (blocking).

    Use --enable-orchestrator for multi-branch parallel execution.
    Use --engine to select execution engine (aisci, ai-scientist, hybrid).
    """
    # Validate engine parameter
    valid_engines = ["aisci", "ai-scientist", "hybrid"]
    if engine not in valid_engines:
        typer.echo(
            f"Error: Invalid engine '{engine}'. Must be one of: {', '.join(valid_engines)}",
            err=True
        )
        raise typer.Exit(1)

    # Validate num_ideas range
    if not (1 <= num_ideas <= 10):
        typer.echo(
            f"Error: num_ideas must be between 1 and 10, got {num_ideas}",
            err=True
        )
        raise typer.Exit(1)

    # Validate writeup format
    if writeup not in ["latex", "md"]:
        typer.echo(
            f"Error: writeup must be 'latex' or 'md', got '{writeup}'",
            err=True
        )
        raise typer.Exit(1)

    cfg = _load_config(config)
    if enable_docker:
        cfg.setdefault("experiment", {})["enable_docker"] = True

    # Route to appropriate engine
    if engine == "ai-scientist":
        _run_ai_scientist_engine(run_id, cfg, model, num_ideas, writeup)
        return
    elif engine == "hybrid":
        _run_hybrid_engine(run_id, cfg, model, num_ideas, writeup, enable_docker)
        return

    # Default: aisci engine

    # If orchestrator is enabled, delegate to orchestrator_run
    if enable_orchestrator:
        from pathlib import Path
        from src.orchestrator.branch_orchestrator import BranchOrchestrator
        from src.orchestrator.config import OrchestratorConfig
        from src.schemas.research_spec import ResearchSpec

        # Load spec and plan from run directory
        runs_dir = Path("runs")
        spec_path = runs_dir / run_id / "spec" / "research_spec.json"
        plan_path = runs_dir / run_id / "plan" / "experiment_plan.json"

        if not spec_path.exists():
            typer.echo(f"Error: Research spec not found: {spec_path}", err=True)
            raise typer.Exit(1)

        if not plan_path.exists():
            typer.echo(f"Error: Experiment plan not found: {plan_path}", err=True)
            raise typer.Exit(1)

        # Load spec and plan
        spec = ResearchSpec.model_validate_json(spec_path.read_text())

        # Load plan from JSON (experiment_plan.json is JSON format)
        import json
        plan_data = json.loads(plan_path.read_text())
        from src.schemas.research_spec import ExperimentPlan
        plan = ExperimentPlan.model_validate(plan_data)

        # Create LLM client from app config (supports local ollama/qwen3)
        llm_client = _build_llm_client(cfg)

        # Create orchestrator config (immutable, so create new instance)
        base_config = OrchestratorConfig.default()
        orchestrator_config = OrchestratorConfig(
            orchestrator=base_config.orchestrator.model_copy(
                update={"num_branches": num_branches}
            ),
            budget=base_config.budget,
            docker=base_config.docker.model_copy(
                update={"enabled": enable_docker}
            ),
            memory=base_config.memory,
            logging=base_config.logging,
        )

        # Run orchestrator
        orchestrator = BranchOrchestrator(orchestrator_config, llm_client)
        result = orchestrator.run(
            spec=spec,
            plan=plan,
            run_id=run_id,
            runs_dir=runs_dir,
        )
        _persist_orchestrator_result(run_id, cfg, result)

        # Display results
        typer.echo("✓ Orchestration completed")
        typer.echo(f"  Status: {result.status}")
        typer.echo(f"  Total cost: ${result.total_cost_usd:.2f}")
        typer.echo(f"  Total time: {result.total_time_seconds:.1f}s")
        typer.echo(f"  Iterations: {result.iterations}")

        if result.best_code_path:
            typer.echo(f"  Best code: {result.best_code_path}")
        return

    # Otherwise use standard single-branch execution
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


@run_app.command("external-status")
def run_external_status(
    run_id: str = typer.Argument(help="Run ID to check"),
    config: str | None = config_option,
) -> None:
    """Check status of AI-Scientist external job."""
    from pathlib import Path
    from src.integrations.ai_scientist.adapter import AIScientistAdapter
    from src.integrations.ai_scientist.job_store import JobStore

    cfg = _load_config(config)
    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))

    # Initialize adapter and job store
    runtime_path = Path("external/ai-scientist-runtime")
    adapter = AIScientistAdapter(runtime_path)
    job_store_path = runs_dir / run_id / "external" / "jobs.jsonl"
    job_store = JobStore(job_store_path, max_concurrent=2)

    # Get all jobs for this run
    jobs = job_store.list_all()
    if not jobs:
        typer.echo(f"No external jobs found for run {run_id}", err=True)
        raise typer.Exit(1)

    # Display status for each job
    typer.echo(f"External jobs for run {run_id}:\n")
    for job in jobs:
        status_info = adapter.get_status(job, job_store)

        typer.echo(f"Job ID: {job.job_id}")
        typer.echo(f"  Status: {status_info['status']}")
        typer.echo(f"  Progress: {status_info['progress']}")
        typer.echo(f"  Elapsed: {status_info['elapsed_time']}")
        typer.echo(f"  Log: {status_info['log_path']}")
        if status_info.get("workspace_path"):
            typer.echo(f"  Workspace: {status_info['workspace_path']}")

        if status_info.get('error'):
            typer.echo(f"  Error: {status_info['error']}")
        typer.echo()


@run_app.command("external-fetch")
def run_external_fetch(
    run_id: str = typer.Argument(help="Run ID to fetch results"),
    config: str | None = config_option,
) -> None:
    """Fetch results from AI-Scientist jobs that already produced outputs."""
    from pathlib import Path
    import uuid
    from datetime import timezone
    from src.schemas import BestResult, EvidenceEntry
    from src.schemas.report import ExperimentReport
    from src.schemas.experiment import ExperimentRun
    from src.schemas.state import RunStatus, StopReason
    from src.schemas.ai_scientist import JobStatus
    from src.integrations.ai_scientist.adapter import AIScientistAdapter
    from src.integrations.ai_scientist.job_store import JobStore
    from src.integrations.ai_scientist.result_parser import ResultParser
    from datetime import datetime

    cfg = _load_config(config)
    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))

    # Initialize components
    runtime_path = Path("external/ai-scientist-runtime")
    adapter = AIScientistAdapter(runtime_path)
    job_store_path = runs_dir / run_id / "external" / "jobs.jsonl"
    job_store = JobStore(job_store_path, max_concurrent=2)

    jobs = job_store.list_all()
    if not jobs:
        typer.echo(f"No external jobs found for run {run_id}", err=True)
        raise typer.Exit(1)

    fetched_count = 0
    for job in jobs:
        # Parse results - AI-Scientist outputs to results/<experiment>/
        result_dir = runtime_path / "results" / job.template_name
        parser = ResultParser(result_dir)
        parsed = parser.parse_result_dir()
        if not parsed:
            continue

        typer.echo(f"Fetching results for job {job.job_id}...")

        # Convert to ExperimentResult
        experiment_result = parser.to_experiment_result(
            run_id=run_id,
            job_id=job.job_id,
            template_name=job.template_name,
            start_time=job.start_time,
            end_time=job.end_time or datetime.now(),
        )

        if not experiment_result:
            typer.echo(f"  No results found", err=True)
            continue

        # Copy artifacts to run directory
        artifacts_dir = parser.copy_artifacts_to_run_dir(
            run_id=run_id,
            job_id=job.job_id,
            runs_dir=runs_dir,
        )

        # Save ExperimentResult JSON
        output_dir = runs_dir / run_id / "external" / "ai_scientist"
        output_dir.mkdir(parents=True, exist_ok=True)

        result_file = output_dir / f"result_{job.job_id}.json"
        result_file.write_text(experiment_result.model_dump_json(indent=2))

        typer.echo(f"  ✓ Results saved to {result_file}")
        typer.echo(f"  ✓ Artifacts copied to {artifacts_dir}")
        typer.echo(f"  Status: {experiment_result.status}")
        typer.echo(f"  Metrics: {len(experiment_result.metrics)}")
        typer.echo(f"  Artifacts: {len(experiment_result.artifacts)}")
        typer.echo(f"  Time: {experiment_result.total_time_seconds:.1f}s")
        typer.echo()
        fetched_count += 1

        # Reconcile stale job status: results exist and are parsed successfully.
        if job.status != JobStatus.COMPLETED:
            job.status = JobStatus.COMPLETED
            job.end_time = job.end_time or datetime.now()
            job.error = None
            job_store.save(job)

        # Sync external result into run.json + report.json for final delivery.
        run_json_path = runs_dir / run_id / "run.json"
        if run_json_path.exists():
            run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
            run_obj = ExperimentRun(**run_data)
            run_obj.status = (
                RunStatus.SUCCEEDED
                if experiment_result.status == "success"
                else RunStatus.FAILED
            )
            run_obj.stop_reason = (
                StopReason.GOAL_MET
                if experiment_result.status == "success"
                else StopReason.FATAL_ERROR
            )
            run_obj.updated_at = datetime.now(timezone.utc)
            run_obj.engine = "ai-scientist"
            run_obj.external_metadata = {
                **(run_obj.external_metadata or {}),
                "job_id": job.job_id,
                "template_name": job.template_name,
                "result_file": str(result_file),
                "artifacts_dir": str(artifacts_dir),
                "ai_scientist_status": experiment_result.status,
            }
            run_json_path.write_text(
                json.dumps(run_obj.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            best_metrics = experiment_result.metrics or {"no_metrics": 0.0}
            report = ExperimentReport(
                report_id=f"report_{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                summary=(
                    f"External AI-Scientist job {job.job_id} fetched successfully. "
                    f"Status={experiment_result.status}, time={experiment_result.total_time_seconds:.1f}s."
                ),
                best_result=BestResult(
                    iteration_id=f"external:{job.job_id}",
                    metrics=best_metrics,
                ),
                key_findings=[
                    f"External status: {experiment_result.status}",
                    f"Artifacts: {len(experiment_result.artifacts)}",
                    f"Best code path: {experiment_result.best_code_path or 'N/A'}",
                ],
                failed_attempts=[],
                evidence_map=[
                    EvidenceEntry(
                        claim="AI-Scientist external execution result imported",
                        evidence_paths=[
                            f"external/ai_scientist/result_{job.job_id}.json",
                            f"external/ai_scientist/artifacts/{job.job_id}/report.md",
                        ],
                    )
                ],
                next_actions=[],
                generated_at=datetime.now(timezone.utc),
            )
            (runs_dir / run_id / "report.json").write_text(
                json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    if fetched_count == 0:
        typer.echo(
            f"No parseable AI-Scientist outputs found for run {run_id}",
            err=True,
        )
        raise typer.Exit(1)


@run_app.command("external-cancel")
def run_external_cancel(
    run_id: str = typer.Argument(help="Run ID to cancel"),
    config: str | None = config_option,
    force: bool = typer.Option(False, "--force", "-f", help="Force kill (SIGKILL)"),
) -> None:
    """Cancel running AI-Scientist job."""
    from pathlib import Path
    from src.integrations.ai_scientist.adapter import AIScientistAdapter
    from src.integrations.ai_scientist.job_store import JobStore

    cfg = _load_config(config)
    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))

    # Initialize components
    runtime_path = Path("external/ai-scientist-runtime")
    adapter = AIScientistAdapter(runtime_path)
    job_store_path = runs_dir / run_id / "external" / "jobs.jsonl"
    job_store = JobStore(job_store_path, max_concurrent=2)

    # Get running jobs
    running_jobs = [j for j in job_store.list_all() if j.status == "running"]
    if not running_jobs:
        typer.echo(f"No running jobs found for run {run_id}", err=True)
        raise typer.Exit(1)

    # Cancel each running job
    for job in running_jobs:
        typer.echo(f"Cancelling job {job.job_id}...")

        try:
            adapter.cancel_job(job, job_store, force=force)
            typer.echo(f"  ✓ Job cancelled")
        except Exception as e:
            typer.echo(f"  ✗ Failed to cancel: {e}", err=True)


@run_app.command("check-env")
def run_check_env(
    model: str = typer.Option("deepseek-chat", "--model", "-m", help="Model to validate"),
    config: str | None = config_option,
) -> None:
    """Check AI-Scientist environment setup."""
    from pathlib import Path
    from src.integrations.ai_scientist.adapter import AIScientistAdapter

    runtime_path = Path("external/ai-scientist-runtime")
    adapter = AIScientistAdapter(runtime_path)

    typer.echo("Checking AI-Scientist environment...\n")

    # Run validation
    result = adapter.validate_environment(model=model)

    # Display results
    if result["valid"]:
        typer.echo("✓ Environment is ready!")
    else:
        typer.echo("✗ Environment validation failed\n")

    if result["errors"]:
        typer.echo("Errors:")
        for error in result["errors"]:
            typer.echo(f"  ✗ {error}")
        typer.echo()

    if result["warnings"]:
        typer.echo("Warnings:")
        for warning in result["warnings"]:
            typer.echo(f"  ⚠ {warning}")
        typer.echo()

    # Show installation guide if needed
    if not result["valid"]:
        typer.echo("\nInstallation Guide:")
        typer.echo(adapter.get_installation_guide())
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
            typer.echo("\nNext steps:")
            typer.echo(f"  1. Review suggestions in {plan_path}")
            typer.echo("  2. Edit plan manually if needed")
            typer.echo(f"  3. Run 'plan revise {run_id} --apply' to increment version\n")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ============================================================================
# Orchestrator Commands (Spec 003)
# ============================================================================

orchestrator_app = typer.Typer(help="Multi-branch orchestration")
app.add_typer(orchestrator_app, name="orchestrator")


@orchestrator_app.command("run")
def orchestrator_run(
    run_id: str = typer.Argument(..., help="Run identifier"),
    num_branches: int = typer.Option(3, help="Number of parallel branches (1-3)"),
    max_cost_usd: float = typer.Option(10.0, help="Maximum cost in USD"),
    max_time_seconds: float = typer.Option(3600.0, help="Maximum time in seconds"),
    enable_docker: bool = typer.Option(False, help="Enable Docker isolation"),
    config_path: str | None = typer.Option(None, help="Path to config file"),
) -> None:
    """Run multi-branch experiment orchestration.

    Example:
        aisci orchestrator run run_001 --num-branches 3 --max-cost-usd 10.0
    """
    try:
        from pathlib import Path
        import json

        from src.orchestrator.branch_orchestrator import BranchOrchestrator
        from src.orchestrator.config import OrchestratorConfig
        from src.schemas.research_spec import ResearchSpec, ExperimentPlan

        # Load configuration
        if config_path:
            config = OrchestratorConfig.from_yaml(config_path)
        else:
            config = OrchestratorConfig.default()

        # Override with CLI parameters
        config = config.model_copy(
            update={
                "orchestrator": config.orchestrator.model_copy(
                    update={"num_branches": num_branches}
                ),
                "budget": config.budget.model_copy(
                    update={
                        "max_cost_usd": max_cost_usd,
                        "max_time_seconds": max_time_seconds,
                    }
                ),
                "docker": config.docker.model_copy(update={"enabled": enable_docker}),
            }
        )

        # Create LLM client from app config (supports local ollama/qwen3)
        llm_client = _build_llm_client(_load_config())

        # Load spec and plan
        runs_dir = Path("runs")
        spec_path = runs_dir / run_id / "spec" / "research_spec.json"
        plan_path = runs_dir / run_id / "plan" / "experiment_plan.json"

        if not spec_path.exists():
            typer.echo(f"Error: Research spec not found: {spec_path}", err=True)
            raise typer.Exit(1)

        if not plan_path.exists():
            typer.echo(f"Error: Experiment plan not found: {plan_path}", err=True)
            raise typer.Exit(1)

        # Load spec
        spec = ResearchSpec.model_validate_json(spec_path.read_text())

        # Load plan from JSON
        import json
        plan_data = json.loads(plan_path.read_text())
        plan = ExperimentPlan.model_validate(plan_data)

        # Create orchestrator
        orchestrator = BranchOrchestrator(config=config, llm_client=llm_client)

        # Run orchestration
        typer.echo(f"Starting multi-branch orchestration for {run_id}...")
        typer.echo(f"  Branches: {num_branches}")
        typer.echo(f"  Max cost: ${max_cost_usd:.2f}")
        typer.echo(f"  Max time: {max_time_seconds:.0f}s")
        typer.echo(f"  Docker: {'enabled' if enable_docker else 'disabled'}")
        typer.echo()

        result = orchestrator.run(
            spec=spec,
            plan=plan,
            run_id=run_id,
            runs_dir=runs_dir,
        )
        _persist_orchestrator_result(run_id, _load_config(), result)

        # Display results
        typer.echo("✓ Orchestration completed")
        typer.echo(f"  Status: {result.status}")
        typer.echo(f"  Total cost: ${result.total_cost_usd:.2f}")
        typer.echo(f"  Total time: {result.total_time_seconds:.1f}s")
        typer.echo(f"  Iterations: {result.iterations}")

        if result.best_code_path:
            typer.echo(f"  Best code: {result.best_code_path}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# --- AI-Scientist Engine Functions -------------------------------------------


def _run_ai_scientist_engine(
    run_id: str,
    cfg: dict,
    model: str,
    num_ideas: int,
    writeup: str,
) -> None:
    """Run AI-Scientist engine asynchronously."""
    from pathlib import Path
    from src.integrations.ai_scientist.adapter import AIScientistAdapter
    from src.integrations.ai_scientist.job_store import JobStore

    # Initialize adapter
    runtime_path = Path("external/ai-scientist-runtime")
    adapter = AIScientistAdapter(runtime_path)

    # Check if AI-Scientist is installed
    if not adapter.is_installed():
        typer.echo(
            "Error: AI-Scientist not found. Please initialize the submodule:\n"
            "  git submodule update --init external/ai-scientist-runtime",
            err=True
        )
        raise typer.Exit(1)

    # Initialize job store
    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))
    job_store_path = runs_dir / run_id / "external" / "jobs.jsonl"
    job_store = JobStore(job_store_path, max_concurrent=2)

    # Load spec and plan
    spec_path = runs_dir / run_id / "spec" / "research_spec.json"
    if not spec_path.exists():
        typer.echo(f"Error: Research spec not found: {spec_path}", err=True)
        raise typer.Exit(1)

    from src.schemas.research_spec import ResearchSpec
    spec = ResearchSpec.model_validate_json(spec_path.read_text())

    # Submit job
    typer.echo(f"Submitting AI-Scientist job for run {run_id}...")
    typer.echo(f"  Model: {model}")
    typer.echo(f"  Ideas: {num_ideas}")
    typer.echo(f"  Writeup: {writeup}")

    try:
        job_id = adapter.submit_job(
            run_id=run_id,
            spec=spec,
            model=model,
            num_ideas=num_ideas,
            writeup=writeup,
            job_store=job_store,
        )

        # Update main run status to RUNNING with external metadata
        run_json_path = runs_dir / run_id / "run.json"
        if run_json_path.exists():
            run_data = json.loads(run_json_path.read_text())
            run = ExperimentRun(**run_data)
            run.status = RunStatus.RUNNING
            run.engine = "ai-scientist"
            run.external_metadata = {
                "job_id": job_id,
                "model": model,
                "num_ideas": num_ideas,
                "writeup": writeup,
            }
            run.updated_at = datetime.now(timezone.utc)
            run_json_path.write_text(
                json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

        typer.echo(f"\n✓ Job submitted successfully")
        typer.echo(f"  Job ID: {job_id}")
        typer.echo(f"\nCheck status with:")
        typer.echo(f"  python cli.py run external-status {run_id}")
        typer.echo(f"\nFetch results with:")
        typer.echo(f"  python cli.py run external-fetch {run_id}")

    except Exception as e:
        typer.echo(f"Error submitting job: {e}", err=True)
        raise typer.Exit(1)


def _run_hybrid_engine(
    run_id: str,
    cfg: dict,
    model: str,
    num_ideas: int,
    writeup: str,
    enable_docker: bool,
) -> None:
    """Run hybrid engine: AiSci baseline → AI-Scientist."""
    import json
    import shutil
    from datetime import datetime, timezone
    from pathlib import Path

    from src.integrations.ai_scientist.adapter import AIScientistAdapter
    from src.integrations.ai_scientist.callbacks import JobCallbacks
    from src.integrations.ai_scientist.job_store import JobStore
    from src.integrations.ai_scientist.result_parser import ResultParser
    from src.schemas.research_spec import ExperimentPlan
    from src.schemas.state import RunStatus

    del enable_docker  # Reserved for future dockerized baseline execution.

    typer.echo("=" * 60)
    typer.echo("HYBRID MODE: AiSci Baseline -> AI-Scientist")
    typer.echo("=" * 60)

    runs_dir = Path(cfg.get("storage", {}).get("runs_dir", "runs"))
    run_dir = runs_dir / run_id
    spec_path = run_dir / "spec" / "research_spec.json"
    plan_path = run_dir / "plan" / "experiment_plan.json"

    if not spec_path.exists():
        typer.echo(f"Error: Research spec not found: {spec_path}", err=True)
        raise typer.Exit(1)
    if not plan_path.exists():
        typer.echo(f"Error: Experiment plan not found: {plan_path}", err=True)
        raise typer.Exit(1)

    spec = ResearchSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    plan = ExperimentPlan.model_validate(plan_data)

    # ========================================================================
    # PHASE 1: Baseline (single AiSci iteration)
    # ========================================================================
    typer.echo("\n" + "=" * 60)
    typer.echo("PHASE 1: Baseline with AiSci (max_iterations=1)")
    typer.echo("=" * 60)

    baseline_spec = spec.model_copy(
        update={
            "constraints": spec.constraints.model_copy(update={"max_iterations": 1})
        }
    )
    baseline_run_id = f"{run_id}_baseline"
    baseline_runs_dir = run_dir / "hybrid_baseline_runs"
    baseline_store = ArtifactStore(runs_dir=baseline_runs_dir)
    baseline_llm = _build_llm_client(cfg)
    baseline_sandbox = SubprocessSandbox(runs_dir=baseline_runs_dir)
    baseline_loop = ExperimentLoop(
        llm=baseline_llm,
        sandbox=baseline_sandbox,
        store=baseline_store,
        max_turns_per_iteration=20,
    )

    baseline_run = ExperimentRun(
        run_id=baseline_run_id,
        spec_id=spec.spec_id,
        plan_id=plan.plan_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        engine="aisci",
    )

    try:
        baseline_final = baseline_loop.run(
            experiment_run=baseline_run,
            spec=baseline_spec,
            plan=plan,
        )
    except Exception as e:
        typer.echo(f"Error generating baseline: {e}", err=True)
        raise typer.Exit(1)

    # Baseline must produce at least one completed iteration artifact.
    if baseline_final.status == RunStatus.FAILED or baseline_final.iteration_count == 0:
        typer.echo(
            f"Error: Baseline generation failed (status={baseline_final.status}, "
            f"iterations={baseline_final.iteration_count})",
            err=True,
        )
        raise typer.Exit(1)

    baseline_metrics: dict[str, float] = {}
    baseline_iteration_status: str | None = None
    baseline_iter_file = (
        baseline_store.run_path(baseline_run_id)
        / "iterations"
        / "it_0001"
        / "iteration.json"
    )
    if baseline_iter_file.exists():
        iter_data = json.loads(baseline_iter_file.read_text(encoding="utf-8"))
        baseline_iteration_status = iter_data.get("status")
        if isinstance(iter_data.get("metrics"), dict):
            baseline_metrics = iter_data["metrics"]
    if baseline_iteration_status != "succeeded":
        typer.echo(
            "Error: Baseline iteration did not succeed, aborting hybrid execution. "
            f"(iteration_status={baseline_iteration_status}, run_status={baseline_final.status})",
            err=True,
        )
        raise typer.Exit(1)
    if not baseline_metrics:
        baseline_metrics = {"baseline_score": 0.0}

    typer.echo("Baseline completed")
    typer.echo(f"  Status: {baseline_final.status}")
    typer.echo(f"  Metrics: {baseline_metrics}")

    # ========================================================================
    # PHASE 2: Build dynamic AI-Scientist template
    # ========================================================================
    typer.echo("\n" + "=" * 60)
    typer.echo("PHASE 2: Prepare dynamic AI-Scientist template")
    typer.echo("=" * 60)

    runtime_path = Path("external/ai-scientist-runtime")
    adapter = AIScientistAdapter(runtime_path)
    if not adapter.is_installed():
        typer.echo(
            "Error: AI-Scientist not found at external/ai-scientist-runtime",
            err=True,
        )
        raise typer.Exit(1)

    template_name = f"dynamic_{run_id}"
    template_dir = runtime_path / "templates" / template_name
    if template_dir.exists():
        shutil.rmtree(template_dir)
    template_dir.mkdir(parents=True, exist_ok=True)

    # Baseline file required by AI-Scientist templates.
    # For ai_toy_research_cn-compatible plotting, provide expected keys.
    run0 = template_dir / "run_0"
    run0.mkdir(parents=True, exist_ok=True)
    baseline_score = float(baseline_metrics.get("baseline_score", 0.0))
    baseline_info = {
        "toy_ai_regression": {
            "means": {
                "train_mse": baseline_score,
                "val_mse": baseline_score,
                "test_mse": baseline_score,
                "degree": 1,
                "reg_lambda": 0.0,
                "noise_std": 0.0,
            },
            "test_curve": {
                "x": [0.0, 1.0],
                "y_true": [0.0, 0.0],
                "y_pred": [0.0, 0.0],
            },
        }
    }
    (run0 / "final_info.json").write_text(
        json.dumps(baseline_info, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Use lightweight template as dynamic baseline to avoid hard dependency
    # on large local datasets (e.g. generic_ai_research_cn expects earthquake data files).
    generic_template = runtime_path / "templates" / "ai_toy_research_cn"
    for filename in ("experiment.py", "plot.py"):
        src = generic_template / filename
        dst = template_dir / filename
        if src.exists():
            shutil.copy2(src, dst)
        else:
            dst.write_text("# Auto-generated placeholder\n", encoding="utf-8")

    prompt_json = {
        "system": "You are an AI research assistant.",
        "task": spec.objective,
        "task_description": spec.objective,
        "constraints": spec.constraints.model_dump(mode="json"),
        "metrics": [m.name for m in spec.metrics],
    }
    (template_dir / "prompt.json").write_text(
        json.dumps(prompt_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    seed_ideas = []
    for i in range(num_ideas):
        seed_ideas.append(
            {
                "Name": f"idea_{i + 1}",
                "Title": f"{spec.title} - Idea {i + 1}",
                "Experiment": spec.objective,
                "Interestingness": 6,
                "Feasibility": 7,
                "Novelty": 5,
            }
        )
    (template_dir / "seed_ideas.json").write_text(
        json.dumps(seed_ideas, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    typer.echo(f"Template ready: {template_dir}")

    # ========================================================================
    # PHASE 3: Run AI-Scientist and wait for completion
    # ========================================================================
    typer.echo("\n" + "=" * 60)
    typer.echo("PHASE 3: Run AI-Scientist")
    typer.echo("=" * 60)

    job_store = JobStore(run_dir / "external" / "jobs.jsonl", max_concurrent=2)
    try:
        job_id = adapter.submit_job(
            run_id=run_id,
            spec=spec,
            model=model,
            num_ideas=num_ideas,
            writeup=writeup,
            job_store=job_store,
            template_name=template_name,
        )
    except Exception as e:
        typer.echo(f"Error submitting AI-Scientist job: {e}", err=True)
        raise typer.Exit(1)

    # Persist high-level run state
    run_json_path = run_dir / "run.json"
    if run_json_path.exists():
        run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
        run_obj = ExperimentRun(**run_data)
        run_obj.status = RunStatus.RUNNING
        run_obj.engine = "hybrid"
        run_obj.external_metadata = {
            "job_id": job_id,
            "template_name": template_name,
            "model": model,
            "num_ideas": num_ideas,
            "writeup": writeup,
        }
        run_obj.updated_at = datetime.now(timezone.utc)
        run_json_path.write_text(
            json.dumps(run_obj.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    typer.echo(f"Submitted AI-Scientist job: {job_id}")
    callbacks = JobCallbacks(adapter=adapter, job_store=job_store)
    hybrid_timeout_sec = int(
        cfg.get("external", {}).get("hybrid_timeout_sec", 4 * 3600)
    )
    poll_result = callbacks.poll_status(job_id=job_id, interval=15, timeout=hybrid_timeout_sec)

    # Parse and persist result
    job = job_store.load(job_id)
    if job is None:
        typer.echo(f"Error: Job record not found: {job_id}", err=True)
        raise typer.Exit(1)

    result_dir = runtime_path / "results" / template_name
    parser = ResultParser(result_dir=result_dir)
    experiment_result = parser.to_experiment_result(
        run_id=run_id,
        job_id=job_id,
        template_name=template_name,
        start_time=job.start_time,
        end_time=job.end_time or datetime.now(),
    )
    if experiment_result is None:
        poll_status = poll_result.get("status")
        if poll_status in {"timeout", "failed"}:
            typer.echo(
                f"Error: AI-Scientist job {poll_status}: {poll_result.get('error')}",
                err=True,
            )
            if run_json_path.exists():
                run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
                run_obj = ExperimentRun(**run_data)
                run_obj.status = RunStatus.FAILED
                run_obj.updated_at = datetime.now(timezone.utc)
                run_json_path.write_text(
                    json.dumps(
                        run_obj.model_dump(mode="json"),
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            raise typer.Exit(1)
        typer.echo("Error: No parsable AI-Scientist results found", err=True)
        raise typer.Exit(1)

    artifacts_dir = parser.copy_artifacts_to_run_dir(
        run_id=run_id,
        job_id=job_id,
        runs_dir=runs_dir,
    )
    result_file = run_dir / "external" / "ai_scientist" / f"result_{job_id}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(
        experiment_result.model_dump_json(indent=2),
        encoding="utf-8",
    )

    # Final run state
    if run_json_path.exists():
        run_data = json.loads(run_json_path.read_text(encoding="utf-8"))
        run_obj = ExperimentRun(**run_data)
        run_obj.status = RunStatus.SUCCEEDED
        run_obj.iteration_count = baseline_final.iteration_count
        run_obj.cost_usage = baseline_final.cost_usage
        run_obj.updated_at = datetime.now(timezone.utc)
        run_obj.external_metadata = {
            **(run_obj.external_metadata or {}),
            "result_file": str(result_file),
            "artifacts_dir": str(artifacts_dir),
            "ai_scientist_status": experiment_result.status,
        }
        run_json_path.write_text(
            json.dumps(run_obj.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ========================================================================
    # PHASE 4: Generate unified report and comparison
    # ========================================================================
    typer.echo("\n" + "=" * 60)
    typer.echo("PHASE 4: Generate Unified Report")
    typer.echo("=" * 60)

    from src.integrations.ai_scientist.report_synthesizer import ReportSynthesizer

    synthesizer = ReportSynthesizer(llm_client=baseline_llm)

    # Generate unified report
    unified_report = synthesizer.synthesize_hybrid_report(
        run_id=run_id,
        baseline_run=baseline_final,
        baseline_metrics=baseline_metrics,
        ai_scientist_result=experiment_result,
        runs_dir=runs_dir,
    )

    # Save unified report
    unified_report_path = run_dir / "report.json"
    unified_report_path.write_text(
        json.dumps(unified_report.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    typer.echo(f"✓ Unified report saved to {unified_report_path}")

    # Generate comparison report (markdown)
    comparison_report_path = run_dir / "comparison_report.md"
    synthesizer.generate_comparison_report(
        run_id=run_id,
        baseline_metrics=baseline_metrics,
        ai_scientist_metrics=experiment_result.metrics or {},
        output_path=comparison_report_path,
    )
    typer.echo(f"✓ Comparison report saved to {comparison_report_path}")

    typer.echo("\n" + "=" * 60)
    typer.echo("HYBRID MODE COMPLETED")
    typer.echo("=" * 60)
    typer.echo(f"Phase 1 baseline metrics: {baseline_metrics}")
    typer.echo(f"AI-Scientist status: {experiment_result.status}")
    typer.echo(f"Result file: {result_file}")
    typer.echo(f"Artifacts: {artifacts_dir}")
    typer.echo(f"Unified report: {unified_report_path}")
    typer.echo(f"Comparison report: {comparison_report_path}")


if __name__ == "__main__":
    app()
