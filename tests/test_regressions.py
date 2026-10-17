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


def test_audit_persistence_across_restart():
    """Verify that audit records and hash chain head survive process restart intact."""
    from app.adapters.audit_sqlite import SqliteAudit

    db_file = Path(os.environ.get("TEMP", ".")) / f"witness_persist_test_{os.getpid()}.db"
    try:
        db_file.unlink()
    except OSError:
        pass

    try:
        # Process 1: write initial entries
        ledger1 = SqliteAudit(str(db_file))
        e1 = ledger1.append("CASE-TEST-001", "intake", "officer1", {"test": "data1"})
        e2 = ledger1.append("CASE-TEST-001", "human_decision", "officer1", {"action": "approve"})
        v1 = ledger1.verify()
        assert v1["ok"] is True and v1["total"] == 2
        head1 = v1["head"]

        # Process 2 (simulated restart): reopen the same file
        ledger2 = SqliteAudit(str(db_file))
        v2 = ledger2.verify()
        assert v2["ok"] is True and v2["total"] == 2
        assert v2["head"] == head1, "Chain head drifted across process restart"
        entries = ledger2.entries("CASE-TEST-001")
        assert len(entries) == 2
        assert entries[0]["hash"] == e1["hash"]
        assert entries[1]["hash"] == e2["hash"]

        # Append new entry onto the existing chain
        e3 = ledger2.append("CASE-TEST-002", "intake", "officer2", {"test": "data2"})
        assert e3["prev_hash"] == head1
        v3 = ledger2.verify()
        assert v3["ok"] is True and v3["total"] == 3
        assert v3["head"] == e3["hash"]
    finally:
        try:
            db_file.unlink()
        except OSError:
            pass
    print("OK: audit records and hash chain persist across process restart with matching head")


def test_resilient_audit_runtime_outage_fallback():
    """Verify that a primary database outage triggers graceful fallback and a visible degraded status."""
    from app.adapters.audit_sqlite import SqliteAudit
    from app.adapters.resilient import ResilientAudit
    from app.config import AdapterBundle, describe_adapters

    db_primary = Path(os.environ.get("TEMP", ".")) / f"witness_prim_{os.getpid()}.db"
    db_fallback = Path(os.environ.get("TEMP", ".")) / f"witness_fall_{os.getpid()}.db"
    for f in (db_primary, db_fallback):
        try:
            f.unlink()
        except OSError:
            pass

    try:
        prim = SqliteAudit(str(db_primary))
        prim.name = "postgres"  # simulate postgres primary
        fall = SqliteAudit(str(db_fallback))

        resilient = ResilientAudit(prim, fall)
        bundle = build_adapters()
        bundle.audit = resilient

        # Before failure: not degraded
        os.environ["AUDIT"] = "postgres"
        desc0 = describe_adapters(bundle)
        assert desc0["audit_requested"] == "postgres"
        assert desc0["audit_degraded"] is False
        assert desc0["audit_runtime_degraded"] is False

        # First append succeeds on primary
        resilient.append("C1", "event1", "system", {"k": 1})
        assert prim.entries("C1")
        assert not fall.entries("C1")

        # Simulate primary outage (e.g. database network disconnects)
        def broken_append(*args, **kwargs):
            raise ConnectionError("connection to postgres closed")

        prim.append = broken_append

        # Append during outage: falls back to fallback without crashing
        e2 = resilient.append("C1", "event2", "officer", {"k": 2})
        assert resilient.degraded is True
        assert fall.entries("C1"), "Event was not written to fallback ledger"

        # Verification reports fallback ledger and chain remains valid
        ver = resilient.verify()
        assert ver["ok"] is True
        assert ver["ledger"] == "sqlite"

        # describe_adapters reflects degradation visibly
        desc1 = describe_adapters(bundle)
        assert desc1["audit_degraded"] is True
        assert desc1["audit_runtime_degraded"] is True
        assert "fell back" in desc1["audit_note"]
    finally:
        os.environ.pop("AUDIT", None)
        for f in (db_primary, db_fallback):
            try:
                f.unlink()
            except OSError:
                pass
    print("OK: database outage triggers documented fallback and a visible degraded status")


def test_sensitive_values_never_exposed_in_api():
    """Verify that credentials and connection strings never leak in endpoints or error outputs."""
    import app.main as main
    from fastapi.testclient import TestClient

    secret_key = "gsk_SUPER_SECRET_TOKEN_DO_NOT_LEAK"
    secret_db = "postgresql://user:SUPER_SECRET_PW@db.internal:5432/appdb"
    os.environ["GROQ_API_KEY"] = secret_key
    os.environ["DATABASE_URL"] = secret_db

    try:
        with TestClient(main.app) as client:
            endpoints = [
                "/health",
                "/api/info",
                "/api/adapters",
                "/api/cases",
                "/api/policy",
                "/api/eval",
                "/api/metrics",
                "/api/audit/verify",
                "/api/diag",
            ]
            for ep in endpoints:
                resp = client.get(ep)
                assert resp.status_code == 200, (ep, resp.status_code)
                assert secret_key not in resp.text, f"Key leaked in {ep}"
                assert "SUPER_SECRET_PW" not in resp.text, f"DB password leaked in {ep}"

            # Invalid case ID gives 404 with no secret leaks
            err_resp = client.get("/api/cases/INVALID-CASE-ID/audit")
            assert err_resp.status_code == 404
            assert secret_key not in err_resp.text
            assert "SUPER_SECRET_PW" not in err_resp.text
    finally:
        os.environ.pop("GROQ_API_KEY", None)
        os.environ.pop("DATABASE_URL", None)
    print("OK: sensitive keys and connection passwords never appear in API responses")


def test_decision_not_applied_when_audit_write_fails():
    """A decision must never appear to succeed if its audit entry was not recorded."""
    store, bundle = fresh_store("auditfail")
    case = store.add_case({"applicant_name": "Audit Fail", "documents": [{"title": "Form", "text": FORM}]})

    from app.config import AdapterBundle
    from app.store import AuditWriteError

    class RaisingAudit:
        name = "sqlite"

        def append(self, *a, **k):
            raise RuntimeError("ledger unavailable")

        def entries(self, case_id=None):
            return []

        def has_event(self, *a, **k):
            return False

        def case_ids(self):
            return set()

        def verify(self):
            return {"ok": True, "checked": 0, "total": 0}

    store._bundle = AdapterBundle(
        reader=bundle.reader,
        extractor=bundle.extractor,
        rules=bundle.rules,
        verifier=bundle.verifier,
        audit=RaisingAudit(),
    )

    try:
        store.decide(case.id, "Officer A", "approve", "Attempting with a broken ledger.")
        raise AssertionError("expected AuditWriteError")
    except AuditWriteError:
        pass

    after = store.get(case.id)
    assert after.status == "VERIFIED", after.status
    assert after.decision is None, after.decision
    print("OK: failed audit write leaves the case undecided (no phantom approval)")


def test_decision_api_returns_503_when_audit_write_fails():
    from fastapi.testclient import TestClient
    import app.main as main
    from app.config import AdapterBundle

    class RaisingAudit:
        name = "sqlite"

        def append(self, *a, **k):
            raise RuntimeError("ledger unavailable")

        def entries(self, case_id=None):
            return []

        def has_event(self, *a, **k):
            return False

        def case_ids(self):
            return set()

        def verify(self):
            return {"ok": True, "checked": 0, "total": 0}

    with TestClient(main.app) as client:
        created = client.post(
            "/api/cases",
            json={"applicant_name": "Audit Failure API", "documents": [{"title": "Form", "text": FORM}]},
        )
        assert created.status_code == 200, created.text
        case_id = created.json()["id"]

        store = client.app.state.store
        original = store._bundle
        store._bundle = AdapterBundle(
            reader=original.reader,
            extractor=original.extractor,
            rules=original.rules,
            verifier=original.verifier,
            audit=RaisingAudit(),
        )
        try:
            response = client.post(
                f"/api/cases/{case_id}/decision",
                json={"officer": "Officer A", "action": "approve", "reason": "Broken ledger attempt."},
            )
            assert response.status_code == 503, (response.status_code, response.text)
            assert store.get(case_id).decision is None, "case must not be approved without an audit entry"
        finally:
            store._bundle = original
    print("OK: decision endpoint returns 503 and does not approve when the audit write fails")


def main() -> int:
    test_concurrent_decision_is_serialized()
    test_intake_id_does_not_collide_after_reseed()
    test_llm_key_never_leaks()
    test_decision_override_is_recorded()
    test_api_error_and_status_paths()
    test_llm_transport_failure_falls_back_end_to_end()
    test_decision_not_applied_when_audit_write_fails()
    test_decision_api_returns_503_when_audit_write_fails()
    test_tamper_demo_on_empty_ledger()
    test_audit_persistence_across_restart()
    test_resilient_audit_runtime_outage_fallback()
    test_sensitive_values_never_exposed_in_api()
    print("ALL REGRESSION TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

