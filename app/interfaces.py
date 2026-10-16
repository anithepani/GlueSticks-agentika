"""Swappable ports behind environment flags. Implementations live in app.adapters."""

from __future__ import annotations

from typing import Protocol

from app.models import Document, Fact, Recommendation, RuleResult, Verification


class Reader(Protocol):
    name: str

    def read(self, packet: dict) -> list[Document]: ...


class Extractor(Protocol):
    name: str

    def extract(self, documents: list[Document], packet: dict) -> list[Fact]: ...


class RulesEngine(Protocol):
    name: str

    def evaluate(self, facts: list[Fact]) -> list[RuleResult]: ...


class Verifier(Protocol):
    name: str

    def verify(
        self,
        documents: list[Document],
        facts: list[Fact],
        rules: list[RuleResult],
        recommendation: Recommendation,
    ) -> Verification: ...


class AuditLog(Protocol):
    name: str

    def append(self, case_id: str, event: str, actor: str | None, payload: dict) -> dict: ...

    def entries(self, case_id: str | None = None) -> list[dict]: ...

    def has_event(self, case_id: str, event: str) -> bool: ...

    def case_ids(self) -> set[str]: ...

    def verify(self) -> dict: ...
