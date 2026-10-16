"""Lightweight observability: request IDs, JSON access logs, and counters.

No third-party dependency. Enough to make a live demo legible: every response
carries an `x-request-id`, every request emits one JSON log line, and /api/metrics
summarises traffic.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.time()
        self._total = 0
        self._by_status: dict[int, int] = defaultdict(int)
        self._by_path: dict[str, int] = defaultdict(int)
        self._total_ms = 0.0

    def record(self, path: str, status: int, ms: float) -> None:
        with self._lock:
            self._total += 1
            self._by_status[int(status)] += 1
            self._by_path[path] += 1
            self._total_ms += ms

    def reset(self) -> None:
        with self._lock:
            self._started = time.time()
            self._total = 0
            self._by_status = defaultdict(int)
            self._by_path = defaultdict(int)
            self._total_ms = 0.0

    def snapshot(self) -> dict:
        with self._lock:
            top = sorted(self._by_path.items(), key=lambda item: item[1], reverse=True)[:10]
            return {
                "uptime_seconds": round(time.time() - self._started, 1),
                "requests_total": self._total,
                "avg_ms": round(self._total_ms / self._total, 2) if self._total else 0.0,
                "by_status": {str(k): v for k, v in sorted(self._by_status.items())},
                "top_paths": [{"path": p, "count": c} for p, c in top],
            }


def log_json(payload: dict) -> None:
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception:
        pass
