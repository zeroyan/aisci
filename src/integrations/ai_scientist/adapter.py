"""AI-Scientist adapter for external execution."""

import json
import os
import re
import socket
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from src.schemas.ai_scientist import JobRecord, JobStatus
from src.schemas.research_spec import ResearchSpec


class AIScientistAdapter:
    """Adapter for AI-Scientist external execution engine."""

    def __init__(self, runtime_path: Path):
        """Initialize adapter.

        Args:
            runtime_path: Path to ai-scientist-runtime directory
        """
        self.runtime_path = runtime_path
        self.launch_script = runtime_path / "launch_scientist.py"

    def is_installed(self) -> bool:
        """Check if AI-Scientist is installed."""
        return self.runtime_path.exists() and self.launch_script.exists()

    def check_version(self) -> Optional[str]:
        """Check AI-Scientist version.

        Returns:
            Version string or None if not installed
        """
        if not self.is_installed():
            return None

        try:
            result = subprocess.run(
                ["python", str(self.launch_script), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def check_ollama_service(self, host: str = "localhost", port: int = 11434) -> bool:
        """Check if Ollama service is running.

        Args:
            host: Ollama host (default: localhost)
            port: Ollama port (default: 11434)

        Returns:
            True if Ollama is accessible
        """
        try:
            import requests
            response = requests.get(f"http://{host}:{port}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def check_ollama_model(self, model_name: str = "qwen3") -> bool:
        """Check if specific Ollama model is available.

        Args:
            model_name: Model name to check (default: qwen3)

        Returns:
            True if model is available
        """
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return model_name in result.stdout
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_installation_guide(self) -> str:
        """Get installation guide for AI-Scientist.

        Returns:
            Markdown formatted installation guide
        """
        guide = """# AI-Scientist Installation Guide

## Prerequisites

1. **Python 3.11+** with venv support
2. **Git** for submodule management
3. **Ollama** (optional, for local models)

## Installation Steps

### 1. Initialize AI-Scientist Submodule

```bash
git submodule update --init external/ai-scientist-runtime
cd external/ai-scientist-runtime
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ollama (Optional)

For local model support:

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve
```

### 5. Pull qwen3 Model (Optional)

```bash
ollama pull qwen3
```

## Verification

Test the installation:

```bash
python launch_scientist.py --version
```

## Configuration

Set API keys in environment:

```bash
export DEEPSEEK_API_KEY="your_api_key_here"
```

Or use Ollama for local execution:

```bash
python cli.py run start <run_id> --engine ai-scientist --model ollama/qwen3
```

## Troubleshooting

### AI-Scientist Not Found
- Verify submodule is initialized: `git submodule status`
- Check path: `external/ai-scientist-runtime/launch_scientist.py`

### Ollama Connection Failed
- Check service: `curl http://localhost:11434/api/tags`
- Restart service: `ollama serve`

### Model Not Available
- List models: `ollama list`
- Pull model: `ollama pull qwen3`

### Missing Dependencies
- Reinstall: `pip install -r requirements.txt`
- Check Python version: `python --version` (need 3.11+)
"""
        return guide

    def validate_environment(self, model: str = "deepseek-chat") -> dict:
        """Validate complete environment setup.

        Args:
            model: Model to validate (e.g., "deepseek-chat", "ollama/qwen3")

        Returns:
            Dict with validation results and error messages
        """
        results = {
            "ai_scientist_installed": False,
            "version": None,
            "ollama_service": False,
            "ollama_model": None,
            "api_key": False,
            "errors": [],
            "warnings": [],
        }

        # Check AI-Scientist installation
        if not self.is_installed():
            results["errors"].append(
                "AI-Scientist not installed. Run: git submodule update --init external/ai-scientist-runtime"
            )
        else:
            results["ai_scientist_installed"] = True
            results["version"] = self.check_version()

        # Check model-specific requirements
        if model.startswith("ollama/"):
            model_name = model.split("/")[1]

            # Check Ollama service
            if not self.check_ollama_service():
                results["errors"].append(
                    "Ollama service not running. Start with: ollama serve"
                )
            else:
                results["ollama_service"] = True

            # Check Ollama model
            if not self.check_ollama_model(model_name):
                results["warnings"].append(
                    f"Model '{model_name}' not found. Pull with: ollama pull {model_name}"
                )
            else:
                results["ollama_model"] = model_name

        else:
            # Check API key for cloud models
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                results["errors"].append(
                    "DEEPSEEK_API_KEY not set. Export with: export DEEPSEEK_API_KEY='your_key'"
                )
            else:
                results["api_key"] = True

        return results

    def submit_job(
        self,
        run_id: str,
        spec: ResearchSpec,
        model: str,
        num_ideas: int,
        writeup: str,
        job_store,
        template_name: str | None = None,
    ) -> str:
        """Submit AI-Scientist job asynchronously.

        Args:
            run_id: Experiment run ID
            spec: Research specification
            model: Model to use (e.g., "deepseek-chat")
            num_ideas: Number of ideas to generate
            writeup: Writeup format ("latex" or "md")
            job_store: JobStore instance for task management
            template_name: Optional template name (default: "generic_ai_research_cn")

        Returns:
            Job ID (UUID)
        """
        # Generate job ID
        job_id = str(uuid.uuid4())

        # Create log directory
        log_dir = Path("runs") / run_id / "external" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}.log"

        # Prepare command - use AI-Scientist's venv python
        venv_python = self.runtime_path.absolute() / ".venv" / "bin" / "python"
        if not venv_python.exists():
            # Try backup venv
            venv_python = self.runtime_path.absolute() / ".venv_py313_backup" / "bin" / "python"

        python_cmd = str(venv_python) if venv_python.exists() else "python"

        # Validate runtime environment before launching long-running process.
        self._validate_runtime_environment(python_cmd)

        # Use provided template name or default
        experiment_template = template_name or "generic_ai_research_cn"

        cmd = [
            python_cmd,
            "launch_scientist.py",
            "--experiment", experiment_template,
            "--model", model,
            "--writeup", writeup,
            "--num-ideas", str(num_ideas),
            "--skip-novelty-check",
        ]

        # Set environment variables for API key
        # Read from environment or config, never hardcode
        api_key = subprocess.os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY environment variable not set. "
                "Please set it before running AI-Scientist jobs."
            )
        env = self._build_runtime_env(python_cmd)
        env["DEEPSEEK_API_KEY"] = api_key
        env = self._sanitize_proxy_env(env)

        # Check if we can submit (concurrent control)
        can_start = job_store.can_submit()

        # Create run workspace for observability.
        self._ensure_job_workspace(run_id, job_id)

        # Create job record first
        job = JobRecord(
            job_id=job_id,
            run_id=run_id,
            pid=None,  # Will be set if started
            status=JobStatus.PENDING if not can_start else JobStatus.RUNNING,
            log_path=str(log_path),
            start_time=datetime.now(),
            end_time=None,
            error=None,
            template_name=experiment_template,
            num_ideas=num_ideas,
            model=model,
            writeup=writeup,
        )

        # Only start process if we can submit
        if can_start:
            # Start subprocess with correct working directory
            with open(log_path, "w") as log_file:
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.runtime_path.absolute()),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                )
            job.pid = process.pid
            job_store.save(job)
            print(f"Job {job_id} started (PID: {process.pid})")
        else:
            # Queue the job
            job_store.save(job)
            print(f"Job {job_id} queued (concurrent limit reached)")

        return job_id

    def get_status(self, job: JobRecord, job_store) -> dict:
        """Get job status and progress.

        Args:
            job: Job record
            job_store: JobStore instance

        Returns:
            Status dict with keys: status, progress, elapsed_time, log_path, error
        """
        import psutil
        from datetime import datetime

        # Check if process is still running (skip if job is pending)
        if job.pid is not None:
            try:
                process = psutil.Process(job.pid)
                is_running = process.is_running()
            except psutil.NoSuchProcess:
                is_running = False
        else:
            is_running = False

        # Do not fail-fast while process is still running.
        # AI-Scientist logs often contain transient/retried errors; final status
        # should be decided when process exits.

        # Update job status if process ended
        if not is_running and job.status == JobStatus.RUNNING:
            # Check if results exist in AI-Scientist output directory.
            result_dir = self.runtime_path / "results" / job.template_name
            log_error = self._extract_log_error(job)
            has_new_results = self._has_new_results_since_start(job, result_dir)
            if has_new_results and log_error is None:
                job.status = JobStatus.COMPLETED
                job.end_time = datetime.now()
            else:
                job.status = JobStatus.FAILED
                job.end_time = datetime.now()
                job.error = log_error or "Process ended without producing new results"

            job_store.save(job)

            # Try to start a pending job
            self._try_start_pending_job(job_store)

        # Calculate progress (estimate based on log file)
        progress = self._estimate_progress(job)
        workspace_dir = self._sync_job_workspace(job, progress)

        # Calculate elapsed time
        elapsed = datetime.now() - job.start_time
        elapsed_str = f"{int(elapsed.total_seconds())}s"

        return {
            "status": job.status.value,
            "progress": progress,
            "elapsed_time": elapsed_str,
            "log_path": job.log_path,
            "workspace_path": str(workspace_dir),
            "error": job.error,
        }

    def _estimate_progress(self, job: JobRecord) -> str:
        """Estimate progress from log file.

        Args:
            job: Job record

        Returns:
            Progress string (e.g., "1/2 ideas")
        """
        from pathlib import Path

        log_path = Path(job.log_path)
        if not log_path.exists():
            return "0/? ideas"

        try:
            log_content = log_path.read_text(encoding="utf-8", errors="ignore")
            completed = self._count_completed_ideas(log_content)
            return f"{completed}/{job.num_ideas} ideas"
        except Exception:
            return "?/? ideas"

    def _count_completed_ideas(self, log_content: str) -> int:
        """Count completed ideas from common AI-Scientist log patterns."""
        patterns = [
            r"Checking novelty of idea\s+(\d+)",
            r"Processing idea:\s+([A-Za-z0-9_\-]+)",
            r"Idea generation converged after\s+(\d+)\s+iterations",
        ]
        hits = set()
        for pattern in patterns:
            for match in re.findall(pattern, log_content):
                hits.add(str(match))
        return len(hits)

    def _extract_log_error(self, job: JobRecord) -> str | None:
        """Extract fatal error from log if present."""
        log_path = Path(job.log_path)
        if not log_path.exists():
            return None
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        # Common launch_scientist argument/parser failures.
        if "error: unrecognized arguments:" in content:
            m = re.search(r"error: unrecognized arguments:(.*)", content)
            return m.group(0).strip() if m else "Invalid launch_scientist arguments"
        # Surface actionable DeepSeek networking errors with highest priority.
        if "DeepseekException" in content and "Connection refused" in content:
            return "DeepSeek API connection refused (check proxy/network/API endpoint)"

        if "Run failed with the following error" in content:
            # Keep the most actionable traceback tail, if present.
            tail = content.strip().splitlines()[-20:]
            for line in reversed(tail):
                stripped = line.strip()
                if stripped.startswith("ModuleNotFoundError:"):
                    return stripped
                if stripped.startswith("ImportError:"):
                    return stripped
                if stripped.startswith("FileNotFoundError:"):
                    return stripped
            return "AI-Scientist run failed (see log for details)"
        if "Traceback (most recent call last):" in content:
            return "AI-Scientist process crashed (see log traceback)"
        return None

    def _has_new_results_since_start(self, job: JobRecord, result_dir: Path) -> bool:
        """Return True if result_dir has files newer than this job's start time."""
        if not result_dir.exists():
            return False
        start_ts = job.start_time.timestamp()
        for p in result_dir.rglob("*"):
            if p.is_file() and p.stat().st_mtime >= start_ts:
                return True
        return False

    def _validate_runtime_environment(self, python_cmd: str) -> None:
        """Check required AI-Scientist runtime dependencies before launch."""
        checks = (
            ("numpy", "numpy"),
            ("matplotlib", "matplotlib"),
            ("sklearn", "scikit-learn"),
        )
        missing = []
        for module_name, pip_name in checks:
            result = subprocess.run(
                [python_cmd, "-c", f"import {module_name}"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                missing.append(pip_name)

        if missing:
            deps = " ".join(sorted(set(missing)))
            raise ValueError(
                "AI-Scientist runtime missing dependencies: "
                f"{deps}. Install with: {python_cmd} -m pip install {deps}"
            )

    def _build_runtime_env(self, python_cmd: str) -> dict[str, str]:
        """Build env so nested 'python ...' calls use runtime venv."""
        env = dict(os.environ)
        python_path = Path(python_cmd)
        if python_path.exists():
            venv_bin = python_path.parent
            venv_root = venv_bin.parent
            current_path = env.get("PATH", "")
            env["PATH"] = (
                f"{venv_bin}{os.pathsep}{current_path}" if current_path else str(venv_bin)
            )
            env["VIRTUAL_ENV"] = str(venv_root)
            env.setdefault("PYTHONNOUSERSITE", "1")
        return env

    def _sanitize_proxy_env(self, env: dict[str, str]) -> dict[str, str]:
        """Remove broken localhost proxies to avoid DeepSeek connection refusal."""
        proxy_keys = [
            "http_proxy", "https_proxy", "all_proxy",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        ]
        configured = [env.get(k) for k in proxy_keys if env.get(k)]
        if not configured:
            return env

        localhost_targets: list[tuple[str, int]] = []
        for value in configured:
            try:
                parsed = urlparse(value)
                host = parsed.hostname
                port = parsed.port
                if host in {"127.0.0.1", "localhost"} and port:
                    localhost_targets.append((host, port))
            except Exception:
                continue

        if not localhost_targets:
            return env

        for host, port in localhost_targets:
            if not self._is_tcp_reachable(host, port):
                for key in proxy_keys:
                    env.pop(key, None)
                return env
        return env

    def _is_tcp_reachable(self, host: str, port: int, timeout: float = 0.3) -> bool:
        """Best-effort TCP reachability check."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def cancel_job(self, job: JobRecord, job_store, force: bool = False) -> None:
        """Cancel a running job.

        Args:
            job: Job record
            job_store: JobStore instance
            force: If True, use SIGKILL instead of SIGTERM
        """
        import psutil
        import signal
        from datetime import datetime

        try:
            process = psutil.Process(job.pid)

            if force:
                # Force kill
                process.kill()
            else:
                # Graceful termination
                process.terminate()

                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    # Force kill if graceful shutdown failed
                    process.kill()

            # Update job status
            job.status = JobStatus.FAILED
            job.end_time = datetime.now()
            job.error = "Cancelled by user"
            job_store.save(job)

        except psutil.NoSuchProcess:
            # Process already ended
            job.status = JobStatus.FAILED
            job.end_time = datetime.now()
            job.error = "Process not found (may have already ended)"
            job_store.save(job)
        except psutil.AccessDenied:
            # No permission to signal process in current environment.
            # Preserve running state and let periodic status checks decide later.
            return

    def _try_start_pending_job(self, job_store) -> None:
        """Try to start a pending job if capacity available."""
        if not job_store.can_submit():
            return

        # Find oldest pending job
        pending_jobs = [j for j in job_store.list_all() if j.status == JobStatus.PENDING]
        if not pending_jobs:
            return

        job = min(pending_jobs, key=lambda j: j.start_time)

        # Prepare command using job's original parameters
        venv_python = self.runtime_path.absolute() / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = self.runtime_path.absolute() / ".venv_py313_backup" / "bin" / "python"
        python_cmd = str(venv_python) if venv_python.exists() else "python"

        cmd = [
            python_cmd,
            "launch_scientist.py",
            "--experiment", job.template_name,
            "--model", job.model,
            "--writeup", job.writeup,
            "--num-ideas", str(job.num_ideas),
            "--skip-novelty-check",
        ]

        # Get API key
        api_key = subprocess.os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            job.status = JobStatus.FAILED
            job.error = "DEEPSEEK_API_KEY not set"
            job_store.save(job)
            return

        env = self._build_runtime_env(python_cmd)
        env["DEEPSEEK_API_KEY"] = api_key
        env = self._sanitize_proxy_env(env)

        # Start process
        log_path = Path(job.log_path)
        try:
            with open(log_path, "a") as log_file:
                log_file.write(f"\n\n=== Job started from queue at {datetime.now()} ===\n\n")
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.runtime_path.absolute()),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                )
            job.pid = process.pid
            job.status = JobStatus.RUNNING
            job_store.save(job)
            print(f"Started queued job {job.job_id} (PID: {process.pid})")
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = f"Failed to start: {e}"
            job_store.save(job)

    def _ensure_job_workspace(self, run_id: str, job_id: str) -> Path:
        """Create per-job workspace under run directory."""
        workspace_dir = Path("runs") / run_id / "external" / "workspace" / job_id
        workspace_dir.mkdir(parents=True, exist_ok=True)
        return workspace_dir

    def _sync_job_workspace(self, job: JobRecord, progress: str) -> Path:
        """Mirror key AI-Scientist artifacts into run workspace for visibility."""
        workspace_dir = self._ensure_job_workspace(job.run_id, job.job_id)

        # 1) Keep log mirrored inside workspace.
        log_src = Path(job.log_path)
        if log_src.exists():
            log_dst = workspace_dir / "job.log"
            try:
                if (not log_dst.exists()) or (log_src.stat().st_mtime > log_dst.stat().st_mtime):
                    shutil.copy2(log_src, log_dst)
            except OSError:
                pass

        # 2) Mirror template inputs and intermediate files.
        template_src = self.runtime_path / "templates" / job.template_name
        template_dst = workspace_dir / "template"
        self._sync_tree_incremental(template_src, template_dst)

        # 3) Mirror generated results.
        results_src = self.runtime_path / "results" / job.template_name
        results_dst = workspace_dir / "results"
        self._sync_tree_incremental(results_src, results_dst)

        # 4) Persist a small status snapshot for dashboarding/debugging.
        snapshot = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "status": job.status.value,
            "progress": progress,
            "template_name": job.template_name,
            "model": job.model,
            "num_ideas": job.num_ideas,
            "writeup": job.writeup,
            "updated_at": datetime.now().isoformat(),
        }
        try:
            (workspace_dir / "status_snapshot.json").write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

        return workspace_dir

    def _sync_tree_incremental(self, src: Path, dst: Path) -> None:
        """Copy changed files from src tree to dst tree."""
        if not src.exists():
            return
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(src)
            target = dst / rel
            try:
                src_mtime = path.stat().st_mtime
                dst_mtime = target.stat().st_mtime if target.exists() else -1
                if src_mtime > dst_mtime:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
            except OSError:
                continue
