"""Adapter tests for the LLM extractor/verifier using a scripted fake client.

No network and no API key required. Run: python tests/test_llm.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from app.adapters.extractor_fixture import FixtureExtractor
from app.adapters.extractor_llm import LLMExtractor
from app.adapters.resilient import ResilientExtractor
from app.adapters.rules_pmt import PmtRules
from app.adapters.reader_text import TextReader
from app.adapters.verifier_det import DeterministicVerifier
from app.adapters.verifier_llm import LLMVerifier
from app.models import OUTCOME_ELIGIBLE, VERIFY_ABSTAIN, VERIFY_OK, Recommendation
from app.seed_cases import DEFAULT_CASES


class FakeClient:
    provider = "fake"
    model = "fake-1"

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def complete_json(self, system, user):
        if self._error:
            raise self._error
        return self._response


def case_one():
    packet = DEFAULT_CASES[0]
    documents = TextReader().read(packet)
    facts = FixtureExtractor().extract(documents, packet)
    rules = PmtRules().evaluate(facts)
    return documents, facts, rules, Recommendation(OUTCOME_ELIGIBLE, [])


def test_extractor_grounds_only_verbatim_quotes():
    packet = DEFAULT_CASES[0]
    documents = TextReader().read(packet)
    fake = FakeClient(
        response={
            "facts": [
                {"key": "age", "value": 34, "quote": "Age: 34 years", "doc_id": "d1"},
                {"key": "province", "value": "Punjab", "quote": "Province of residence: Punjab", "doc_id": "d1"},
                {"key": "household_size", "value": 5, "quote": "Household size: 99 persons", "doc_id": "d1"},
                {"key": "monthly_income_pkr", "value": None, "quote": "", "doc_id": "d1"},
                {"key": "not_a_field", "value": 1, "quote": "Age: 34 years", "doc_id": "d1"},
            ]
        }
    )
    facts = LLMExtractor(fake).extract(documents, packet)
    by_key = {fact.key: fact for fact in facts}

    assert "monthly_income_pkr" not in by_key, "null values must be skipped"
    assert "not_a_field" not in by_key, "unknown keys must be dropped"
    assert by_key["age"].citation is not None and by_key["age"].citation.grounded
    assert by_key["household_size"].citation is None, "invented quote must not be grounded"
    assert all(fact.method == "llm" for fact in facts)
    print("OK: LLM extractor grounds verbatim, drops nulls/unknowns, flags invented quotes")


def test_verifier_can_abstain_only_add():
    documents, facts, rules, rec = case_one()
    clean = DeterministicVerifier().verify(documents, facts, rules, rec)
    assert clean.status == VERIFY_OK, clean.status

    income_index = next(i for i, f in enumerate(facts) if f.key == "monthly_income_pkr")
    fake = FakeClient(
        response={
            "judgments": [
                {"i": income_index, "supports": False, "reason": "quote does not state an income amount"},
            ]
        }
    )
    verdict = LLMVerifier(fake).verify(documents, facts, rules, rec)
    assert verdict.status == VERIFY_ABSTAIN, verdict.status
    assert any("disputed" in reason for reason in verdict.reasons), verdict.reasons
    assert any(
        c["check"] == "llm_adjudication" and c["ok"] is False for c in verdict.checks
    ), verdict.checks
    print("OK: LLM verifier adds an abstain (never silently clears a failure)")

    agree = FakeClient(response={"judgments": [{"i": i, "supports": True, "reason": "ok"} for i in range(len(facts))]})
    verdict2 = LLMVerifier(agree).verify(documents, facts, rules, rec)
    assert verdict2.status == VERIFY_OK, verdict2.status
    print("OK: agreement keeps a passing case passing")


def test_verifier_model_outage_keeps_deterministic_result():
    documents, facts, rules, rec = case_one()
    from app.adapters.llm_client import LLMError

    verdict = LLMVerifier(FakeClient(error=LLMError("timeout"))).verify(documents, facts, rules, rec)
    assert verdict.status == VERIFY_OK, verdict.status
    assert any(c["check"] == "llm_adjudication" for c in verdict.checks)
    print("OK: verifier outage degrades to deterministic checks")


def test_resilient_extractor_falls_back():
    packet = DEFAULT_CASES[0]
    documents = TextReader().read(packet)

    class Boom:
        name = "llm"

        def extract(self, documents, packet):
            raise RuntimeError("api down")

    facts = ResilientExtractor(Boom(), FixtureExtractor()).extract(documents, packet)
    assert facts and all("fallback" in fact.method for fact in facts), [f.method for f in facts]
    print("OK: resilient extractor falls back to fixture on failure")


def test_no_key_means_no_llm_client():
    saved = {k: os.environ.pop(k, None) for k in ("GROQ_API_KEY", "GEMINI_API_KEY")}
    try:
        from app.adapters.llm_client import build_llm_client

        assert build_llm_client() is None
        print("OK: no API key -> no LLM client (fixture/deterministic path stays in use)")
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def main() -> int:
    test_extractor_grounds_only_verbatim_quotes()
    test_verifier_can_abstain_only_add()
    test_verifier_model_outage_keeps_deterministic_result()
    test_resilient_extractor_falls_back()
    test_no_key_means_no_llm_client()
    print("ALL LLM ADAPTER TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
