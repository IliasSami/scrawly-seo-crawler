"""Pluggable AI provider for generating SEO fix suggestions.

Two wire formats cover every popular provider:
  - "anthropic"  → POST {base}/v1/messages (x-api-key + anthropic-version)
  - "openai"     → POST {base}/chat/completions (Bearer) — OpenAI-compatible,
                   which also covers DeepSeek, OpenRouter, GLM, Nara Router,
                   Together, Groq, and any custom OpenAI-compatible endpoint.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List

import httpx


class AIProviderError(RuntimeError):
    """The AI provider refused a request. The message is plain and safe to show."""


_HINTS = {
    401: "Check the API key.",
    403: "Check the API key's permissions.",
    404: "Check the provider address and the model name.",
    429: "The provider is limiting requests; try again shortly.",
}


def _check(resp: httpx.Response) -> None:
    """Raise AIProviderError carrying the provider's own explanation (e.g. "The
    requested model is not available") instead of a bare HTTP status line."""
    if resp.is_success:
        return
    data: Any = {}
    try:
        resp.read()
        data = resp.json()
    except (ValueError, httpx.HTTPError):
        data = {}
    msg: Any = ""
    if isinstance(data, dict):
        err = data.get("error")
        msg = (err.get("message") if isinstance(err, dict) else err) or data.get("message") or ""
    text = f"The AI provider returned an error ({resp.status_code})"
    text += f": {str(msg).strip()[:200]}" if msg else "."
    hint = _HINTS.get(resp.status_code)
    if hint:
        text += f" {hint}"
    raise AIProviderError(text)


# preset name → default {kind, base_url, model}. `base_url`/`model` are editable.
AI_PRESETS: Dict[str, Dict[str, str]] = {
    "anthropic": {"kind": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude-sonnet-5"},
    "openai": {"kind": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "deepseek": {"kind": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "openrouter": {"kind": "openai", "base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini"},
    "glm": {"kind": "openai", "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "nara": {"kind": "openai", "base_url": "", "model": ""},
    "opencode": {"kind": "openai", "base_url": "", "model": ""},
    "custom": {"kind": "openai", "base_url": "", "model": ""},
}


def is_configured(cfg: Dict[str, Any]) -> bool:
    return bool(
        (cfg.get("api_key") or "").strip()
        and (cfg.get("base_url") or "").strip()
        and (cfg.get("model") or "").strip()
    )


def ai_complete(cfg: Dict[str, Any], system: str, prompt: str, max_tokens: int = 400) -> str:
    """Call the configured provider and return the assistant text. Raises on error."""
    if not is_configured(cfg):
        raise ValueError("AI is not configured (need api_key, base_url and model).")
    kind = (cfg.get("kind") or "openai").strip()
    key = str(cfg["api_key"]).strip()
    base = str(cfg["base_url"]).strip().rstrip("/")
    model = str(cfg["model"]).strip()

    if kind == "anthropic":
        resp = httpx.post(
            f"{base}/v1/messages",
            timeout=45.0,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        _check(resp)
        data = resp.json()
        return "".join(
            b.get("text", "") for b in data.get("content", []) if isinstance(b, dict)
        ).strip()

    # OpenAI-compatible chat completions.
    resp = httpx.post(
        f"{base}/chat/completions",
        timeout=45.0,
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
    )
    _check(resp)
    choice = resp.json()["choices"][0]["message"]["content"]
    return str(choice).strip()


def ai_stream(
    cfg: Dict[str, Any],
    system: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 700,
) -> Iterator[str]:
    """Stream assistant text chunks from the configured provider.

    `messages` is a chat history of {role, content} (roles user/assistant);
    `system` is sent out-of-band (Anthropic) or prepended as a system message
    (OpenAI-compatible). Yields incremental text deltas. Raises on setup/HTTP
    errors so the caller can surface them.
    """
    if not is_configured(cfg):
        raise ValueError("AI is not configured (need api_key, base_url and model).")
    kind = (cfg.get("kind") or "openai").strip()
    key = str(cfg["api_key"]).strip()
    base = str(cfg["base_url"]).strip().rstrip("/")
    model = str(cfg["model"]).strip()

    if kind == "anthropic":
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "stream": True,
        }
        with httpx.stream(
            "POST",
            f"{base}/v1/messages",
            timeout=60.0,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        ) as resp:
            _check(resp)
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    evt = json.loads(data)
                except ValueError:
                    continue
                if evt.get("type") == "content_block_delta":
                    text = (evt.get("delta") or {}).get("text")
                    if text:
                        yield str(text)
        return

    # OpenAI-compatible streaming chat completions.
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "stream": True,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    with httpx.stream(
        "POST",
        f"{base}/chat/completions",
        timeout=60.0,
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json=payload,
    ) as resp:
        _check(resp)
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except ValueError:
                continue
            choices = evt.get("choices") or [{}]
            delta = (choices[0].get("delta") or {}).get("content")
            if delta:
                yield str(delta)
