"""Resilience wrappers: if a primary adapter fails, fall back without failing the case."""

from __future__ import annotations

from app.interfaces import AuditLog, Extractor, Verifier
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


class ResilientAudit:
    """Prefer the primary ledger; on any failure, degrade to the fallback ledger.

    The mode is reported so /api/diag can show which ledger is in use. Writes are
    best-effort: if the primary is down, entries land in the fallback and are
    detectable by inspecting the ledger name.
    """

    def __init__(self, primary: AuditLog, fallback: AuditLog) -> None:
        self._primary = primary
        self._fallback = fallback
        self.name = f"{primary.name}(fallback:{fallback.name})"
        self.degraded = False

    def _active(self) -> AuditLog:
        return self._fallback if self.degraded else self._primary

    def append(self, case_id: str, event: str, actor: str | None, payload: dict) -> dict:
        try:
            return self._primary.append(case_id, event, actor, payload)
        except Exception:
            self.degraded = True
            return self._fallback.append(case_id, event, actor, payload)

    def entries(self, case_id: str | None = None) -> list[dict]:
        try:
            return self._active().entries(case_id)
        except Exception:
            self.degraded = True
            return self._fallback.entries(case_id)

    def has_event(self, case_id: str, event: str) -> bool:
        try:
            return self._active().has_event(case_id, event)
        except Exception:
            self.degraded = True
            return self._fallback.has_event(case_id, event)

    def verify(self) -> dict:
        try:
            result = dict(self._active().verify())
        except Exception:
            self.degraded = True
            result = dict(self._fallback.verify())
        result["ledger"] = self._fallback.name if self.degraded else self._primary.name
        return result
