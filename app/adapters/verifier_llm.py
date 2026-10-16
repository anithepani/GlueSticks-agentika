"""LLM adjudication layered on top of the deterministic verifier.

Design rule: the model may only make the verdict *more* cautious. It re-reads each
grounded citation and asks whether the quote really states the value. It can add an
abstain; it can never clear a deterministic failure. If the model is unavailable the
deterministic result stands untouched.
"""

from __future__ import annotations

from app.adapters.llm_client import LLMClient, LLMError
from app.adapters.verifier_det import DeterministicVerifier
from app.models import (
    VERIFY_ABSTAIN,
    Document,
    Fact,
    Recommendation,
    RuleResult,
    Verification,
)

SYSTEM = (
    "You are an auditor checking whether a quoted span of text actually states a claimed "
    "value. You only output JSON and you are strict: if the quote does not directly support "
    "the value, you answer false."
)


class LLMVerifier:
    name = "llm"

    def __init__(self, client: LLMClient, primary: DeterministicVerifier | None = None) -> None:
        self._client = client
        self._primary = primary or DeterministicVerifier()

    def verify(
        self,
        documents: list[Document],
        facts: list[Fact],
        rules: list[RuleResult],
        recommendation: Recommendation,
    ) -> Verification:
        verification = self._primary.verify(documents, facts, rules, recommendation)
        grounded = [fact for fact in facts if fact.citation is not None]
        if not grounded:
            return verification
        try:
            judgments = self._judge(grounded)
        except (LLMError, ValueError) as exc:
            verification.checks.append(
                {
                    "check": "llm_adjudication",
                    "fact": "*",
                    "ok": True,
                    "note": f"model unavailable, deterministic checks only ({exc})",
                }
            )
            return verification

        for index, fact in enumerate(grounded):
            verdict = judgments.get(index)
            if verdict is None:
                continue
            supports = bool(verdict.get("supports"))
            note = str(verdict.get("reason", "")) or (
                "quote supports the value" if supports else "quote does not support the value"
            )
            verification.checks.append(
                {
                    "check": "llm_adjudication",
                    "fact": fact.key,
                    "ok": supports,
                    "note": note,
                }
            )
            if not supports:
                verification.reasons.append(
                    f"Model adjudication disputed '{fact.label}': {note}"
                )

        if verification.reasons:
            verification.status = VERIFY_ABSTAIN
        return verification

    def _judge(self, facts: list[Fact]) -> dict[int, dict]:
        items = []
        for index, fact in enumerate(facts):
            items.append(
                {
                    "i": index,
                    "field": fact.key,
                    "value": fact.value,
                    "quote": fact.citation.quote if fact.citation else "",
                }
            )
        user = (
            "For each item decide whether the quote directly states the value for the field.\n"
            f"{_json(items)}\n\n"
            'Return only: {"judgments": [{"i": <index>, "supports": <true|false>, '
            '"reason": "<short reason>"}]}'
        )
        data = self._client.complete_json(SYSTEM, user)
        raw = data.get("judgments", [])
        if not isinstance(raw, list):
            raise ValueError("model did not return a 'judgments' list")
        judgments: dict[int, dict] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                idx = int(entry.get("i"))
            except (TypeError, ValueError):
                continue
            judgments[idx] = entry
        return judgments


def _json(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
