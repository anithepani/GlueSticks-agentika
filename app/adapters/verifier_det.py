"""Independent deterministic verifier.

The verifier re-audits the pipeline's own work rather than trusting it. It refuses
to endorse a recommendation when a citation is not found verbatim in its source, a
field has conflicting values, or a rule could not be decided. An abstain never
denies anyone: it escalates the case to a human officer.
"""

from __future__ import annotations

from app.models import (
    VERIFY_ABSTAIN,
    VERIFY_OK,
    Document,
    Fact,
    Recommendation,
    RuleResult,
    Verification,
)


class DeterministicVerifier:
    name = "det"

    def verify(
        self,
        documents: list[Document],
        facts: list[Fact],
        rules: list[RuleResult],
        recommendation: Recommendation,
    ) -> Verification:
        checks: list[dict] = []
        reasons: list[str] = []
        doc_text = {document.doc_id: document.text for document in documents}

        self._grounding(facts, doc_text, checks, reasons)
        self._contradictions(facts, checks, reasons)
        self._undecided(rules, reasons)

        status = VERIFY_OK if not reasons else VERIFY_ABSTAIN
        return Verification(status=status, checks=checks, reasons=reasons)

    def _grounding(
        self,
        facts: list[Fact],
        doc_text: dict[str, str],
        checks: list[dict],
        reasons: list[str],
    ) -> None:
        for fact in facts:
            if fact.citation is None:
                ok = False
                note = "no citation attached to this fact"
            else:
                source = doc_text.get(fact.citation.doc_id)
                ok = source is not None and fact.citation.quote in source
                note = "quote found verbatim in source" if ok else "quote not found verbatim in source"
            checks.append({"check": "citation_grounding", "fact": fact.key, "ok": ok, "note": note})
            if not ok:
                reasons.append(f"Grounding failed for '{fact.label}': {note}.")

    def _contradictions(self, facts: list[Fact], checks: list[dict], reasons: list[str]) -> None:
        grouped: dict[str, list[Fact]] = {}
        for fact in facts:
            grouped.setdefault(fact.key, []).append(fact)
        for key, items in grouped.items():
            values = sorted({repr(item.value) for item in items})
            ok = len(values) <= 1
            note = "consistent" if ok else f"conflicting values: {', '.join(values)}"
            checks.append({"check": "contradiction", "fact": key, "ok": ok, "note": note})
            if not ok:
                reasons.append(f"Conflicting values for '{key}': {', '.join(values)}.")

    def _undecided(self, rules: list[RuleResult], reasons: list[str]) -> None:
        for rule in rules:
            if rule.status == "UNKNOWN":
                reasons.append(f"Rule {rule.rule_id} could not be decided: {rule.detail}")
