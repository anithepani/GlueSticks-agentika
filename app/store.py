"""In-memory case store with idempotent seeding and the human decision gate."""

from __future__ import annotations

import os
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


class CaseStore:
    def __init__(self, bundle: AdapterBundle, cases_dir: Path) -> None:
        self._bundle = bundle
        self._dir = Path(cases_dir)
        self._cases: dict[str, Case] = {}
        self._source = "unseeded"
        self._diagnostics: dict = {}

    def seed(self) -> int:
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
        return {"seed_source": self._source, "cases_loaded": len(self._cases), **self._diagnostics}

    def reseed(self) -> int:
        self._cases.clear()
        return self.seed()

    def add_case(self, payload: dict) -> Case:
        if len(self._cases) >= MAX_INTAKE_CASES:
            raise ValueError(f"intake limit reached ({MAX_INTAKE_CASES} cases)")
        packet = self._intake_packet(payload)
        extractor = intake_extractor()
        case = run_pipeline(packet, self._bundle, extractor=extractor)
        self._cases[case.id] = case
        case.log("intake_submitted", f"case created via API with {len(case.documents)} document(s)")
        self._bundle.audit.append(
            case.id,
            "intake",
            "officer",
            {
                "applicant_name": case.applicant_name,
                "documents": len(case.documents),
                "extractor": extractor.name,
            },
        )
        self._record_pipeline(case)
        return case

    def resubmit(self, case_id: str, documents: list[dict]) -> Case:
        case = self._cases.get(case_id)
        if case is None:
            raise KeyError(case_id)
        if case.status != STATUS_INFO_REQUESTED:
            raise ValueError(f"case in status {case.status} is not awaiting information")
        cleaned = self._clean_documents(documents)
        if not cleaned:
            raise ValueError("at least one document with text is required")

        existing = [{"doc_id": d.doc_id, "title": d.title, "text": d.text} for d in case.documents]
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
        case.documents = updated.documents
        case.facts = updated.facts
        case.rules = updated.rules
        case.verification = updated.verification
        case.recommendation = updated.recommendation
        case.status = updated.status
        case.decision = None
        case.touch()
        case.log("resubmit", f"{len(cleaned)} new document(s); pipeline re-run -> {case.status}")
        self._bundle.audit.append(
            case.id,
            "resubmit",
            "officer",
            {
                "documents": len(cleaned),
                "status": case.status,
                "verification": case.verification.status,
                "outcome": case.recommendation.outcome,
            },
        )
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
            text = str((raw or {}).get("text", "")).strip()
            if not text:
                continue
            cleaned.append(
                {
                    "doc_id": str((raw or {}).get("doc_id") or f"d{index + 1}"),
                    "title": str((raw or {}).get("title") or f"Document {index + 1}"),
                    "text": text,
                }
            )
        return cleaned

    def _next_intake_id(self) -> str:
        used = set(self._cases)
        serial = 1
        while f"INTK-{serial:04d}" in used:
            serial += 1
        return f"INTK-{serial:04d}"

    def _record_pipeline(self, case: Case) -> None:
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

    def list(self) -> list[Case]:
        return [self._cases[case_id] for case_id in sorted(self._cases)]

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def summaries(self) -> list[dict]:
        return [
            {
                "id": case.id,
                "applicant_name": case.applicant_name,
                "province": case.province,
                "status": case.status,
                "outcome": case.recommendation.outcome if case.recommendation else None,
                "verification": case.verification.status if case.verification else None,
                "decision": case.decision.action if case.decision else None,
            }
            for case in self.list()
        ]

    def decide(self, case_id: str, officer: str, action: str, reason: str) -> Case:
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

        case.decision = Decision(officer=officer, action=action, reason=reason, decided_at=_now())
        case.status = FINAL_BY_ACTION[action]
        case.touch()
        case.log("human_decision", f"{action} by {officer}")
        self._bundle.audit.append(
            case.id,
            "human_decision",
            officer,
            {
                "action": action,
                "reason": reason,
                "status": case.status,
                "outcome": case.recommendation.outcome if case.recommendation else None,
                "verification": case.verification.status if case.verification else None,
            },
        )
        return case

    def stats(self) -> dict:
        counters: dict[str, int] = {}
        for case in self._cases.values():
            counters[case.status] = counters.get(case.status, 0) + 1
        return {
            "total": len(self._cases),
            "by_status": counters,
            "decided": sum(1 for c in self._cases.values() if c.decision is not None),
        }


def _now() -> str:
    from app.models import now_iso

    return now_iso()


def is_denial(action: str) -> bool:
    return action == ACTION_DENY


def is_request(action: str) -> bool:
    return action == ACTION_REQUEST_INFO
