import pytest
from pydantic import ValidationError

from app.llm.models import LLMMessage, LLMRequest, LLMResponse, TokenUsage


def test_llm_message_model() -> None:
    message = LLMMessage(role="user", content="Hello")
    assert message.role == "user"
    assert message.content == "Hello"


def test_llm_request_model() -> None:
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="Hi")],
        model="anthropic/claude-sonnet-4",
        temperature=0.5,
        max_tokens=100,
        metadata={"source": "test"},
    )
    assert request.model == "anthropic/claude-sonnet-4"
    assert request.max_tokens == 100
    assert request.metadata["source"] == "test"


def test_llm_response_model() -> None:
    response = LLMResponse(
        content="Answer",
        model="openai/gpt-4o-mini",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        latency_ms=123.4,
    )
    assert response.content == "Answer"
    assert response.usage.total_tokens == 15


def test_llm_request_temperature_validation() -> None:
    with pytest.raises(ValidationError):
        LLMRequest(
            messages=[LLMMessage(role="user", content="Hi")],
            temperature=3.0,
        )
