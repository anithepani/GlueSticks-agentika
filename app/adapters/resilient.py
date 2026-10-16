"""Resilience wrappers: if a primary adapter fails, fall back without failing the case."""

from __future__ import annotations

from app.interfaces import Extractor, Verifier
from app.models import Document, Fact, Recommendation, RuleResult, Verification


class ResilientExtractor:
    def __init__(self, primary: Extractor, fallback: Extractor) -> None:
        self._primary = primary
        self._fallback = fallback
        self.name = f"{primary.name}(fallback:{fallback.name})"

    def extract(self, documents: list[Document], packet: dict) -> list[Fact]:
        try:
            return self._primary.extract(documents, packet)
        except Exception:
            facts = self._fallback.extract(documents, packet)
            for fact in facts:
                fact.method = f"{self._fallback.name}(fallback)"
            return facts


class ResilientVerifier:
    def __init__(self, primary: Verifier, fallback: Verifier) -> None:
        self._primary = primary
        self._fallback = fallback
        self.name = f"{primary.name}(fallback:{fallback.name})"

    def verify(
        self,
        documents: list[Document],
        facts: list[Fact],
        rules: list[RuleResult],
        recommendation: Recommendation,
    ) -> Verification:
        try:
            return self._primary.verify(documents, facts, rules, recommendation)
        except Exception as exc:
            verification = self._fallback.verify(documents, facts, rules, recommendation)
            verification.checks.append(
                {
                    "check": "verifier_fallback",
                    "fact": "*",
                    "ok": True,
                    "note": f"primary verifier failed, used deterministic checks ({exc})",
                }
            )
            return verification
