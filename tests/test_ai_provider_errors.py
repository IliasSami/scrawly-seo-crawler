"""AI provider failures surface the provider's own message, not a raw HTTP line."""
import httpx
import pytest
import respx

from sentinelseo.ai.provider import AIProviderError, ai_complete

CFG = {"kind": "openai", "base_url": "https://llm.test/v1", "model": "m", "api_key": "k"}


@respx.mock
def test_model_not_available_message() -> None:
    respx.post("https://llm.test/v1/chat/completions").mock(return_value=httpx.Response(
        400, json={"error": {"type": "bad_request", "message": "The requested model is not available."}}))
    with pytest.raises(AIProviderError, match="model is not available"):
        ai_complete(CFG, "system", "prompt")


@respx.mock
def test_credit_message_and_auth_hint() -> None:
    respx.post("https://llm.test/v1/chat/completions").mock(return_value=httpx.Response(
        402, json={"error": {"message": "Insufficient credits. Please top up your balance."}}))
    with pytest.raises(AIProviderError, match="Insufficient credits"):
        ai_complete(CFG, "system", "prompt")
    respx.post("https://llm.test/v1/chat/completions").mock(return_value=httpx.Response(401, text="nope"))
    with pytest.raises(AIProviderError, match="Check the API key"):
        ai_complete(CFG, "system", "prompt")


@respx.mock
def test_success_still_returns_text() -> None:
    respx.post("https://llm.test/v1/chat/completions").mock(return_value=httpx.Response(
        200, json={"choices": [{"message": {"content": " Hello "}}]}))
    assert ai_complete(CFG, "system", "prompt") == "Hello"
