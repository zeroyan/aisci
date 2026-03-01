"""Tool dispatcher: routes tool calls to sandbox operations."""

from __future__ import annotations

import logging
from pathlib import Path

from src.sandbox.base import SandboxExecutor
from src.schemas.tool_use import ToolCall, ToolResult

logger = logging.getLogger(__name__)


class ToolDispatcher:
    """Routes tool calls to SubprocessSandbox operations."""

    def __init__(
        self,
        sandbox: SandboxExecutor,
        workspace: Path,
    ) -> None:
        """
        Args:
            sandbox: Sandbox executor instance
            workspace: Working directory for file operations
        """
        self.sandbox = sandbox
        self.workspace = workspace
        self.workspace.mkdir(parents=True, exist_ok=True)

    def dispatch(self, call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        try:
            if call.tool_name == "write_file":
                return self._write_file(call)
            elif call.tool_name == "run_bash":
                return self._run_bash(call)
            elif call.tool_name == "read_file":
                return self._read_file(call)
            elif call.tool_name == "finish":
                return self._finish(call)
            else:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    exit_code=1,
                    error=f"Unknown tool: {call.tool_name}",
                )
        except Exception as e:
            logger.exception(f"Tool dispatch error for {call.tool_name}")
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                exit_code=1,
                error=f"Dispatch exception: {e}",
            )

    def _write_file(self, call: ToolCall) -> ToolResult:
        """Write content to a file in the workspace."""
        try:
            path_str = call.arguments.get("path")
            content = call.arguments.get("content")

            if not path_str or content is None:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="write_file",
                    exit_code=1,
                    error="Missing 'path' or 'content' argument",
                )

            file_path = self.workspace / path_str
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            return ToolResult(
                call_id=call.call_id,
                tool_name="write_file",
                stdout=f"Wrote {len(content)} bytes to {path_str}",
                exit_code=0,
            )
        except Exception as e:
            return ToolResult(
                call_id=call.call_id,
                tool_name="write_file",
                exit_code=1,
                error=str(e),
            )

    def _run_bash(self, call: ToolCall) -> ToolResult:
        """Execute a bash command in the workspace."""
        import subprocess

        try:
            cmd = call.arguments.get("cmd")
            if not cmd:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="run_bash",
                    exit_code=1,
                    error="Missing 'cmd' argument",
                )

            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
            )

            return ToolResult(
                call_id=call.call_id,
                tool_name="run_bash",
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                call_id=call.call_id,
                tool_name="run_bash",
                exit_code=124,
                error="Command timeout (300s)",
            )
        except Exception as e:
            return ToolResult(
                call_id=call.call_id,
                tool_name="run_bash",
                exit_code=1,
                error=str(e),
            )

    def _read_file(self, call: ToolCall) -> ToolResult:
        """Read a file from the workspace."""
        try:
            path_str = call.arguments.get("path")
            if not path_str:
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="read_file",
                    exit_code=1,
                    error="Missing 'path' argument",
                )

            file_path = self.workspace / path_str
            if not file_path.exists():
                return ToolResult(
                    call_id=call.call_id,
                    tool_name="read_file",
                    exit_code=1,
                    error=f"File not found: {path_str}",
                )

            content = file_path.read_text(encoding="utf-8")
            return ToolResult(
                call_id=call.call_id,
                tool_name="read_file",
                stdout=content,
                exit_code=0,
            )
        except Exception as e:
            return ToolResult(
                call_id=call.call_id,
                tool_name="read_file",
                exit_code=1,
                error=str(e),
            )

    def _finish(self, call: ToolCall) -> ToolResult:
        """Handle finish tool call (signals completion)."""
        # Finish is handled by ToolAgent, just return success
        return ToolResult(
            call_id=call.call_id,
            tool_name="finish",
            stdout="Finish signal received",
            exit_code=0,
        )
