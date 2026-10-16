"""Append-only, hash-chained audit ledger backed by SQLite (stdlib only).

Every entry stores the hash of the previous entry, so editing or removing an entry
breaks the chain. verify() recomputes the whole chain and reports the first break.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from typing import Any

from app.models import now_iso

GENESIS = "0" * 64


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chain_hash(prev_hash: str, body: dict) -> str:
    return hashlib.sha256((prev_hash + canonical(body)).encode("utf-8")).hexdigest()


def body_of(entry: dict) -> dict:
    return {
        "ts": entry["ts"],
        "case_id": entry["case_id"],
        "event": entry["event"],
        "actor": entry["actor"],
        "payload": entry["payload"],
    }


def verify_entries(entries: list[dict]) -> dict:
    """Recompute a hash chain over entries and report the first break.

    Adapter-agnostic: works on any list of entry dicts, so it can also be used to
    audit a *copy* of the ledger without touching stored data.
    """
    prev = GENESIS
    for entry in entries:
        expected = chain_hash(prev, body_of(entry))
        if entry.get("prev_hash") != prev or expected != entry.get("hash"):
            return {"ok": False, "checked": entry.get("seq"), "total": len(entries), "broken_at": entry.get("seq")}
        prev = entry["hash"]
    return {"ok": True, "checked": len(entries), "total": len(entries), "head": prev}


class SqliteAudit:
    name = "sqlite"

    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
        except sqlite3.Error:
            pass
        return conn

    def _init(self) -> None:
        with self._lock, self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.Error:
                pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    case_id TEXT,
                    event TEXT NOT NULL,
                    actor TEXT,
                    payload TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                )
                """
            )

    def append(self, case_id: str, event: str, actor: str | None, payload: dict) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT hash FROM entries ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row["hash"] if row else GENESIS
            body = {
                "ts": now_iso(),
                "case_id": case_id,
                "event": event,
                "actor": actor,
                "payload": payload,
            }
            digest = chain_hash(prev, body)
            cursor = conn.execute(
                "INSERT INTO entries (ts, case_id, event, actor, payload, prev_hash, hash)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (body["ts"], case_id, event, actor, canonical(payload), prev, digest),
            )
            entry = dict(body)
            entry["seq"] = cursor.lastrowid
            entry["prev_hash"] = prev
            entry["hash"] = digest
            return entry

    def entries(self, case_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if case_id:
                rows = conn.execute(
                    "SELECT * FROM entries WHERE case_id = ? ORDER BY seq", (case_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM entries ORDER BY seq").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    def has_event(self, case_id: str, event: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM entries WHERE case_id = ? AND event = ? LIMIT 1",
                (case_id, event),
            ).fetchone()
        return row is not None

    def case_ids(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT case_id FROM entries WHERE case_id IS NOT NULL").fetchall()
        return {row[0] for row in rows}

    def verify(self) -> dict:
        result = verify_entries(self.entries())
        result["ledger"] = self.name
        return result
