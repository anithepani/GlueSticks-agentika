"""Minimal stdlib-only LLM client for Groq and Gemini. No extra dependencies.

Both providers are asked for strict JSON. Any transport or parse failure raises
LLMError so callers can fall back to a deterministic path instead of guessing.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))


class LLMError(RuntimeError):
    pass


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


def _post(url: str, payload: dict, headers: dict, timeout: float) -> dict:
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
        raise LLMError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise LLMError(str(exc)) from exc


@dataclass
class LLMClient:
    provider: str
    model: str
    api_key: str
    timeout: float = DEFAULT_TIMEOUT

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
            self.timeout,
        )
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected Groq response: {json.dumps(data)[:300]}") from exc

    def _gemini(self, system: str, user: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        data = _post(url, payload, {}, self.timeout)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected Gemini response: {json.dumps(data)[:300]}") from exc


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
