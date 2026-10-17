"""In-memory case store with idempotent seeding and the human decision gate."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import AdapterBundle, intake_extractor
from app.models import (
    ACTION_DENY,
    ACTION_REQUEST_INFO,
    ACTIONS,
    DECIDABLE_STATUSES,
    FINAL_BY_ACTION,
    STATUS_INFO_REQUESTED,
    Decision,
    Case,
)
from app.pipeline import run_pipeline
from app.seed_cases import load_packets

MAX_INTAKE_CASES = int(os.getenv("WITNESS_MAX_INTAKE", "50"))
MAX_PDF_B64 = int(os.getenv("WITNESS_MAX_PDF_B64", "4000000"))
SLA_HOURS = float(os.getenv("WITNESS_SLA_HOURS", "24"))
OPEN_STATUSES = ("INTAKE", "VERIFIED", "NEEDS_REVIEW", "INFO_REQUESTED")


class AuditWriteError(RuntimeError):
    """Raised when a state change could not be durably recorded in the audit ledger.

    Callers must treat this as "not recorded": the in-memory state is left unchanged
    so a decision never appears to have succeeded without an audit entry.
    """


def age_minutes(case: Case, now: datetime | None = None) -> float:
    try:
        received = datetime.fromisoformat(case.received_at)
    except ValueError:
        return 0.0
    reference = now or datetime.now(timezone.utc)
    return max(0.0, (reference - received).total_seconds() / 60.0)


def sla_breached(case: Case, now: datetime | None = None) -> bool:
    if case.status not in ("VERIFIED", "NEEDS_REVIEW", "INFO_REQUESTED"):
        return False
    return age_minutes(case, now) > SLA_HOURS * 60.0


class CaseStore:
    def __init__(self, bundle: AdapterBundle, cases_dir: Path) -> None:
        self._bundle = bundle
        self._dir = Path(cases_dir)
        self._cases: dict[str, Case] = {}
        self._source = "unseeded"
        self._diagnostics: dict = {}
        self._lock = threading.RLock()

    def seed(self) -> int:
        with self._lock:
            return self._seed_locked()

    def _seed_locked(self) -> int:
        packets, source, diagnostics = load_packets(self._dir)
        self._source = source
        self._diagnostics = diagnostics
        created = 0
        for packet in packets:
            case_id = str(packet["id"])
            if case_id in self._cases:
                continue
            case = run_pipeline(packet, self._bundle)
            self._cases[case_id] = case
            self._record_pipeline(case)
            created += 1
        return created

    def diag(self) -> dict:
        with self._lock:
            return {"seed_source": self._source, "cases_loaded": len(self._cases), **self._diagnostics}

    def reseed(self) -> int:
        with self._lock:
            self._cases.clear()
            return self._seed_locked()

    def add_case(self, payload: dict) -> Case:
        with self._lock:
            if len(self._cases) >= MAX_INTAKE_CASES:
                raise ValueError(f"intake limit reached ({MAX_INTAKE_CASES} cases)")
            packet = self._intake_packet(payload)
            extractor = intake_extractor()
            case = run_pipeline(packet, self._bundle, extractor=extractor)
            # Durable first: the case is only registered if its intake is audited.
            self._append_or_raise(
                case.id,
                "intake",
                "officer",
                {
                    "applicant_name": case.applicant_name,
                    "documents": len(case.documents),
                    "extractor": extractor.name,
                },
            )
            self._cases[case.id] = case
            case.log("intake_submitted", f"case created via API with {len(case.documents)} document(s)")
            self._record_pipeline(case)
            return case

    def resubmit(self, case_id: str, documents: list[dict]) -> Case:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                raise KeyError(case_id)
            if case.status != STATUS_INFO_REQUESTED:
                raise ValueError(f"case in status {case.status} is not awaiting information")
            cleaned = self._clean_documents(documents)
            if not cleaned:
                raise ValueError("at least one document with text is required")

            existing = [
                {"doc_id": d.doc_id, "title": d.title, "text": d.text}
                for d in case.documents
            ]
            for index, document in enumerate(cleaned):
                document["doc_id"] = f"d{len(existing) + index + 1}"

            packet = {
                "id": case.id,
                "applicant_name": case.applicant_name,
                "applicant_cnic": case.applicant_cnic,
                "province": case.province,
                "documents": existing + cleaned,
            }
            updated = run_pipeline(packet, self._bundle, extractor=intake_extractor())
            # Durable first: only reopen the case once the resubmission is recorded.
            self._append_or_raise(
                case.id,
                "resubmit",
                "officer",
                {
                    "documents": len(cleaned),
                    "status": updated.status,
                    "verification": updated.verification.status,
                    "outcome": updated.recommendation.outcome,
                },
            )
            case.documents = updated.documents
            case.facts = updated.facts
            case.rules = updated.rules
            case.verification = updated.verification
            case.recommendation = updated.recommendation
            case.status = updated.status
            case.decision = None
            case.touch()
            case.log("resubmit", f"{len(cleaned)} new document(s); pipeline re-run -> {case.status}")
            return case

    def _intake_packet(self, payload: dict) -> dict:
        name = str(payload.get("applicant_name", "")).strip()
        if not name:
            raise ValueError("applicant_name is required")
        documents = self._clean_documents(payload.get("documents", []))
        if not documents:
            raise ValueError("at least one document with text is required")
        return {
            "id": self._next_intake_id(),
            "applicant_name": name,
            "applicant_cnic": str(payload.get("applicant_cnic", "")).strip(),
            "province": str(payload.get("province", "")).strip(),
            "documents": documents,
        }

    def _clean_documents(self, documents) -> list[dict]:
        cleaned: list[dict] = []
        for index, raw in enumerate(documents or []):
            raw = raw or {}
            text = str(raw.get("text", "")).strip()
            pdf = raw.get("pdf_base64")
            if not text and not pdf:
                continue
            entry = {
                "doc_id": str(raw.get("doc_id") or f"d{index + 1}"),
                "title": str(raw.get("title") or f"Document {index + 1}"),
                "text": text,
            }
            if pdf:
                if len(str(pdf)) > MAX_PDF_B64:
                    raise ValueError(f"document '{entry['title']}' exceeds the size limit")
                entry["pdf_base64"] = str(pdf)
            cleaned.append(entry)
        return cleaned

    def _next_intake_id(self) -> str:
        """A fresh intake id that cannot collide with any id already in the ledger.

        The in-memory cases are rebuilt on every start, but the audit ledger is not,
        so the counter must also account for ids the ledger already holds. Otherwise a
        new case could reuse an old id and its pipeline_run entry would be suppressed
        as a duplicate while prior history stayed attached to it.
        """
        used = set(self._cases)
        try:
            used |= self._bundle.audit.case_ids()
        except Exception:
            pass
        serial = 1
        while f"INTK-{serial:04d}" in used:
            serial += 1
        return f"INTK-{serial:04d}"

    def _append_or_raise(self, case_id: str, event: str, actor, payload: dict) -> dict:
        """Append an audit entry, converting any failure into AuditWriteError.

        Used for state-changing operations so the caller can guarantee that a change
        is only applied after it is durably recorded.
        """
        try:
            return self._bundle.audit.append(case_id, event, actor, payload)
        except Exception as exc:
            raise AuditWriteError(f"audit write failed for {case_id}/{event}: {exc}") from exc

    def _record_pipeline(self, case: Case) -> None:
        # Best-effort: the pipeline_run marker is informational. A failure here must
        # not stop the service from starting or a case from being created; the ledger
        # is still verified independently by /api/audit/verify.
        try:
            if self._bundle.audit.has_event(case.id, "pipeline_run"):
                return
            self._bundle.audit.append(
                case.id,
                "pipeline_run",
                "system",
                {
                    "status": case.status,
                    "outcome": case.recommendation.outcome,
                    "verification": case.verification.status,
                    "rules": {rule.rule_id: rule.status for rule in case.rules},
                },
            )
        except Exception:
            return

    def list(self) -> list[Case]:
        with self._lock:
            return [self._cases[case_id] for case_id in sorted(self._cases)]

    def get(self, case_id: str) -> Case | None:
        with self._lock:
            return self._cases.get(case_id)

    def summaries(self) -> list[dict]:
        with self._lock:
            cases = [self._cases[case_id] for case_id in sorted(self._cases)]
            return [
                {
                    "id": case.id,
                    "applicant_name": case.applicant_name,
                    "province": case.province,
                    "status": case.status,
                    "outcome": case.recommendation.outcome if case.recommendation else None,
                    "verification": case.verification.status if case.verification else None,
                    "decision": case.decision.action if case.decision else None,
                    "assignee": case.assignee,
                    "age_minutes": round(age_minutes(case), 1),
                    "sla_breached": sla_breached(case),
                }
                for case in cases
            ]

    def assign(self, case_id: str, officer: str) -> Case:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                raise KeyError(case_id)
            officer = (officer or "").strip()
            if not officer:
                raise ValueError("officer name is required")
            # Record first, mutate second: a failed write must not change state.
            self._append_or_raise(case.id, "assigned", officer, {"assignee": officer})
            case.assignee = officer
            case.assigned_at = _now()
            case.touch()
            case.log("assigned", f"assigned to {officer}")
            return case

    def decide(self, case_id: str, officer: str, action: str, reason: str) -> Case:
        with self._lock:
            case = self._cases.get(case_id)
            if case is None:
                raise KeyError(case_id)
            if action not in ACTIONS:
                raise ValueError(f"action must be one of {', '.join(ACTIONS)}")
            if case.status not in DECIDABLE_STATUSES:
                raise ValueError(f"case in status {case.status} cannot be decided")
            officer = (officer or "").strip()
            reason = (reason or "").strip()
            if not officer:
                raise ValueError("officer name is required")
            if len(reason) < 3:
                raise ValueError("a written reason is required")

            verification_status = case.verification.status if case.verification else None
            outcome = case.recommendation.outcome if case.recommendation else None
            new_status = FINAL_BY_ACTION[action]
            decided_at = _now()

            # Durability first: if the ledger write fails, the case is left untouched
            # and the request surfaces as "not recorded" instead of a phantom approval.
            self._append_or_raise(
                case.id,
                "human_decision",
                officer,
                {
                    "action": action,
                    "reason": reason,
                    "status": new_status,
                    "outcome": outcome,
                    "verification": verification_status,
                    "overrode_abstention": verification_status == "ABSTAIN",
                },
            )

            case.decision = Decision(officer=officer, action=action, reason=reason, decided_at=decided_at)
            case.status = new_status
            case.touch()
            case.log("human_decision", f"{action} by {officer}")
            return case

    def stats(self) -> dict:
        with self._lock:
            counters: dict[str, int] = {}
            for case in self._cases.values():
                counters[case.status] = counters.get(case.status, 0) + 1
            return {
                "total": len(self._cases),
                "by_status": counters,
                "decided": sum(1 for c in self._cases.values() if c.decision is not None),
                "unassigned_open": sum(
                    1 for c in self._cases.values() if c.status in OPEN_STATUSES and not c.assignee
                ),
                "sla_breached": sum(1 for c in self._cases.values() if sla_breached(c)),
                "sla_hours": SLA_HOURS,
            }


def _now() -> str:
    from app.models import now_iso

    return now_iso()


def is_denial(action: str) -> bool:
    return action == ACTION_DENY


def is_request(action: str) -> bool:
    return action == ACTION_REQUEST_INFO
