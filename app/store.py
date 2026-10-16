"""In-memory case store with idempotent seeding and the human decision gate."""

from __future__ import annotations

from pathlib import Path

from app.config import AdapterBundle
from app.models import (
    ACTION_DENY,
    ACTION_REQUEST_INFO,
    ACTIONS,
    DECIDABLE_STATUSES,
    FINAL_BY_ACTION,
    Decision,
    Case,
)
from app.pipeline import run_pipeline
from app.seed_cases import load_packets


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
