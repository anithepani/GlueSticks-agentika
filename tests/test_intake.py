"""Intake, resubmit and evaluation tests. No network required.

Run: python tests/test_intake.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ["AUDIT_DB"] = str(Path(os.environ.get("TEMP", ".")) / "witness_intake_test.db")
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.adapters.extractor_labels import LabelsExtractor
from app.adapters.reader_text import TextReader
from app.evaluation import evaluate
from app.seed_cases import DEFAULT_CASES
from app.models import STATUS_INFO_REQUESTED, STATUS_NEEDS_REVIEW, STATUS_VERIFIED

CLEAN = """Form B-1: Income Support Application
Name: Fatima Noor
Age: 46 years
Province of residence: Punjab
Household size: 6 persons
Monthly household income: PKR 38,000
Owns a car: No"""

CONFLICT_EXTRA = "Income Verification Note\nMonthly household income (revised): PKR 150,000"


def test_labels_extractor_grounds_from_raw_text():
    documents = TextReader().read({"documents": [{"doc_id": "d1", "title": "form", "text": CLEAN}]})
    facts = LabelsExtractor().extract(documents, {})
    by_key = {fact.key: fact for fact in facts}
    assert by_key["age"].value == 46, by_key["age"]
    assert by_key["household_size"].value == 6
    assert by_key["monthly_income_pkr"].value == 38000, by_key["monthly_income_pkr"]
    assert by_key["owns_car"].value is False
    assert by_key["province"].value == "Punjab"
    assert all(fact.citation is not None for fact in facts), "every fact must be grounded"
    print("OK: labels extractor pulls age/province/size/income/car from pasted text")


def test_labels_extractor_omits_missing_fields():
    text = "Form B-1\nName: Test\nAge: 30 years\nOwns a car: No"
    documents = TextReader().read({"documents": [{"doc_id": "d1", "title": "form", "text": text}]})
    keys = {fact.key for fact in LabelsExtractor().extract(documents, {})}
    assert "monthly_income_pkr" not in keys and "household_size" not in keys, keys
    print("OK: labels extractor omits absent fields (so their rules become UNKNOWN)")


def build_store():
    from app.config import CASES_DIR, build_adapters
    from app.store import CaseStore

    bundle = build_adapters()
    store = CaseStore(bundle, CASES_DIR)
    store.seed()
    return store, bundle


def test_intake_runs_pipeline_and_grounds():
    store, _ = build_store()
    case = store.add_case(
        {
            "applicant_name": "Fatima Noor",
            "applicant_cnic": "35202-9999999-1",
            "province": "Punjab",
            "documents": [{"title": "Intake form", "text": CLEAN}],
        }
    )
    assert case.id.startswith("INTK-"), case.id
    assert case.status == STATUS_VERIFIED, (case.status, case.verification.reasons)
    assert case.recommendation.outcome == "ELIGIBLE", case.recommendation
    assert all(fact.citation is not None for fact in case.facts)
    assert store.get(case.id) is not None
    assert [e["event"] for e in store._bundle.audit.entries(case.id)][:2] == ["intake", "pipeline_run"]
    print(f"OK: intake case {case.id} -> {case.status}/{case.recommendation.outcome} fully grounded")


def test_intake_with_contradiction_goes_to_review():
    store, _ = build_store()
    case = store.add_case(
        {
            "applicant_name": "Conflicting Applicant",
            "documents": [
                {"title": "Form", "text": CLEAN},
                {"title": "Note", "text": CONFLICT_EXTRA},
            ],
        }
    )
    assert case.status == STATUS_NEEDS_REVIEW, case.status
    assert case.verification.status == "ABSTAIN", case.verification.status
    assert any("Conflicting" in reason for reason in case.verification.reasons), case.verification.reasons
    print("OK: intake with a second, conflicting document abstains and escalates")


def test_intake_validation_errors():
    store, _ = build_store()
    for bad, needle in (
        ({"documents": [{"text": "x"}]}, "applicant_name"),
        ({"applicant_name": "X", "documents": []}, "document"),
    ):
        try:
            store.add_case(bad)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert needle in str(exc), (needle, str(exc))
    print("OK: intake rejects missing name and empty documents")


def test_request_info_then_resubmit_reruns_pipeline():
    store, _ = build_store()
    case = store.add_case(
        {
            "applicant_name": "Needs Info",
            "documents": [{"title": "Form", "text": CLEAN + "\nNote: income statement not attached."}],
        }
    )
    # Remove the income line to force NEEDS_REVIEW, then request info.
    missing = "\n".join(line for line in CLEAN.splitlines() if "income" not in line.lower())
    case2 = store.add_case({"applicant_name": "Missing Income", "documents": [{"title": "Form", "text": missing}]})
    assert case2.status == STATUS_NEEDS_REVIEW, (case2.status, case2.verification.reasons)

    store.decide(case2.id, "Officer R. Khan", "request_info", "Please provide proof of monthly income.")
    assert store.get(case2.id).status == STATUS_INFO_REQUESTED

    updated = store.resubmit(case2.id, [{"title": "Income proof", "text": "Monthly household income: PKR 25,000"}])
    assert updated.status == STATUS_VERIFIED, (updated.status, updated.verification.reasons)
    assert len(updated.documents) == 2, [d.doc_id for d in updated.documents]
    assert updated.decision is None, "resubmission reopens the case"
    events = [e["event"] for e in store._bundle.audit.entries(case2.id)]
    assert events[-1] == "resubmit", events
    assert "resubmit" in events and "human_decision" in events, events
    print("OK: request_info -> resubmit re-runs the pipeline and reopens the case")

    try:
        store.resubmit(case.id, [{"title": "x", "text": "Monthly household income: PKR 10,000"}])
        raise AssertionError("expected ValueError for non-awaiting case")
    except ValueError as exc:
        assert "awaiting" in str(exc), str(exc)
    print("OK: resubmit is refused unless the case is awaiting information")


def test_evaluation_gate():
    store, bundle = build_store()
    report = evaluate(bundle)
    assert report["cases"] == len(DEFAULT_CASES) == 5, report["cases"]
    assert report["invariants"]["no_auto_deny"] is True, report["invariants"]
    assert report["all_passed"] is True, [
        (d["id"], [c for c in d["checks"] if not c["ok"]]) for d in report["details"]
    ]
    assert report["metrics"]["grounding_rate"] > 0.8, report["metrics"]
    assert 0 < report["metrics"]["abstain_rate"] < 1, report["metrics"]
    print("OK: evaluation gate passes:", report["metrics"], report["invariants"])


def main() -> int:
    test_labels_extractor_grounds_from_raw_text()
    test_labels_extractor_omits_missing_fields()
    test_intake_runs_pipeline_and_grounds()
    test_intake_with_contradiction_goes_to_review()
    test_intake_validation_errors()
    test_request_info_then_resubmit_reruns_pipeline()
    test_evaluation_gate()
    print("ALL INTAKE/EVAL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
