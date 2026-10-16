"""Regression and end-to-end tests for confirmed defects and required scenarios.

Run: python tests/test_regressions.py
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ["AUDIT_DB"] = str(Path(os.environ.get("TEMP", ".")) / "witness_regression_test.db")
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.adapters import llm_client
from app.adapters.llm_client import LLMClient, LLMError, redact
from app.config import CASES_DIR, build_adapters
from app.store import CaseStore

FORM = (
    "Form B-1: Income Support Application\nName: Regression Test\nAge: 33 years\n"
    "Province of residence: Punjab\nHousehold size: 4 persons\n"
    "Monthly household income: PKR 22,000\nOwns a car: No\n"
    "Land owned (acres): 0\nBank balance: PKR 4,000"
)


def fresh_store(db_name: str = "regression"):
    path = Path(os.environ.get("TEMP", ".")) / f"witness_{db_name}_{os.getpid()}.db"
    try:
        path.unlink()
    except OSError:
        pass
    os.environ["AUDIT_DB"] = str(path)
    bundle = build_adapters()
    store = CaseStore(bundle, CASES_DIR)
    store.seed()
    return store, bundle


def test_concurrent_decision_is_serialized():
    store, bundle = fresh_store("conc")
    case = store.add_case({"applicant_name": "Race", "documents": [{"title": "Form", "text": FORM}]})
    results = []
    barrier = threading.Barrier(8)

    def worker(index):
        barrier.wait()
        try:
            store.decide(case.id, f"Officer {index}", "approve", "Concurrent approval attempt.")
            results.append("ok")
        except ValueError as exc:
            results.append(f"rejected:{exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count("ok") == 1, results
    assert sum(1 for r in results if r.startswith("rejected")) == 7, results
    decisions = [e for e in bundle.audit.entries(case.id) if e["event"] == "human_decision"]
    assert len(decisions) == 1, decisions
    assert bundle.audit.verify()["ok"] is True
    print("OK: concurrent decisions -> exactly one wins, one audit entry, chain intact")


def test_intake_id_does_not_collide_after_reseed():
    store, bundle = fresh_store("ids")
    first = store.add_case({"applicant_name": "First", "documents": [{"title": "Form", "text": FORM}]})
    assert first.id == "INTK-0001", first.id
    store.reseed()
    second = store.add_case({"applicant_name": "Second", "documents": [{"title": "Form", "text": FORM}]})
    assert second.id != first.id, (first.id, second.id)
    assert bundle.audit.has_event(second.id, "pipeline_run"), "new case's pipeline_run must be recorded"
    events = [e["event"] for e in bundle.audit.entries(second.id)]
    assert "intake" in events and "pipeline_run" in events, events
    print(f"OK: intake ids stay unique across reseed ({first.id} then {second.id}) with correct audit linkage")


def test_llm_key_never_leaks():
    client = LLMClient("gemini", "gemini-1.5-flash", "SECRET-KEY-123")
    assert "SECRET-KEY-123" not in repr(client), repr(client)
    assert "SECRET-KEY-123" not in redact("boom key=SECRET-KEY-123", client.api_key)
    assert "***" in redact("Authorization: Bearer SECRET-KEY-123", client.api_key)

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"candidates":[{"content":{"parts":[{"text":"{}"}]}}]}'

    original = llm_client.urllib.request.urlopen
    try:
        def capture(request, timeout=None):
            captured["url"] = request.full_url
            captured["headers"] = {k.lower(): v for k, v in request.header_items()}
            return FakeResponse()

        llm_client.urllib.request.urlopen = capture
        client._gemini("system", "user")
        assert "SECRET-KEY-123" not in captured["url"], captured["url"]
        assert captured["headers"].get("x-goog-api-key") == "SECRET-KEY-123"

        def boom(request, timeout=None):
            raise RuntimeError(f"connect failed for {request.full_url} key=SECRET-KEY-123")

        llm_client.urllib.request.urlopen = boom
        try:
            client._gemini("system", "user")
            raise AssertionError("expected LLMError")
        except LLMError as exc:
            assert "SECRET-KEY-123" not in str(exc), str(exc)
            assert "***" in str(exc), str(exc)
    finally:
        llm_client.urllib.request.urlopen = original
    print("OK: provider key is header-only, hidden from repr, and redacted from errors")


def test_decision_override_is_recorded():
    store, bundle = fresh_store("override")
    contradiction = (
        "Form B-1\nName: Dubious\nAge: 40 years\nProvince of residence: Punjab\n"
        "Household size: 3 persons\nMonthly household income: PKR 30,000\nOwns a car: No\n"
        "Land owned (acres): 0\nBank balance: PKR 5,000"
    )
    revised = "Income note\nMonthly household income (revised): PKR 95,000"
    case = store.add_case(
        {
            "applicant_name": "Dubious",
            "documents": [{"title": "Form", "text": contradiction}, {"title": "Note", "text": revised}],
        }
    )
    assert case.verification.status == "ABSTAIN", case.verification.status
    store.decide(case.id, "Officer Override", "approve", "Resolved the conflict with the applicant by phone.")
    payload = bundle.audit.entries(case.id)[-1]["payload"]
    assert payload["overrode_abstention"] is True, payload
    assert payload["verification"] == "ABSTAIN", payload
    print("OK: a human decision that overrides an abstention is recorded explicitly")


def test_api_error_and_status_paths():
    from fastapi.testclient import TestClient
    import app.main as main

    with TestClient(main.app) as client:
        assert client.get("/api/cases/NOPE/audit").status_code == 404
        assert client.post("/api/cases/NOPE/decision", json={"officer": "x", "action": "approve", "reason": "ok"}).status_code == 404
        assert client.post("/api/cases/NOPE/assign", json={"officer": "x"}).status_code == 404

        missing_reason = client.post(
            "/api/cases/CASE-2026-0001/decision",
            json={"officer": "Officer", "action": "approve", "reason": "  "},
        )
        assert missing_reason.status_code == 400, missing_reason.text

        bad_action = client.post(
            "/api/cases/CASE-2026-0001/decision",
            json={"officer": "Officer", "action": "delete", "reason": "nonsense action"},
        )
        assert bad_action.status_code == 400, bad_action.text

        malformed = client.post("/api/cases", json={"documents": [{"text": "x"}]})
        assert malformed.status_code in (400, 422), malformed.text

        info_flow = client.post(
            "/api/cases/CASE-2026-0002/decision",
            json={"officer": "Officer", "action": "request_info", "reason": "Need proof of income."},
        )
        assert info_flow.status_code == 200 and info_flow.json()["status"] == "INFO_REQUESTED"
        blocked = client.post(
            "/api/cases/CASE-2026-0002/decision",
            json={"officer": "Officer", "action": "approve", "reason": "trying again"},
        )
        assert blocked.status_code == 400, blocked.text

        verify = client.get("/api/audit/verify").json()
        assert verify["ok"] is True and verify.get("ledger"), verify
    print("OK: invalid transitions, duplicate decisions, malformed intake and unknown cases are rejected correctly")


def test_tamper_demo_on_empty_ledger():
    from app.adapters.audit_sqlite import SqliteAudit
    from app.tamper_demo import tamper_demo

    path = Path(os.environ.get("TEMP", ".")) / f"witness_empty_{os.getpid()}.db"
    try:
        path.unlink()
    except OSError:
        pass
    report = tamper_demo(SqliteAudit(str(path)))
    assert report["tampered"] is None and report["intact"]["ok"] is True, report
    print("OK: tamper demo handles an empty ledger without crashing")


def test_llm_transport_failure_falls_back_end_to_end():
    """Scenario 8 at the app level: a failing provider must degrade safely and leak nothing."""
    import app.main as main
    from app.adapters import llm_client
    from fastapi.testclient import TestClient

    os.environ["EXTRACTOR"] = "llm"
    os.environ["VERIFIER"] = "llm"
    os.environ["LLM_PROVIDER"] = "groq"
    os.environ["GROQ_API_KEY"] = "gsk_TESTKEY_LEAKCANARY"
    original = llm_client.urllib.request.urlopen

    def boom(request, timeout=None):
        raise RuntimeError(
            f"connection refused for {request.full_url} Authorization: Bearer gsk_TESTKEY_LEAKCANARY"
        )

    llm_client.urllib.request.urlopen = boom
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/cases",
                json={"applicant_name": "Outage Case", "documents": [{"title": "Form", "text": FORM}]},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["status"] == "VERIFIED", (body["status"], body["verification"]["reasons"])
            assert any(f["method"].endswith("(fallback)") for f in body["facts"]), body["facts"]
            assert "gsk_TESTKEY_LEAKCANARY" not in response.text, "key leaked into the response"
            adapters = client.get("/api/adapters").json()
            assert adapters["llm_configured"] is True, adapters
            assert "fallback" in adapters["extractor"], adapters
    finally:
        llm_client.urllib.request.urlopen = original
        os.environ.pop("GROQ_API_KEY", None)
        os.environ["EXTRACTOR"] = "fixture"
        os.environ["VERIFIER"] = "det"
    print("OK: provider outage degrades to the deterministic path with no key leakage")


def main() -> int:
    test_concurrent_decision_is_serialized()
    test_intake_id_does_not_collide_after_reseed()
    test_llm_key_never_leaks()
    test_decision_override_is_recorded()
    test_api_error_and_status_paths()
    test_llm_transport_failure_falls_back_end_to_end()
    test_tamper_demo_on_empty_ledger()
    print("ALL REGRESSION TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
