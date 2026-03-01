"""Unit tests for SubprocessSandbox."""

from __future__ import annotations

import json

import pytest

from src.sandbox.subprocess_sandbox import SubprocessSandbox
from src.schemas.sandbox_io import CodeSnapshot, SandboxRequest, SandboxStatus


def make_request(
    files: dict[str, str],
    entrypoint: str = "python main.py",
    timeout_sec: int = 30,
) -> SandboxRequest:
    return SandboxRequest(
        request_id="test_req",
        run_id="test_run",
        iteration_index=1,
        code_snapshot=CodeSnapshot(files=files, entrypoint=entrypoint),
        timeout_sec=timeout_sec,
    )


class TestSubprocessSandbox:
    """Tests for SubprocessSandbox.execute()."""

    def test_execute_success(self, tmp_path: pytest.TempPathFactory) -> None:
        sandbox = SubprocessSandbox(runs_dir=tmp_path)
        request = make_request(
            files={
                "main.py": (
                    "import json; "
                    "json.dump({'accuracy': 0.95}, open('metrics.json', 'w'))"
                ),
            },
            entrypoint="python main.py",
        )

        response = sandbox.execute(request)

        assert response.status == SandboxStatus.succeeded
        assert response.exit_code == 0
        assert "metrics.json" in response.output_files
        metrics = json.loads(response.output_files["metrics.json"])
        assert metrics["accuracy"] == pytest.approx(0.95)

    def test_execute_failure(self, tmp_path: pytest.TempPathFactory) -> None:
        sandbox = SubprocessSandbox(runs_dir=tmp_path)
        request = make_request(
            files={"main.py": "raise ValueError('boom')"},
        )

        response = sandbox.execute(request)

        assert response.status == SandboxStatus.failed
        assert response.exit_code != 0
        assert "ValueError" in response.stderr

    def test_execute_timeout(self, tmp_path: pytest.TempPathFactory) -> None:
        sandbox = SubprocessSandbox(runs_dir=tmp_path)
        request = make_request(
            files={"main.py": "import time; time.sleep(60)"},
            timeout_sec=1,
        )

        response = sandbox.execute(request)

        assert response.status == SandboxStatus.timeout

    def test_stdout_captured(self, tmp_path: pytest.TempPathFactory) -> None:
        sandbox = SubprocessSandbox(runs_dir=tmp_path)
        request = make_request(
            files={"main.py": "print('hello world')"},
        )

        response = sandbox.execute(request)

        assert "hello world" in response.stdout

    def test_workspace_created(self, tmp_path: pytest.TempPathFactory) -> None:
        sandbox = SubprocessSandbox(runs_dir=tmp_path)
        request = make_request(
            files={"main.py": "print('ok')"},
        )

        sandbox.execute(request)

        workspace_file = (
            tmp_path
            / request.run_id
            / "iterations"
            / "it_0001"
            / "workspace"
            / "main.py"
        )
        assert workspace_file.exists()

    def test_metrics_json_parsing(self, tmp_path: pytest.TempPathFactory) -> None:
        sandbox = SubprocessSandbox(runs_dir=tmp_path)
        request = make_request(
            files={
                "main.py": (
                    "import json; "
                    "json.dump("
                    "{'accuracy': 0.95, 'loss': 0.05, 'f1': 0.92}, "
                    "open('metrics.json', 'w'))"
                ),
            },
        )

        response = sandbox.execute(request)

        assert "metrics.json" in response.output_files
        metrics = json.loads(response.output_files["metrics.json"])
        assert metrics["accuracy"] == pytest.approx(0.95)
        assert metrics["loss"] == pytest.approx(0.05)
        assert metrics["f1"] == pytest.approx(0.92)
