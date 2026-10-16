"""Wires the swappable ports to concrete adapters based on environment flags."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.adapters import (
    DeterministicVerifier,
    FixtureExtractor,
    PmtRules,
    SqliteAudit,
    TextReader,
)
from app.interfaces import AuditLog, Extractor, Reader, RulesEngine, Verifier

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("WITNESS_DATA_DIR", str(ROOT / "data")))
CASES_DIR = DATA_DIR / "cases"
POLICY_DIR = DATA_DIR / "policy"

STAGE = int(os.getenv("WITNESS_STAGE", "1"))


@dataclass
class AdapterBundle:
    reader: Reader
    extractor: Extractor
    rules: RulesEngine
    verifier: Verifier
    audit: AuditLog


def _reader(name: str) -> Reader:
    if name == "text":
        return TextReader()
    raise ValueError(f"READER '{name}' is not implemented in this stage")


def _extractor(name: str) -> Extractor:
    if name == "fixture":
        return FixtureExtractor()
    raise ValueError(f"EXTRACTOR '{name}' is not implemented in this stage")


def _verifier(name: str) -> Verifier:
    if name == "det":
        return DeterministicVerifier()
    raise ValueError(f"VERIFIER '{name}' is not implemented in this stage")


def _audit(name: str) -> AuditLog:
    if name == "sqlite":
        return SqliteAudit(os.getenv("AUDIT_DB", str(DATA_DIR / "audit.db")))
    raise ValueError(f"AUDIT '{name}' is not implemented in this stage")


def build_adapters() -> AdapterBundle:
    return AdapterBundle(
        reader=_reader(os.getenv("READER", "text")),
        extractor=_extractor(os.getenv("EXTRACTOR", "fixture")),
        rules=PmtRules(),
        verifier=_verifier(os.getenv("VERIFIER", "det")),
        audit=_audit(os.getenv("AUDIT", "sqlite")),
    )
