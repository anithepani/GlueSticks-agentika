"""Minimal stdlib-only LLM client for Groq and Gemini. No extra dependencies.

Both providers are asked for strict JSON. Any transport or parse failure raises
LLMError so callers can fall back to a deterministic path instead of guessing.

Secrets are never placed in a URL and never included in an error message: the
provider key is sent as an Authorization / x-goog-api-key header, all error text
is passed through `redact()`, and the dataclass repr hides the key.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_TIMEOUT = 20.0

_KEY_QUERY = re.compile(r"(?i)([?&](?:key|api_key|apikey|token|access_token)=)[^&\s]+")
_BEARER = re.compile(r"(?i)(bearer\s+)\S+")
_GOOG = re.compile(r"(?i)(x-goog-api-key['\"]?\s*[:=]\s*['\"]?)\S+")


class LLMError(RuntimeError):
    pass


def redact(text, *secrets: str) -> str:
    """Remove provider keys from any string that might surface to a client."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), "***")
    out = _KEY_QUERY.sub(r"\1***", out)
    out = _BEARER.sub(r"\1***", out)
    out = _GOOG.sub(r"\1***", out)
    return out


def _timeout() -> float:
    try:
        return float(os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT


def parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise LLMError("no JSON object found in model output")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"invalid JSON from model: {exc}") from exc


def _post(url: str, payload: dict, headers: dict, timeout: float, secrets: tuple[str, ...] = ()) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LLMError(redact(f"HTTP {exc.code}: {detail}", *secrets)) from exc
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(redact(exc, *secrets)) from exc


@dataclass
class LLMClient:
    provider: str
    model: str
    api_key: str = field(repr=False)
    timeout: float | None = None

    def _effective_timeout(self) -> float:
        return self.timeout if self.timeout is not None else _timeout()

    def complete(self, system: str, user: str) -> str:
        if self.provider == "groq":
            return self._groq(system, user)
        if self.provider == "gemini":
            return self._gemini(system, user)
        raise LLMError(f"unknown provider '{self.provider}'")

    def complete_json(self, system: str, user: str) -> dict:
        return parse_json(self.complete(system, user))

    def _groq(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = _post(
            "https://api.groq.com/openai/v1/chat/completions",
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
            self._effective_timeout(),
            (self.api_key,),
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(redact(f"unexpected Groq response: {json.dumps(data)[:300]}", self.api_key)) from exc

    def _gemini(self, system: str, user: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            ":generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        data = _post(
            url,
            payload,
            {"x-goog-api-key": self.api_key},
            self._effective_timeout(),
            (self.api_key,),
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(redact(f"unexpected Gemini response: {json.dumps(data)[:300]}", self.api_key)) from exc


def build_llm_client() -> LLMClient | None:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider == "groq":
        key = os.getenv("GROQ_API_KEY", "").strip()
        if not key:
            return None
        return LLMClient("groq", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), key)
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            return None
        return LLMClient("gemini", os.getenv("GEMINI_MODEL", "gemini-1.5-flash"), key)
    return None
