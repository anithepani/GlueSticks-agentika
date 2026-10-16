"""Evaluation gate: run the pipeline over the seeded set and score it.

This is the check the hackathon judges (and Alternate Futures' philosophy) care
about: deterministic outcomes, grounded citations, honest abstention, and a hard
invariant that the automated pipeline never denies anyone.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import POLICY_DIR, AdapterBundle
from app.adapters import DeterministicVerifier, FixtureExtractor
from app.embedded import DEFAULT_GOLDEN
from app.models import STATUS_DENIED
from app.pipeline import run_pipeline
from app.seed_cases import load_packets

GOLDEN_PATH = POLICY_DIR.parent / "eval" / "golden.json"

PRE_HUMAN_STATUSES = ("INTAKE", "VERIFIED", "NEEDS_REVIEW")


def deterministic_view(bundle: AdapterBundle) -> AdapterBundle:
    """The reproducible slice of the pipeline that the gate scores.

    Extraction/verification are pinned to the deterministic adapters so the gate
    is stable regardless of whether an LLM key is configured or the model drifts.
    The reader, rules and audit are reused as-is.
    """
    return AdapterBundle(
        reader=bundle.reader,
        extractor=FixtureExtractor(),
        rules=bundle.rules,
        verifier=DeterministicVerifier(),
        audit=bundle.audit,
    )


def _load_golden() -> dict[str, dict]:
    entries = DEFAULT_GOLDEN
    if GOLDEN_PATH.exists():
        data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        entries = data.get("cases", entries)
    return {entry["id"]: entry for entry in entries}


def evaluate(bundle: AdapterBundle) -> dict:
    packets, source, _ = load_packets()
    expected = _load_golden()
    gate_bundle = deterministic_view(bundle)
    details: list[dict] = []
    grounded_total = 0
    facts_total = 0
    abstains = 0
    checks_passed = 0
    checks_total = 0
    no_auto_deny = True

    for packet in packets:
        case = run_pipeline(packet, gate_bundle)
        rules = {rule.rule_id: rule.status for rule in case.rules}
        grounded = sum(1 for fact in case.facts if fact.citation is not None)
        grounded_total += grounded
        facts_total += len(case.facts)
        if case.verification.status == "ABSTAIN":
            abstains += 1
        if case.status == STATUS_DENIED:
            no_auto_deny = False

        want = expected.get(case.id)
        case_checks: list[dict] = []
        if want:
            case_checks = [
                _check("status", case.status, want.get("status")),
                _check("outcome", case.recommendation.outcome, want.get("outcome")),
                _check("verification", case.verification.status, want.get("verification")),
                _check(
                    "verification_has_reasons",
                    bool(case.verification.reasons),
                    want.get("verification_has_reasons"),
                ),
            ]
            for rule_id, want_status in (want.get("rules") or {}).items():
                case_checks.append(_check(f"rule:{rule_id}", rules.get(rule_id), want_status))
            checks_passed += sum(1 for check in case_checks if check["ok"])
            checks_total += len(case_checks)

        details.append(
            {
                "id": case.id,
                "status": case.status,
                "outcome": case.recommendation.outcome,
                "verification": case.verification.status,
                "grounded": grounded,
                "facts": len(case.facts),
                "rules": rules,
                "checks": case_checks,
            }
        )

    return {
        "seed_source": source,
        "cases": len(packets),
        "scored_path": {"extractor": "fixture", "verifier": "det"},
        "metrics": {
            "grounding_rate": round(grounded_total / facts_total, 3) if facts_total else 0.0,
            "abstain_rate": round(abstains / len(packets), 3) if packets else 0.0,
            "expectations_met": checks_passed,
            "expectations_total": checks_total,
        },
        "invariants": {
            "no_auto_deny": no_auto_deny,
            "pre_human_statuses": list(PRE_HUMAN_STATUSES),
        },
        "all_passed": no_auto_deny and checks_total > 0 and checks_passed == checks_total,
        "details": details,
    }


def _check(name: str, got, want) -> dict:
    return {"name": name, "ok": want is None or got == want, "got": got, "want": want}
