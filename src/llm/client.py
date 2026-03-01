"""Unified LLM client wrapping litellm with retry, fallback, and cost tracking."""

from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request
import json

import litellm
from litellm import completion
from pydantic import BaseModel

from src.schemas import CostUsage

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    default_model: str = "claude-sonnet-4-6"
    fallback_model: str = "gpt-4o-mini"
    api_base: str | None = None
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_retries: int = 2
    rate_limit_retries: int = 3
    rate_limit_base_delay_sec: float = 1.0


class LLMClient:
    """Thin wrapper around litellm with retry, fallback, and cost tracking."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._accumulated_cost = CostUsage()
        # Suppress litellm's noisy logs
        litellm.suppress_debug_info = True

    @property
    def accumulated_cost(self) -> CostUsage:
        return self._accumulated_cost

    def reset_cost(self) -> None:
        self._accumulated_cost = CostUsage()

    def validate_provider_ready(self) -> None:
        """Fail fast with actionable diagnostics for local providers."""
        model = self.config.default_model
        if not model.startswith("ollama/"):
            return

        api_base = self.config.api_base or "http://127.0.0.1:11434"
        model_name = model.split("/", 1)[1]

        # Avoid proxying localhost in environments that set HTTP(S)_PROXY.
        no_proxy = os.environ.get("NO_PROXY", "")
        required = ["127.0.0.1", "localhost"]
        missing = [item for item in required if item not in no_proxy]
        if missing:
            os.environ["NO_PROXY"] = ",".join([no_proxy, *missing]).strip(",")

        tags_url = f"{api_base.rstrip('/')}/api/tags"
        try:
            with urllib.request.urlopen(tags_url, timeout=3) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Ollama not reachable at {api_base}. "
                f"Start service with 'ollama serve'. Detail: {self._fmt_exc(e)}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to query Ollama tags from {tags_url}. Detail: {self._fmt_exc(e)}"
            ) from e

        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = {m.get("name") for m in models if isinstance(m, dict)}
        if model_name not in names:
            sample = ", ".join(sorted(n for n in names if isinstance(n, str))[:5]) or "<empty>"
            raise RuntimeError(
                f"Ollama model '{model_name}' not found. "
                f"Run 'ollama pull {model_name}'. Installed: {sample}"
            )

    def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> tuple[str, CostUsage]:
        """Call LLM and return (response_text, cost_for_this_call).

        Retry logic:
        - Timeout: retry up to timeout_retries times
        - Rate limit: retry up to rate_limit_retries times with exponential backoff
        - On all retries exhausted for primary model: try fallback model once

        Args:
            messages: List of message dicts
            model: Model to use (defaults to config.default_model)
            system_prompt: Optional system prompt to prepend
            tools: Optional list of tool definitions for function calling
            tool_choice: Optional tool choice strategy ("auto", "required", etc.)
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}, *messages]

        primary_model = model or self.config.default_model
        try:
            return self._call_with_retries(primary_model, messages, tools, tool_choice)
        except Exception as primary_err:
            logger.warning(
                "Primary model %s failed: %s. Trying fallback %s",
                primary_model,
                self._fmt_exc(primary_err),
                self.config.fallback_model,
            )
            try:
                return self._call_with_retries(self.config.fallback_model, messages, tools, tool_choice)
            except Exception as fallback_err:
                raise RuntimeError(
                    f"Both primary ({primary_model}) and fallback "
                    f"({self.config.fallback_model}) models failed. "
                    f"Primary: {self._fmt_exc(primary_err)}, "
                    f"Fallback: {self._fmt_exc(fallback_err)}"
                ) from fallback_err

    def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        model: str | None = None,
        system_prompt: str | None = None,
        tool_choice: str | None = None,
    ) -> tuple[any, CostUsage]:
        """Call LLM with tools and return (full_response_object, cost).

        This method returns the full litellm response object to support tool calling.
        Use this when you need access to tool_calls in the response.

        Args:
            messages: List of message dicts
            tools: List of tool definitions for function calling
            model: Model to use (defaults to config.default_model)
            system_prompt: Optional system prompt to prepend
            tool_choice: Optional tool choice strategy ("auto", "required", etc.)

        Returns:
            Tuple of (litellm_response_object, CostUsage)
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}, *messages]

        primary_model = model or self.config.default_model
        try:
            return self._call_with_tools_retries(primary_model, messages, tools, tool_choice)
        except Exception as primary_err:
            logger.warning(
                "Primary model %s failed: %s. Trying fallback %s",
                primary_model,
                self._fmt_exc(primary_err),
                self.config.fallback_model,
            )
            try:
                return self._call_with_tools_retries(self.config.fallback_model, messages, tools, tool_choice)
            except Exception as fallback_err:
                raise RuntimeError(
                    f"Both primary ({primary_model}) and fallback "
                    f"({self.config.fallback_model}) models failed. "
                    f"Primary: {self._fmt_exc(primary_err)}, "
                    f"Fallback: {self._fmt_exc(fallback_err)}"
                ) from fallback_err

    def _call_with_tools_retries(
        self, model: str, messages: list[dict], tools: list[dict], tool_choice: str | None = None
    ) -> tuple[any, CostUsage]:
        """Call LLM with tools and retries, return (response_object, cost)."""
        last_error: Exception | None = None
        max_attempts = (
            max(self.config.timeout_retries, self.config.rate_limit_retries) + 1
        )

        timeout_attempts = 0
        rate_limit_attempts = 0

        for _ in range(max_attempts):
            try:
                return self._single_call(model, messages, tools, tool_choice)
            except litellm.Timeout as e:
                timeout_attempts += 1
                last_error = e
                if timeout_attempts > self.config.timeout_retries:
                    break
                logger.warning(
                    "Timeout on attempt %d/%d: %s",
                    timeout_attempts,
                    self.config.timeout_retries + 1,
                    self._fmt_exc(e),
                )
                time.sleep(1)
            except litellm.RateLimitError as e:
                rate_limit_attempts += 1
                last_error = e
                if rate_limit_attempts > self.config.rate_limit_retries:
                    break
                backoff = 2 ** rate_limit_attempts
                logger.warning(
                    "Rate limit on attempt %d/%d, backoff %ds: %s",
                    rate_limit_attempts,
                    self.config.rate_limit_retries + 1,
                    backoff,
                    self._fmt_exc(e),
                )
                time.sleep(backoff)
            except Exception as e:
                last_error = e
                break

        raise last_error or RuntimeError("All retry attempts exhausted")

    def _call_with_retries(
        self, model: str, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None
    ) -> tuple[str, CostUsage]:
        """Call LLM with retries and return (content_string, cost)."""
        last_error: Exception | None = None
        max_attempts = (
            max(self.config.timeout_retries, self.config.rate_limit_retries) + 1
        )

        timeout_attempts = 0
        rate_limit_attempts = 0

        for _ in range(max_attempts):
            try:
                response, cost = self._single_call(model, messages, tools, tool_choice)
                # Extract content from response
                content = response.choices[0].message.content or ""
                return content, cost
            except litellm.Timeout as e:
                timeout_attempts += 1
                last_error = e
                if timeout_attempts > self.config.timeout_retries:
                    break
                logger.info("LLM timeout (attempt %d), retrying...", timeout_attempts)
            except litellm.RateLimitError as e:
                rate_limit_attempts += 1
                last_error = e
                if rate_limit_attempts > self.config.rate_limit_retries:
                    break
                delay = self.config.rate_limit_base_delay_sec * (
                    2 ** (rate_limit_attempts - 1)
                )
                logger.info(
                    "Rate limited (attempt %d), waiting %.1fs...",
                    rate_limit_attempts,
                    delay,
                )
                time.sleep(delay)

        raise last_error  # type: ignore[misc]

    def _single_call(self, model: str, messages: list[dict], tools: list[dict] | None = None, tool_choice: str | None = None) -> tuple[any, CostUsage]:
        """Make a single LLM call and return (response_object, cost).

        Returns the full litellm response object to support tool calling.
        """
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        if self.config.api_base and model.startswith("ollama/"):
            kwargs["api_base"] = self.config.api_base

        response = completion(**kwargs)

        usage = response.usage
        call_cost = CostUsage(
            llm_calls=1,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            estimated_cost_usd=response._hidden_params.get("response_cost", 0.0)
            if hasattr(response, "_hidden_params")
            else 0.0,
        )

        self._accumulated_cost = self._accumulated_cost + call_cost
        return response, call_cost

    @staticmethod
    def _fmt_exc(err: Exception) -> str:
        """Format exception to keep messages useful when str(err) is empty."""
        msg = str(err).strip() or repr(err)
        parts = [f"{type(err).__name__}: {msg}"]

        cause = err.__cause__ or err.__context__
        depth = 0
        while cause is not None and depth < 3:
            cmsg = str(cause).strip() or repr(cause)
            parts.append(f"caused_by={type(cause).__name__}: {cmsg}")
            cause = cause.__cause__ or cause.__context__
            depth += 1

        return " | ".join(parts)
