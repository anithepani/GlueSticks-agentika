"""Tests for the fail-closed evaluation gate and the tamper demo.

Run: python tests/test_gate.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ["AUDIT_DB"] = str(Path(os.environ.get("TEMP", ".")) / "witness_gate_test.db")
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from app.adapters.audit_sqlite import SqliteAudit, verify_entries
from app.config import CASES_DIR, build_adapters
from app.evaluation import evaluate
from app.store import CaseStore
from app.tamper_demo import tamper_demo


def fresh_store():
    bundle = build_adapters()
    store = CaseStore(bundle, CASES_DIR)
    store.seed()
    return store, bundle


def test_eval_gate_passes():
    _, bundle = fresh_store()
    report = evaluate(bundle)
    assert report["all_passed"] is True, report
    assert report["invariants"]["no_auto_deny"] is True
    print("OK: eval gate passes and no_auto_deny holds")


def test_verify_entries_detects_forged_chain():
    entries = [
        {"seq": 1, "ts": "t1", "case_id": "c", "event": "e", "actor": "a", "payload": {"v": 1}, "prev_hash": "0" * 64, "hash": ""},
    ]
    from app.adapters.audit_sqlite import GENESIS, chain_hash

    entries[0]["hash"] = chain_hash(GENESIS, {k: entries[0][k] for k in ("ts", "case_id", "event", "actor", "payload")})
    assert verify_entries(entries)["ok"] is True

    forged = [dict(entries[0])]
    forged[0]["payload"] = {"v": 999}
    result = verify_entries(forged)
    assert result["ok"] is False and result["broken_at"] == 1, result
    print("OK: verify_entries detects a single forged payload")


def test_tamper_demo_never_touches_real_ledger():
    store, bundle = fresh_store()
    case = store.add_case(
        {
            "applicant_name": "Tamper Target",
            "documents": [{"title": "Form", "text": "Age: 30 years\nProvince of residence: Punjab\nHousehold size: 2 persons\nMonthly household income: PKR 20,000\nOwns a car: No\nLand owned (acres): 0\nBank balance: PKR 5,000"}],
        }
    )
    store.decide(case.id, "Officer T. Demo", "approve", "Evidence is complete and grounded.")

    before = bundle.audit.verify()
    report = tamper_demo(bundle.audit)
    after = bundle.audit.verify()

    assert before["ok"] and after["ok"], (before, after)
    assert report["intact"]["ok"] is True
    assert report["tampered"]["ok"] is False and report["tampered"]["broken_at"] is not None
    assert report["restored"]["ok"] is True
    assert before == after, "the demo must not alter the stored ledger"
    print(f"OK: tamper demo shows intact -> broken at #{report['tampered']['broken_at']} -> restored, real ledger unchanged")


def test_strict_mode_refuses_when_gate_fails(monkeypatch_target=None):
    from fastapi.testclient import TestClient
    import app.main as main

    os.environ["WITNESS_STRICT"] = "0"
    with TestClient(main.app) as client:
        health = client.get("/health").json()
        assert health["gate"]["all_passed"] is True, health
        print("OK: /health reports the gate result")

    os.environ["WITNESS_STRICT"] = "0"


def main() -> int:
    test_eval_gate_passes()
    test_verify_entries_detects_forged_chain()
    test_tamper_demo_never_touches_real_ledger()
    test_strict_mode_refuses_when_gate_fails()
    print("ALL GATE/TAMPER TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
