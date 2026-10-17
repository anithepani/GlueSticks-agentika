"""Assignment, SLA/aging and observability tests.

Run: python tests/test_ops.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ["AUDIT_DB"] = str(Path(os.environ.get("TEMP", ".")) / "witness_ops_test.db")
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.config import CASES_DIR, build_adapters
from app.store import CaseStore, SLA_HOURS, age_minutes, sla_breached

FORM = (
    "Form B-1: Income Support Application\nName: Ops Test\nAge: 33 years\n"
    "Province of residence: Punjab\nHousehold size: 4 persons\n"
    "Monthly household income: PKR 22,000\nOwns a car: No\n"
    "Land owned (acres): 0\nBank balance: PKR 4,000"
)


def fresh_store():
    bundle = build_adapters()
    store = CaseStore(bundle, CASES_DIR)
    store.seed()
    return store, bundle


def test_assign_records_audit_and_summary():
    store, bundle = fresh_store()
    case = store.add_case({"applicant_name": "Ops Test", "documents": [{"title": "Form", "text": FORM}]})
    assert case.status == "VERIFIED", case.status
    assert case.assignee is None

    store.assign(case.id, "Officer N. Assign")
    assert store.get(case.id).assignee == "Officer N. Assign"

    summary = next(s for s in store.summaries() if s["id"] == case.id)
    assert summary["assignee"] == "Officer N. Assign", summary
    assert "age_minutes" in summary and "sla_breached" in summary

    events = [e["event"] for e in bundle.audit.entries(case.id)]
    assert "assigned" in events, events
    assert bundle.audit.verify()["ok"] is True

    try:
        store.assign(case.id, "   ")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "officer" in str(exc)
    print("OK: assignment is validated, audited and surfaced in the queue summary")


def test_sla_breach_detection():
    store, _ = fresh_store()
    case = store.add_case({"applicant_name": "Slow Case", "documents": [{"title": "Form", "text": FORM}]})
    assert sla_breached(case) is False
    assert age_minutes(case) < 1

    case.received_at = (datetime.now(timezone.utc) - timedelta(hours=SLA_HOURS + 2)).isoformat()
    assert sla_breached(case) is True, SLA_HOURS
    assert age_minutes(case) > SLA_HOURS * 60

    stats = store.stats()
    assert stats["sla_breached"] >= 1, stats
    assert stats["unassigned_open"] >= 1, stats
    assert stats["sla_hours"] == SLA_HOURS
    print(f"OK: aging computed, SLA breach detected (threshold {SLA_HOURS}h)")


def test_decided_case_never_breaches():
    store, _ = fresh_store()
    case = store.add_case({"applicant_name": "Decided", "documents": [{"title": "Form", "text": FORM}]})
    store.decide(case.id, "Officer A", "approve", "Complete and grounded.")
    case.received_at = (datetime.now(timezone.utc) - timedelta(hours=SLA_HOURS + 50)).isoformat()
    assert sla_breached(case) is False, "closed cases must not count as SLA breaches"
    print("OK: closed cases are excluded from SLA breaches")


def test_metrics_and_request_id():
    from fastapi.testclient import TestClient
    import app.main as main

    with TestClient(main.app) as client:
        response = client.get("/health")
        assert response.headers.get("x-request-id"), dict(response.headers)
        client.get("/api/cases")
        client.get("/")
        metrics = client.get("/api/metrics").json()
        assert metrics["requests_total"] >= 3, metrics
        assert metrics["by_status"].get("200", 0) >= 3, metrics
        assert metrics["gate"]["all_passed"] is True, metrics
        assert metrics["cases"]["total"] == 5
        latency = metrics["latency_ms"]
        assert latency["samples"] >= 3 and latency["p50"] >= 0 and latency["p95"] >= latency["p50"], metrics
        print(f"OK: metrics + request IDs work - {metrics['requests_total']} requests, by_status {metrics['by_status']}, "
              f"p50={latency['p50']}ms p95={latency['p95']}ms")


def main() -> int:
    test_assign_records_audit_and_summary()
    test_sla_breach_detection()
    test_decided_case_never_breaches()
    test_metrics_and_request_id()
    print("ALL OPS TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
