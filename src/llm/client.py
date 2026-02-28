"""Unified LLM client wrapping litellm with retry, fallback, and cost tracking."""

from __future__ import annotations

import logging
import time

import litellm
from litellm import completion
from pydantic import BaseModel

from src.schemas import CostUsage

logger = logging.getLogger(__name__)


class LLMConfig(BaseModel):
    default_model: str = "claude-sonnet-4-6"
    fallback_model: str = "gpt-4o-mini"
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

    def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> tuple[str, CostUsage]:
        """Call LLM and return (response_text, cost_for_this_call).

        Retry logic:
        - Timeout: retry up to timeout_retries times
        - Rate limit: retry up to rate_limit_retries times with exponential backoff
        - On all retries exhausted for primary model: try fallback model once
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}, *messages]

        primary_model = model or self.config.default_model
        try:
            return self._call_with_retries(primary_model, messages)
        except Exception as primary_err:
            logger.warning(
                "Primary model %s failed: %s. Trying fallback %s",
                primary_model,
                primary_err,
                self.config.fallback_model,
            )
            try:
                return self._call_with_retries(self.config.fallback_model, messages)
            except Exception as fallback_err:
                raise RuntimeError(
                    f"Both primary ({primary_model}) and fallback "
                    f"({self.config.fallback_model}) models failed. "
                    f"Primary: {primary_err}, Fallback: {fallback_err}"
                ) from fallback_err

    def _call_with_retries(
        self, model: str, messages: list[dict]
    ) -> tuple[str, CostUsage]:
        last_error: Exception | None = None
        max_attempts = (
            max(self.config.timeout_retries, self.config.rate_limit_retries) + 1
        )

        timeout_attempts = 0
        rate_limit_attempts = 0

        for _ in range(max_attempts):
            try:
                return self._single_call(model, messages)
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

    def _single_call(self, model: str, messages: list[dict]) -> tuple[str, CostUsage]:
        response = completion(
            model=model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        content = response.choices[0].message.content or ""
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
        return content, call_cost
