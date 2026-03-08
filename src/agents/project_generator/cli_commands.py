"""CLI commands for project generator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml

from src.agents.project_generator.intake_agent import IntakeAgent
from src.agents.project_generator.clarification_agent import ClarificationAgent
from src.agents.project_generator.evidence_searcher import EvidenceSearcher
from src.agents.project_generator.knowledge_consolidator import KnowledgeConsolidator
from src.agents.project_generator.formalization_agent import FormalizationAgent
from src.agents.project_generator.proposal_generator import ProposalGenerator
from src.agents.project_generator.readiness_checker import ReadinessChecker
from src.llm.client import LLMClient, LLMConfig
from src.schemas.project_generator import EvidencePackage


def _load_project_config(config_path: str | None = None) -> dict:
    """Load project generator config."""
    path = Path(config_path) if config_path else Path("configs/project_generator.yaml")
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def _build_llm_client(config: dict) -> LLMClient:
    """Build LLM client from config."""
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


project_app = typer.Typer(help="Generate research projects from ideas")


@project_app.command("generate")
def project_generate(
    idea: str = typer.Argument(..., help="Research idea description"),
    interactive: bool = typer.Option(True, help="Enable interactive clarification"),
    num_proposals: int = typer.Option(3, help="Number of proposals to generate (1-3)"),
    max_papers: int = typer.Option(10, help="Maximum papers to search"),
    max_repos: int = typer.Option(5, help="Maximum code repositories to search"),
    skip_cache: bool = typer.Option(False, help="Skip knowledge cache"),
    skip_validation: bool = typer.Option(False, help="Skip readiness validation"),
    output_dir: str = typer.Option("scientist", help="Output directory for projects"),
    config_path: str | None = typer.Option(None, help="Path to config file"),
) -> None:
    """Generate research project from idea.

    Example:
        aisci project generate "Improve BERT accuracy on sentiment analysis"
        aisci project generate "Faster inference for GPT models" --num-proposals 2
    """
    try:
        typer.echo(f"🔬 Generating research project from idea: {idea}\n")

        # Load config
        config = _load_project_config(config_path)
        search_cfg = config.get("evidence_search") or config.get("search", {})
        llm_client = _build_llm_client(config)

        # Initialize agents
        intake_agent = IntakeAgent(llm_client=llm_client)
        clarification_agent = ClarificationAgent(llm_client=llm_client)
        evidence_searcher = EvidenceSearcher(
            github_token=search_cfg.get("github_token"),
            llm_client=llm_client,
        )
        knowledge_consolidator = KnowledgeConsolidator(cache_dir=Path(output_dir))
        formalization_agent = FormalizationAgent(llm_client=llm_client)
        proposal_generator = ProposalGenerator(llm_client=llm_client)

        # Step 1: Parse idea
        typer.echo("📝 Step 1: Parsing research idea...")
        idea_record = intake_agent.intake(idea)
        typer.echo(f"   Idea type: {idea_record.idea_type}")
        typer.echo(f"   Entities: {idea_record.entities}")
        typer.echo(f"   Missing info: {idea_record.missing_info}\n")

        # Step 2: Clarification (if needed and interactive)
        if interactive and idea_record.missing_info:
            typer.echo("❓ Step 2: Clarifying missing information...")
            questions = clarification_agent.generate_questions(
                idea_record,
                max_questions=config.get("clarification", {}).get("max_questions", 5),
            )

            if questions:
                typer.echo(f"   Found {len(questions)} questions to clarify:\n")
                answers = {}

                for q in questions:
                    typer.echo(f"   Q: {q.question_text}")
                    if q.options:
                        for i, opt in enumerate(q.options, 1):
                            typer.echo(f"      {i}. {opt}")
                        typer.echo(f"      Default: {q.default_answer}")

                    if q.question_type == "multiple_choice" and q.options:
                        choice = typer.prompt(
                            "   Your choice (number or text)",
                            default=q.default_answer,
                        )
                        # Map number to option
                        try:
                            idx = int(choice) - 1
                            if 0 <= idx < len(q.options):
                                answers[q.question_id] = q.options[idx]
                            else:
                                answers[q.question_id] = choice
                        except ValueError:
                            answers[q.question_id] = choice
                    else:
                        answer = typer.prompt(
                            "   Your answer", default=q.default_answer or ""
                        )
                        answers[q.question_id] = answer

                    typer.echo()

                # Update idea with answers
                idea_record = clarification_agent.update_idea(idea_record, answers)
                typer.echo(f"   Updated entities: {idea_record.entities}\n")
        else:
            typer.echo("✓ Step 2: No clarification needed\n")

        # Step 3: Evidence search
        typer.echo("🔍 Step 3: Searching for evidence...")

        # Check cache first
        evidence: Optional[EvidencePackage] = None
        if not skip_cache:
            evidence = knowledge_consolidator.check_cache(idea)
            if evidence:
                typer.echo("   ✓ Found cached evidence\n")

        # Search if no cache
        if not evidence:
            typer.echo("   Searching papers and code repositories...")
            evidence = evidence_searcher.search(
                query=idea,
                max_papers=max_papers,
                max_repos=max_repos,
            )
            typer.echo(f"   Found {len(evidence.papers)} papers")
            typer.echo(f"   Found {len(evidence.code_repos)} code repositories")
            typer.echo(f"   Identified {len(evidence.baselines)} baseline methods\n")

            # Save to cache
            knowledge_consolidator.save_cache(
                query=idea,
                results=evidence,
                ttl_days=search_cfg.get("cache_ttl_days", 30),
            )

        # Step 4: Generate evidence report
        typer.echo("📊 Step 4: Generating evidence report...")
        report = knowledge_consolidator.generate_report(evidence)
        typer.echo(f"   {report.summary}")

        # Step 5: Formalize to ResearchSpec
        typer.echo("📋 Step 5: Formalizing research specification...")
        research_spec = formalization_agent.formalize(idea_record, evidence)
        typer.echo(f"   Title: {research_spec.title}")
        typer.echo(f"   Objective: {research_spec.objective}")
        typer.echo(f"   Metrics: {[m.name for m in research_spec.metrics]}\n")

        # Step 5.5: Validate readiness (optional)
        if not skip_validation:
            typer.echo("🔍 Step 5.5: Validating research specification...")
            readiness_checker = ReadinessChecker()
            validation_report = readiness_checker.check(research_spec)

            typer.echo(f"   {validation_report.summary}")

            if validation_report.issues:
                for issue in validation_report.issues:
                    icon = "⚠️" if issue.severity == "warning" else "❌"
                    typer.echo(f"   {icon} [{issue.category}] {issue.message}")
                    typer.echo(f"      → {issue.suggestion}")

                if not validation_report.is_ready:
                    if interactive:
                        proceed = typer.confirm(
                            "\n   Continue despite validation errors?", default=False
                        )
                        if not proceed:
                            typer.echo("   Aborted by user")
                            raise typer.Exit(0)
                    else:
                        typer.echo(
                            "   ⚠️ Validation failed but continuing (use --skip-validation to suppress)"
                        )

            typer.echo()

        # Step 6: Generate proposals
        typer.echo(f"💡 Step 6: Generating {num_proposals} candidate proposals...")
        proposals = proposal_generator.generate_proposals(
            idea_record, evidence, num_proposals=num_proposals
        )

        for i, proposal in enumerate(proposals, 1):
            typer.echo(f"\n   Proposal {i}: {proposal.title}")
            typer.echo(f"   Risk profile: {proposal.risk_profile}")
            typer.echo(
                f"   Expected improvement: {proposal.expected_metrics.get('improvement', 1.0):.0%}"
            )
            typer.echo(f"   Estimated cost: ${proposal.estimated_cost:.2f}")
            typer.echo(f"   Estimated time: {proposal.estimated_time}")

        # Step 7: Save outputs
        typer.echo("\n💾 Step 7: Saving outputs...")
        output_path = Path(output_dir) / research_spec.spec_id
        output_path.mkdir(parents=True, exist_ok=True)

        # Save research spec
        spec_file = output_path / "research_spec.json"
        spec_file.write_text(research_spec.model_dump_json(indent=2))
        typer.echo(f"   ✓ Research spec: {spec_file}")

        # Save evidence report
        report_file = output_path / "evidence_report.json"
        report_file.write_text(report.model_dump_json(indent=2))
        typer.echo(f"   ✓ Evidence report: {report_file}")

        # Save proposals
        proposals_file = output_path / "proposals.json"
        proposals_data = [p.model_dump() for p in proposals]
        proposals_file.write_text(json.dumps(proposals_data, indent=2))
        typer.echo(f"   ✓ Proposals: {proposals_file}")

        typer.echo(f"\n✅ Project generated successfully: {research_spec.spec_id}")
        typer.echo(f"   Output directory: {output_path}\n")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@project_app.command("list")
def project_list(
    output_dir: str = typer.Option("scientist", help="Output directory for projects"),
) -> None:
    """List all generated projects.

    Example:
        aisci project list
    """
    try:
        output_path = Path(output_dir)
        if not output_path.exists():
            typer.echo(f"No projects found in {output_dir}")
            return

        projects = []
        for project_dir in output_path.iterdir():
            if project_dir.is_dir():
                spec_file = project_dir / "research_spec.json"
                if spec_file.exists():
                    spec_data = json.loads(spec_file.read_text())
                    projects.append(
                        {
                            "id": spec_data.get("spec_id"),
                            "title": spec_data.get("title"),
                            "status": spec_data.get("status"),
                            "created": project_dir.stat().st_ctime,
                        }
                    )

        if not projects:
            typer.echo(f"No projects found in {output_dir}")
            return

        # Sort by creation time (newest first)
        projects.sort(key=lambda x: x["created"], reverse=True)

        typer.echo(f"\n📁 Found {len(projects)} projects:\n")
        for p in projects:
            created_time = datetime.fromtimestamp(p["created"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            typer.echo(f"  • {p['id']}")
            typer.echo(f"    Title: {p['title']}")
            typer.echo(f"    Status: {p['status']}")
            typer.echo(f"    Created: {created_time}\n")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@project_app.command("show")
def project_show(
    project_id: str = typer.Argument(..., help="Project ID"),
    output_dir: str = typer.Option("scientist", help="Output directory for projects"),
) -> None:
    """Show project details.

    Example:
        aisci project show proj_abc123
    """
    try:
        project_path = Path(output_dir) / project_id
        if not project_path.exists():
            typer.echo(f"❌ Project not found: {project_id}")
            raise typer.Exit(1)

        # Load research spec
        spec_file = project_path / "research_spec.json"
        if not spec_file.exists():
            typer.echo(f"❌ Research spec not found for project: {project_id}")
            raise typer.Exit(1)

        spec_data = json.loads(spec_file.read_text())

        typer.echo(f"\n📋 Project: {spec_data['spec_id']}\n")
        typer.echo(f"Title: {spec_data['title']}")
        typer.echo(f"Status: {spec_data['status']}")
        typer.echo(f"\nObjective:\n{spec_data['objective']}\n")

        typer.echo("Metrics:")
        for metric in spec_data.get("metrics", []):
            typer.echo(
                f"  • {metric['name']}: {metric['direction']} (target: {metric.get('target', 'N/A')})"
            )

        typer.echo("\nConstraints:")
        constraints = spec_data.get("constraints", {})
        typer.echo(f"  • Max budget: ${constraints.get('max_budget_usd', 'N/A')}")
        typer.echo(f"  • Max runtime: {constraints.get('max_runtime_hours', 'N/A')}h")
        typer.echo(f"  • Max iterations: {constraints.get('max_iterations', 'N/A')}")
        typer.echo(f"  • Compute: {constraints.get('compute', 'N/A')}")

        # Load proposals if available
        proposals_file = project_path / "proposals.json"
        if proposals_file.exists():
            proposals_data = json.loads(proposals_file.read_text())
            typer.echo(f"\n💡 Proposals ({len(proposals_data)}):")
            for i, proposal in enumerate(proposals_data, 1):
                typer.echo(f"\n  {i}. {proposal['title']}")
                typer.echo(f"     Risk: {proposal['risk_profile']}")
                typer.echo(f"     Cost: ${proposal['estimated_cost']}")
                typer.echo(f"     Time: {proposal['estimated_time']}")

        # Load evidence report if available
        report_file = project_path / "evidence_report.json"
        if report_file.exists():
            report_data = json.loads(report_file.read_text())
            typer.echo("\n📊 Evidence Report:")
            typer.echo(f"  Papers: {len(report_data.get('key_papers', []))}")
            typer.echo(
                f"  Baselines: {len(report_data.get('recommended_baselines', []))}"
            )
            typer.echo(f"  Risks: {len(report_data.get('identified_risks', []))}")

        typer.echo()

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@project_app.command("delete")
def project_delete(
    project_id: str = typer.Argument(..., help="Project ID"),
    output_dir: str = typer.Option("scientist", help="Output directory for projects"),
    force: bool = typer.Option(False, help="Skip confirmation"),
) -> None:
    """Delete a project.

    Example:
        aisci project delete proj_abc123
        aisci project delete proj_abc123 --force
    """
    try:
        project_path = Path(output_dir) / project_id
        if not project_path.exists():
            typer.echo(f"❌ Project not found: {project_id}")
            raise typer.Exit(1)

        # Confirm deletion
        if not force:
            confirm = typer.confirm(
                f"Are you sure you want to delete project {project_id}?"
            )
            if not confirm:
                typer.echo("Deletion cancelled")
                return

        # Delete project directory
        import shutil

        shutil.rmtree(project_path)
        typer.echo(f"✅ Project deleted: {project_id}")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


@project_app.command("cache")
def project_cache(
    action: str = typer.Argument(..., help="Action: list, clear, or stats"),
    output_dir: str = typer.Option("scientist", help="Output directory for projects"),
) -> None:
    """Manage knowledge cache.

    Example:
        aisci project cache list
        aisci project cache stats
        aisci project cache clear
    """
    try:
        cache_dir = Path(output_dir)
        if not cache_dir.exists():
            typer.echo(f"No cache found in {output_dir}")
            return

        if action == "list":
            # List all cached queries
            cache_entries = []
            for cache_subdir in cache_dir.iterdir():
                if cache_subdir.is_dir():
                    cache_file = cache_subdir / "cache.json"
                    if cache_file.exists():
                        cache_data = json.loads(cache_file.read_text())
                        cache_entries.append(
                            {
                                "key": cache_data.get("cache_key"),
                                "query": cache_data.get("query"),
                                "timestamp": cache_data.get("timestamp"),
                                "hits": cache_data.get("hit_count", 0),
                                "expires": cache_data.get("expires_at"),
                            }
                        )

            if not cache_entries:
                typer.echo("No cache entries found")
                return

            typer.echo(f"\n📦 Found {len(cache_entries)} cache entries:\n")
            for entry in cache_entries:
                typer.echo(f"  • {entry['key']}")
                typer.echo(f"    Query: {entry['query']}")
                typer.echo(f"    Hits: {entry['hits']}")
                typer.echo(f"    Expires: {entry['expires']}\n")

        elif action == "stats":
            # Show cache statistics
            total_entries = 0
            total_hits = 0
            total_size = 0

            for cache_subdir in cache_dir.iterdir():
                if cache_subdir.is_dir():
                    cache_file = cache_subdir / "cache.json"
                    if cache_file.exists():
                        total_entries += 1
                        cache_data = json.loads(cache_file.read_text())
                        total_hits += cache_data.get("hit_count", 0)
                        total_size += cache_file.stat().st_size

            typer.echo("\n📊 Cache Statistics:\n")
            typer.echo(f"  Total entries: {total_entries}")
            typer.echo(f"  Total hits: {total_hits}")
            typer.echo(f"  Total size: {total_size / 1024:.2f} KB")
            if total_entries > 0:
                typer.echo(
                    f"  Average hits per entry: {total_hits / total_entries:.1f}"
                )
            typer.echo()

        elif action == "clear":
            # Clear all cache
            confirm = typer.confirm("Are you sure you want to clear all cache?")
            if not confirm:
                typer.echo("Cache clear cancelled")
                return

            import shutil

            cleared = 0
            for cache_subdir in cache_dir.iterdir():
                if cache_subdir.is_dir():
                    cache_file = cache_subdir / "cache.json"
                    if cache_file.exists():
                        shutil.rmtree(cache_subdir)
                        cleared += 1

            typer.echo(f"✅ Cleared {cleared} cache entries")

        else:
            typer.echo(f"❌ Unknown action: {action}")
            typer.echo("Valid actions: list, stats, clear")
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
