"""Minimal OpenAI API client (standard library only) for OpenAI-based processors.

OpenAI publishes no official MCP server for vision, so processors call the official API
directly over HTTPS instead of trusting a third-party server with the key. The key comes
from the shell or .env and is never printed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from lib.workspace import dotenv_value

API_BASE = "https://api.openai.com/v1"
DEFAULT_VISION_MODEL = "gpt-6-luna"  # OpenAI's model for focused, high-volume tasks


class OpenAIError(Exception):
    """An API failure with a short explanation that never contains the key."""

    def __init__(self, status: int | None, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def setting(name: str, default: str | None = None) -> str | None:
    """A value from the shell, else from .env, else the default."""
    return os.environ.get(name, "").strip() or dotenv_value(name) or default


def request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: float = 180,
) -> dict[str, Any]:
    key = setting("OPENAI_API_KEY")
    if not key:
        raise OpenAIError(
            None, "missing_key", "OPENAI_API_KEY is not set; add it to .env"
        )
    base = (setting("OPENAI_BASE_URL") or API_BASE).rstrip("/")
    if not base.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise OpenAIError(None, "bad_base_url", "OPENAI_BASE_URL must use https")
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(
            req, timeout=timeout
        ) as response:  # noqa: S310 - checked above
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error = json.loads(exc.read().decode("utf-8", "replace")).get("error") or {}
        except ValueError:
            error = {}
        code = error.get("code") or error.get("type") or f"http_{exc.code}"
        raise OpenAIError(
            exc.code, code, (error.get("message") or str(exc.reason))[:300]
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OpenAIError(
            None, "network", str(getattr(exc, "reason", exc))[:200]
        ) from None


def output_text(response: dict[str, Any]) -> str:
    """The text answer of a Responses API reply."""
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "output_text":
                return part.get("text", "")
            if part.get("type") == "refusal":
                raise OpenAIError(None, "refusal", str(part.get("refusal", ""))[:200])
    reason = (response.get("incomplete_details") or {}).get("reason")
    raise OpenAIError(
        None,
        "no_output",
        f"status {response.get('status')}" + (f" ({reason})" if reason else ""),
    )
