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
from app.adapters.extractor_llm import LLMExtractor
from app.adapters.llm_client import build_llm_client
from app.adapters.resilient import ResilientExtractor, ResilientVerifier
from app.adapters.verifier_llm import LLMVerifier
from app.interfaces import AuditLog, Extractor, Reader, RulesEngine, Verifier

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("WITNESS_DATA_DIR", str(ROOT / "data")))
CASES_DIR = DATA_DIR / "cases"
POLICY_DIR = DATA_DIR / "policy"

STAGE = int(os.getenv("WITNESS_STAGE", "2"))


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
    if name == "llm":
        client = build_llm_client()
        if client is None:
            return FixtureExtractor()
        return ResilientExtractor(LLMExtractor(client), FixtureExtractor())
    raise ValueError(f"EXTRACTOR '{name}' is not implemented")


def _verifier(name: str) -> Verifier:
    if name == "det":
        return DeterministicVerifier()
    if name == "llm":
        client = build_llm_client()
        if client is None:
            return DeterministicVerifier()
        return ResilientVerifier(LLMVerifier(client), DeterministicVerifier())
    raise ValueError(f"VERIFIER '{name}' is not implemented")


def _audit(name: str) -> AuditLog:
    if name == "sqlite":
        return SqliteAudit(os.getenv("AUDIT_DB", str(DATA_DIR / "audit.db")))
    raise ValueError(f"AUDIT '{name}' is not implemented")


def build_adapters() -> AdapterBundle:
    return AdapterBundle(
        reader=_reader(os.getenv("READER", "text")),
        extractor=_extractor(os.getenv("EXTRACTOR", "fixture")),
        rules=PmtRules(),
        verifier=_verifier(os.getenv("VERIFIER", "det")),
        audit=_audit(os.getenv("AUDIT", "sqlite")),
    )


def describe_adapters(bundle: AdapterBundle) -> dict:
    client = build_llm_client()
    return {
        "reader": bundle.reader.name,
        "extractor": bundle.extractor.name,
        "rules": bundle.rules.name,
        "verifier": bundle.verifier.name,
        "audit": bundle.audit.name,
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        "llm_configured": client is not None,
        "llm_model": client.model if client else None,
    }
