"""Typed contracts shared by every stage of the Witness pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

STATUS_INTAKE = "INTAKE"
STATUS_VERIFIED = "VERIFIED"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_APPROVED = "APPROVED"
STATUS_DENIED = "DENIED"
STATUS_INFO_REQUESTED = "INFO_REQUESTED"

RULE_PASS = "PASS"
RULE_FAIL = "FAIL"
RULE_UNKNOWN = "UNKNOWN"

VERIFY_OK = "OK"
VERIFY_ABSTAIN = "ABSTAIN"

OUTCOME_ELIGIBLE = "ELIGIBLE"
OUTCOME_NEEDS_REVIEW = "NEEDS_REVIEW"

ACTION_APPROVE = "approve"
ACTION_DENY = "deny"
ACTION_REQUEST_INFO = "request_info"

ACTIONS = (ACTION_APPROVE, ACTION_DENY, ACTION_REQUEST_INFO)

FINAL_BY_ACTION = {
    ACTION_APPROVE: STATUS_APPROVED,
    ACTION_DENY: STATUS_DENIED,
    ACTION_REQUEST_INFO: STATUS_INFO_REQUESTED,
}

DECIDABLE_STATUSES = (STATUS_VERIFIED, STATUS_NEEDS_REVIEW)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Citation:
    doc_id: str
    quote: str
    start: int
    end: int
    grounded: bool = True


@dataclass
class Fact:
    key: str
    label: str
    value: Any
    citation: Citation | None = None
    method: str = "fixture"


@dataclass
class Document:
    doc_id: str
    title: str
    text: str


@dataclass
class RuleResult:
    rule_id: str
    title: str
    status: str
    detail: str
    observed: Any = None
    expected: Any = None


@dataclass
class Verification:
    status: str
    checks: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    outcome: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class Decision:
    officer: str
    action: str
    reason: str
    decided_at: str


@dataclass
class Case:
    id: str
    applicant_name: str
    applicant_cnic: str
    province: str
    status: str = STATUS_INTAKE
    documents: list[Document] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    rules: list[RuleResult] = field(default_factory=list)
    verification: Verification | None = None
    recommendation: Recommendation | None = None
    decision: Decision | None = None
    history: list[dict] = field(default_factory=list)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    def touch(self) -> None:
        self.updated_at = now_iso()

    def log(self, event: str, detail: str | None = None) -> None:
        entry = {"at": now_iso(), "event": event}
        if detail:
            entry["detail"] = detail
        self.history.append(entry)

    def facts_by_key(self) -> dict[str, list[Fact]]:
        grouped: dict[str, list[Fact]] = {}
        for fact in self.facts:
            grouped.setdefault(fact.key, []).append(fact)
        return grouped
