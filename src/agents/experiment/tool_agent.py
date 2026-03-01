"""Tool-use agent: LLM with tools for autonomous experiment execution."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from litellm import completion

from src.agents.experiment.tool_dispatcher import ToolDispatcher
from src.llm.client import LLMClient
from src.sandbox.base import SandboxExecutor
from src.schemas.tool_use import (
    FinishResult,
    ToolCall,
    ToolIterationRecord,
    ToolTurn,
)

logger = logging.getLogger(__name__)

# Tool definitions for litellm (OpenAI function calling format)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root",
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Execute a bash command in the workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "Bash command to execute",
                    },
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to workspace root",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Signal experiment completion with summary and artifacts",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Experiment conclusion summary",
                    },
                    "artifacts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of output file paths",
                    },
                    "success": {
                        "type": "boolean",
                        "description": "Whether experiment succeeded",
                    },
                    "failure_reason": {
                        "type": "string",
                        "description": "Reason for failure if success=false",
                    },
                },
                "required": ["summary", "success"],
            },
        },
    },
]


class ToolAgent:
    """LLM agent with tools for autonomous experiment execution."""

    def __init__(
        self,
        llm_client: LLMClient,
        sandbox: SandboxExecutor,
        system_prompt: str,
        max_turns: int = 20,
    ) -> None:
        """
        Args:
            llm_client: LLM client instance
            sandbox: Sandbox executor (for ToolDispatcher)
            system_prompt: System prompt for the agent
            max_turns: Maximum tool-use turns before timeout
        """
        self.llm_client = llm_client
        self.sandbox = sandbox
        self.system_prompt = system_prompt
        self.max_turns = max_turns

    def run_iteration(
        self,
        run_id: str,
        iteration_index: int,
        workspace: Path,
        initial_prompt: str,
    ) -> ToolIterationRecord:
        """Execute one tool-use iteration until finish or max_turns."""
        started_at = datetime.now(timezone.utc)
        record = ToolIterationRecord(
            run_id=run_id,
            iteration_index=iteration_index,
            started_at=started_at,
        )

        dispatcher = ToolDispatcher(self.sandbox, workspace)
        messages = [{"role": "user", "content": initial_prompt}]
        turn_index = 0

        try:
            while turn_index < self.max_turns:
                turn_index += 1
                logger.info(f"Turn {turn_index}/{self.max_turns}")

                # Call LLM with tools
                response = completion(
                    model=self.llm_client.config.default_model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        *messages,
                    ],
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=self.llm_client.config.temperature,
                    max_tokens=self.llm_client.config.max_tokens,
                )

                assistant_message = response.choices[0].message
                reasoning = assistant_message.content or None
                tool_calls_raw = assistant_message.tool_calls or []

                # No tool calls → LLM finished without calling finish tool
                if not tool_calls_raw:
                    logger.warning("LLM stopped without calling finish tool")
                    record.status = "failed"
                    record.finish_result = FinishResult(
                        summary="Agent stopped without calling finish",
                        success=False,
                        failure_reason="No tool calls in final turn",
                    )
                    break

                # Parse tool calls
                calls = []
                for tc in tool_calls_raw:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    calls.append(
                        ToolCall(
                            tool_name=tc.function.name,
                            arguments=args,
                            call_id=tc.id,
                        )
                    )

                # Execute tools
                results = [dispatcher.dispatch(call) for call in calls]

                # Record turn
                turn = ToolTurn(
                    turn_index=turn_index,
                    calls=calls,
                    results=results,
                    llm_reasoning=reasoning,
                )
                record.turns.append(turn)

                # Check for finish
                finish_call = next(
                    (c for c in calls if c.tool_name == "finish"), None
                )
                if finish_call:
                    record.finish_result = FinishResult(**finish_call.arguments)
                    record.status = "finished"
                    break

                # Append tool results to messages for next turn
                messages.append(
                    {
                        "role": "assistant",
                        "content": reasoning,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls_raw
                        ],
                    }
                )
                messages.extend(
                    [
                        {
                            "role": "tool",
                            "tool_call_id": r.call_id,
                            "content": r.stdout or r.stderr or r.error or "",
                        }
                        for r in results
                    ]
                )

            # Max turns reached without finish
            if record.status == "running":
                record.status = "timeout"
                record.finish_result = FinishResult(
                    summary=f"Timeout after {self.max_turns} turns",
                    success=False,
                    failure_reason="max_turns_exceeded",
                )

        except Exception as e:
            logger.exception("ToolAgent iteration failed")
            record.status = "failed"
            record.finish_result = FinishResult(
                summary=f"Agent error: {e}",
                success=False,
                failure_reason=str(e),
            )

        record.finished_at = datetime.now(timezone.utc)
        record.total_turns = len(record.turns)
        return record
