"""Unit tests for LLMClient with mocked litellm calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import litellm
import pytest

from src.llm.client import LLMClient, LLMConfig
from src.schemas import CostUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_response(
    content: str = "test",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    response._hidden_params = {"response_cost": 0.001}
    return response


MESSAGES = [{"role": "user", "content": "hi"}]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("src.llm.client.completion")
def test_single_call_success(mock_completion: MagicMock) -> None:
    """A single successful call returns content and correct CostUsage."""
    mock_completion.return_value = make_mock_response(
        content="hello", prompt_tokens=100, completion_tokens=50
    )

    client = LLMClient()
    text, cost = client.complete(MESSAGES)

    assert text == "hello"
    assert cost.llm_calls == 1
    assert cost.input_tokens == 100
    assert cost.output_tokens == 50
    assert cost.estimated_cost_usd == pytest.approx(0.001)
    mock_completion.assert_called_once()


@patch("src.llm.client.completion")
def test_cost_accumulation(mock_completion: MagicMock) -> None:
    """Two successful calls accumulate cost correctly."""
    mock_completion.side_effect = [
        make_mock_response(prompt_tokens=100, completion_tokens=50),
        make_mock_response(prompt_tokens=200, completion_tokens=80),
    ]

    client = LLMClient()
    client.complete(MESSAGES)
    client.complete(MESSAGES)

    acc = client.accumulated_cost
    assert acc.llm_calls == 2
    assert acc.input_tokens == 300
    assert acc.output_tokens == 130


@patch("src.llm.client.completion")
def test_timeout_retry(mock_completion: MagicMock) -> None:
    """Timeout errors are retried up to timeout_retries times then succeed."""
    mock_completion.side_effect = [
        litellm.Timeout("timeout", model="test", llm_provider="test"),
        litellm.Timeout("timeout", model="test", llm_provider="test"),
        make_mock_response(content="ok"),
    ]

    config = LLMConfig(timeout_retries=2)
    client = LLMClient(config=config)
    text, _cost = client.complete(MESSAGES)

    assert text == "ok"
    assert mock_completion.call_count == 3


@patch("src.llm.client.completion")
def test_timeout_exhausted(mock_completion: MagicMock) -> None:
    """When timeout retries are exhausted the error propagates."""
    mock_completion.side_effect = litellm.Timeout(
        "timeout", model="test", llm_provider="test"
    )

    config = LLMConfig(timeout_retries=1)
    client = LLMClient(config=config)

    # Primary exhausts retries, then fallback also fails -> RuntimeError
    with pytest.raises(RuntimeError, match="Both primary.*and fallback.*failed"):
        client.complete(MESSAGES)


@patch("src.llm.client.time.sleep")
@patch("src.llm.client.completion")
def test_rate_limit_retry(mock_completion: MagicMock, mock_sleep: MagicMock) -> None:
    """Rate-limit errors are retried with backoff then succeed."""
    rate_err = litellm.RateLimitError(
        "rate limited",
        llm_provider="test",
        model="test",
        response=MagicMock(status_code=429),
    )
    mock_completion.side_effect = [
        rate_err,
        rate_err,
        make_mock_response(content="recovered"),
    ]

    config = LLMConfig(rate_limit_retries=3, rate_limit_base_delay_sec=0.01)
    client = LLMClient(config=config)
    text, _cost = client.complete(MESSAGES)

    assert text == "recovered"
    assert mock_completion.call_count == 3
    assert mock_sleep.call_count == 2


@patch("src.llm.client.completion")
def test_fallback_model(mock_completion: MagicMock) -> None:
    """When the primary model fails, the fallback model is tried."""
    mock_completion.side_effect = [
        Exception("primary down"),
        make_mock_response(content="fallback ok"),
    ]

    config = LLMConfig(
        default_model="primary-model",
        fallback_model="fallback-model",
        timeout_retries=0,
        rate_limit_retries=0,
    )
    client = LLMClient(config=config)
    text, _cost = client.complete(MESSAGES)

    assert text == "fallback ok"
    # Second call should use the fallback model
    assert mock_completion.call_count == 2
    second_call_kwargs = mock_completion.call_args_list[1]
    assert second_call_kwargs.kwargs.get("model") == "fallback-model"


@patch("src.llm.client.completion")
def test_reset_cost(mock_completion: MagicMock) -> None:
    """reset_cost() zeroes out accumulated cost."""
    mock_completion.return_value = make_mock_response(
        prompt_tokens=50, completion_tokens=20
    )

    client = LLMClient()
    client.complete(MESSAGES)

    assert client.accumulated_cost.llm_calls > 0

    client.reset_cost()

    assert client.accumulated_cost == CostUsage()
