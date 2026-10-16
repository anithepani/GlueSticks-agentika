"""Demonstrate that the audit ledger is tamper-evident.

The real ledger is never modified: the demo tampers with an in-memory copy,
shows the chain break, then re-verifies the untouched ledger.
"""

from __future__ import annotations

from app.adapters.audit_sqlite import verify_entries


def tamper_demo(audit) -> dict:
    entries = audit.entries()
    intact = audit.verify()
    if not entries:
        return {"intact": intact, "tampered": None, "restored": intact, "target_seq": None}

    target = next((entry for entry in entries if entry["event"] == "human_decision"), entries[0])
    tampered_copy = [dict(entry) for entry in entries]
    for index, entry in enumerate(tampered_copy):
        if entry["seq"] == target["seq"]:
            forged = dict(entry)
            forged["payload"] = dict(entry.get("payload") or {}, tampered=True, forged_reason="inline-tamper")
            tampered_copy[index] = forged
            break

    tampered = verify_entries(tampered_copy)
    restored = audit.verify()
    return {
        "intact": intact,
        "tampered": tampered,
        "restored": restored,
        "target_seq": target["seq"],
    }
