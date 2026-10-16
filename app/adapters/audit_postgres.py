"""Postgres-backed audit ledger with the same hash-chain semantics as SQLite.

psycopg is imported lazily so the app (and its tests) run without it installed;
only an actual Postgres deployment needs the driver. The DSN is taken from the
service's linked database via DATABASE_URL / POSTGRES_URL, or from the standard
PG* variables libpq reads.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.adapters.audit_sqlite import GENESIS, body_of, canonical, chain_hash, verify_entries
from app.models import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    seq BIGSERIAL PRIMARY KEY,
    ts TEXT NOT NULL,
    case_id TEXT,
    event TEXT NOT NULL,
    actor TEXT,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
)
"""

DSN_ENV_VARS = ("DATABASE_URL", "POSTGRES_URL", "POSTGRESQL_URL", "AF_DATABASE_URL")
LOCK_KEY = 848302  # arbitrary constant; serialises appends across replicas


def dsn() -> str:
    for name in DSN_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _connect():
    import psycopg  # lazy: only needed when Postgres is actually used

    return psycopg.connect(dsn())


class PostgresAudit:
    name = "postgres"

    def __init__(self, connect=_connect, create: bool = True) -> None:
        self._connect = connect
        self.path = dsn() or "postgres"
        if create:
            self._init()

    def _init(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)

    def append(self, case_id: str, event: str, actor: str | None, payload: dict) -> dict:
        body = {"ts": now_iso(), "case_id": case_id, "event": event, "actor": actor, "payload": payload}
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
                cur.execute("SELECT hash FROM entries ORDER BY seq DESC LIMIT 1")
                row = cur.fetchone()
                prev = row[0] if row else GENESIS
                digest = chain_hash(prev, body)
                cur.execute(
                    "INSERT INTO entries (ts, case_id, event, actor, payload, prev_hash, hash)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING seq",
                    (body["ts"], case_id, event, actor, canonical(payload), prev, digest),
                )
                seq = cur.fetchone()[0]
            conn.commit()
        entry = dict(body)
        entry["seq"] = seq
        entry["prev_hash"] = prev
        entry["hash"] = digest
        return entry

    def entries(self, case_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if case_id:
                    cur.execute(
                        "SELECT seq, ts, case_id, event, actor, payload, prev_hash, hash"
                        " FROM entries WHERE case_id = %s ORDER BY seq",
                        (case_id,),
                    )
                else:
                    cur.execute(
                        "SELECT seq, ts, case_id, event, actor, payload, prev_hash, hash"
                        " FROM entries ORDER BY seq"
                    )
                rows = cur.fetchall()
        return [
            {
                "seq": row[0],
                "ts": row[1],
                "case_id": row[2],
                "event": row[3],
                "actor": row[4],
                "payload": json.loads(row[5]),
                "prev_hash": row[6],
                "hash": row[7],
            }
            for row in rows
        ]

    def has_event(self, case_id: str, event: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM entries WHERE case_id = %s AND event = %s LIMIT 1",
                    (case_id, event),
                )
                return cur.fetchone() is not None

    def verify(self) -> dict:
        return verify_entries(self.entries())


def try_postgres() -> PostgresAudit | None:
    """Return a PostgresAudit if the driver is present and the DB is reachable."""
    try:
        return PostgresAudit()
    except Exception:
        return None
