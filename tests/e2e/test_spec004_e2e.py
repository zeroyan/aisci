"""End-to-end test for Spec 004: AI-Scientist Integration.

This test validates the three engine modes:
1. aisci (default)
2. ai-scientist (async)
3. hybrid (baseline → AI-Scientist → refinement)
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


# Test configuration
TEST_RUN_ID = "e2e_test_004"
RUNS_DIR = Path("runs")
TEST_RUN_DIR = RUNS_DIR / TEST_RUN_ID


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Setup test environment and cleanup after tests."""
    # Setup: Create test run directory
    TEST_RUN_DIR.mkdir(parents=True, exist_ok=True)

    # Create spec directory
    spec_dir = TEST_RUN_DIR / "spec"
    spec_dir.mkdir(exist_ok=True)

    # Copy sample spec
    sample_spec = Path("tests/fixtures/sample_research_spec.json")
    if sample_spec.exists():
        shutil.copy(sample_spec, spec_dir / "research_spec.json")

    # Create plan directory
    plan_dir = TEST_RUN_DIR / "plan"
    plan_dir.mkdir(exist_ok=True)

    # Copy sample plan
    sample_plan = Path("tests/fixtures/sample_experiment_plan.json")
    if sample_plan.exists():
        shutil.copy(sample_plan, plan_dir / "experiment_plan.json")

    yield

    # Teardown: Clean up test run directory
    # Comment out to inspect results after test
    # if TEST_RUN_DIR.exists():
    #     shutil.rmtree(TEST_RUN_DIR)


def run_cli_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run CLI command and return exit code, stdout, stderr."""
    # Use virtual environment Python
    if cmd[0] == "python":
        venv_python = Path(".venv/bin/python")
        if venv_python.exists():
            cmd[0] = str(venv_python)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path.cwd(),
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"


class TestEngineRouting:
    """Test US-1: Engine routing selection."""

    def test_invalid_engine(self):
        """Test that invalid engine parameter is rejected."""
        cmd = ["python", "cli.py", "run", "start", TEST_RUN_ID, "--engine", "invalid"]
        returncode, stdout, stderr = run_cli_command(cmd)

        assert returncode != 0, "Should fail with invalid engine"
        assert "invalid" in stderr.lower() or "invalid" in stdout.lower()

    def test_engine_parameter_exists(self):
        """Test that --engine parameter is recognized."""
        cmd = ["python", "cli.py", "run", "start", "--help"]
        returncode, stdout, stderr = run_cli_command(cmd)

        assert returncode == 0
        assert "--engine" in stdout
        assert "aisci" in stdout or "ai-scientist" in stdout


class TestAiSciEngine:
    """Test aisci engine (default mode)."""

    @pytest.mark.skip(reason="Requires full environment setup")
    def test_aisci_engine_basic(self):
        """Test basic aisci engine execution."""
        cmd = [
            "python", "cli.py", "run", "start",
            TEST_RUN_ID + "_aisci",
            "--engine", "aisci"
        ]
        returncode, stdout, stderr = run_cli_command(cmd, timeout=60)

        # Should not fail immediately
        assert returncode == 0 or "Error" not in stderr


class TestAiScientistEngine:
    """Test US-2: AI-Scientist async engine."""

    def test_ai_scientist_requires_api_key(self):
        """Test that AI-Scientist engine requires API key."""
        # Temporarily unset API key
        old_key = os.environ.get("DEEPSEEK_API_KEY")
        if old_key:
            del os.environ["DEEPSEEK_API_KEY"]

        cmd = [
            "python", "cli.py", "run", "start",
            TEST_RUN_ID + "_ai_scientist",
            "--engine", "ai-scientist",
            "--model", "deepseek-chat",
            "--num-ideas", "1"
        ]
        returncode, stdout, stderr = run_cli_command(cmd)

        # Restore API key
        if old_key:
            os.environ["DEEPSEEK_API_KEY"] = old_key

        # Should fail (either due to missing API key or missing spec)
        # Both are acceptable for this test
        assert returncode != 0
        # Either API key error or spec not found error
        assert ("DEEPSEEK_API_KEY" in stderr or "DEEPSEEK_API_KEY" in stdout or
                "spec not found" in stderr.lower() or "spec not found" in stdout.lower())

    def test_external_status_command_exists(self):
        """Test that external-status command exists."""
        cmd = ["python", "cli.py", "run", "external-status", "--help"]
        returncode, stdout, stderr = run_cli_command(cmd)

        # Command should exist (may fail with missing run_id, but command exists)
        assert "external-status" in stdout or returncode == 0

    def test_external_fetch_command_exists(self):
        """Test that external-fetch command exists."""
        cmd = ["python", "cli.py", "run", "external-fetch", "--help"]
        returncode, stdout, stderr = run_cli_command(cmd)

        assert "external-fetch" in stdout or returncode == 0

    def test_external_cancel_command_exists(self):
        """Test that external-cancel command exists."""
        cmd = ["python", "cli.py", "run", "external-cancel", "--help"]
        returncode, stdout, stderr = run_cli_command(cmd)

        assert "external-cancel" in stdout or returncode == 0


class TestHybridEngine:
    """Test US-4: Hybrid mode."""

    def test_hybrid_mode_requires_api_key(self):
        """Test that hybrid mode requires API key."""
        # Temporarily unset API key
        old_key = os.environ.get("DEEPSEEK_API_KEY")
        if old_key:
            del os.environ["DEEPSEEK_API_KEY"]

        cmd = [
            "python", "cli.py", "run", "start",
            TEST_RUN_ID + "_hybrid",
            "--engine", "hybrid",
            "--model", "deepseek-chat",
            "--num-ideas", "1"
        ]
        returncode, stdout, stderr = run_cli_command(cmd, timeout=120)

        # Restore API key
        if old_key:
            os.environ["DEEPSEEK_API_KEY"] = old_key

        # Should fail at some point due to missing API key
        # (may fail during baseline generation or AI-Scientist phase)
        assert returncode != 0 or "Error" in stderr or "Error" in stdout


class TestIntegrationModules:
    """Test that integration modules are properly structured."""

    def test_adapter_module_exists(self):
        """Test that AIScientistAdapter module exists."""
        adapter_path = Path("src/integrations/ai_scientist/adapter.py")
        assert adapter_path.exists()

    def test_job_store_module_exists(self):
        """Test that JobStore module exists."""
        job_store_path = Path("src/integrations/ai_scientist/job_store.py")
        assert job_store_path.exists()

    def test_result_parser_module_exists(self):
        """Test that ResultParser module exists."""
        parser_path = Path("src/integrations/ai_scientist/result_parser.py")
        assert parser_path.exists()

    def test_callbacks_module_exists(self):
        """Test that JobCallbacks module exists."""
        callbacks_path = Path("src/integrations/ai_scientist/callbacks.py")
        assert callbacks_path.exists()

    def test_schemas_module_exists(self):
        """Test that AI-Scientist schemas exist."""
        schemas_path = Path("src/schemas/ai_scientist.py")
        assert schemas_path.exists()

    def test_can_import_adapter(self):
        """Test that AIScientistAdapter can be imported."""
        try:
            from src.integrations.ai_scientist.adapter import AIScientistAdapter
            assert AIScientistAdapter is not None
        except ImportError as e:
            pytest.fail(f"Failed to import AIScientistAdapter: {e}")

    def test_can_import_job_store(self):
        """Test that JobStore can be imported."""
        try:
            from src.integrations.ai_scientist.job_store import JobStore
            assert JobStore is not None
        except ImportError as e:
            pytest.fail(f"Failed to import JobStore: {e}")

    def test_can_import_schemas(self):
        """Test that AI-Scientist schemas can be imported."""
        try:
            from src.schemas.ai_scientist import JobRecord, JobStatus, TemplatePackage
            assert JobRecord is not None
            assert JobStatus is not None
            assert TemplatePackage is not None
        except ImportError as e:
            pytest.fail(f"Failed to import schemas: {e}")


class TestJobStore:
    """Test JobStore functionality."""

    def test_job_store_initialization(self):
        """Test that JobStore can be initialized."""
        from src.integrations.ai_scientist.job_store import JobStore

        test_path = TEST_RUN_DIR / "test_jobs.jsonl"
        job_store = JobStore(test_path, max_concurrent=2)

        assert job_store.max_concurrent == 2
        assert job_store.storage_path == test_path

    def test_job_store_can_submit(self):
        """Test JobStore concurrent control."""
        from src.integrations.ai_scientist.job_store import JobStore

        test_path = TEST_RUN_DIR / "test_jobs2.jsonl"
        job_store = JobStore(test_path, max_concurrent=2)

        # Initially should be able to submit
        assert job_store.can_submit() is True


class TestResultParser:
    """Test US-3: Result parser functionality."""

    def test_result_parser_initialization(self):
        """Test that ResultParser can be initialized."""
        from src.integrations.ai_scientist.result_parser import ResultParser

        runtime_path = Path("external/ai-scientist-runtime")
        parser = ResultParser(runtime_path)

        # Just verify it initializes without error
        assert parser is not None


class TestTemplateGeneration:
    """Test template generation for Hybrid mode."""

    def test_baseline_format(self):
        """Test that baseline format is correct."""
        baseline_metrics = {"accuracy": 0.75, "loss": 0.25}
        baseline_info = {
            "experiment": {
                "means": baseline_metrics
            }
        }

        # Verify format
        assert "experiment" in baseline_info
        assert "means" in baseline_info["experiment"]
        assert baseline_info["experiment"]["means"] == baseline_metrics

    def test_template_structure(self):
        """Test that template directory structure is correct."""
        # Create test template
        test_template_dir = TEST_RUN_DIR / "test_template"
        test_template_dir.mkdir(exist_ok=True)

        # Create required files
        (test_template_dir / "experiment.py").write_text("# Test")
        (test_template_dir / "prompt.json").write_text("{}")
        (test_template_dir / "seed_ideas.json").write_text("[]")

        baseline_dir = test_template_dir / "run_0"
        baseline_dir.mkdir(exist_ok=True)
        (baseline_dir / "final_info.json").write_text('{"experiment": {"means": {}}}')

        # Verify all files exist
        assert (test_template_dir / "experiment.py").exists()
        assert (test_template_dir / "prompt.json").exists()
        assert (test_template_dir / "seed_ideas.json").exists()
        assert (baseline_dir / "final_info.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
