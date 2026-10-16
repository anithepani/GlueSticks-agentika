"""Case packet loading with an embedded fallback.

The JSON files under data/cases are the source of truth, but not every build
system copies a data directory into the image. If no case files are found, the
pipeline seeds from the embedded packets in app/embedded.py so the service is
never empty. tests/test_seed.py asserts the two stay in sync.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_DIR, ROOT
from app.embedded import DEFAULT_CASES


def candidate_dirs() -> list[Path]:
    candidates = [DATA_DIR, ROOT / "data", Path.cwd() / "data", Path.cwd().parent / "data"]
    unique: list[Path] = []
    for candidate in candidates:
        resolved = Path(candidate)
        if resolved not in unique:
            unique.append(resolved)
    return unique


def load_packets(data_dir: Path | None = None) -> tuple[list[dict], str, dict]:
    candidates = ([data_dir] if data_dir else []) + candidate_dirs()
    diagnostics: dict = {"candidates": []}
    for base in candidates:
        base = Path(base)
        cases_dir = base / "cases"
        files = sorted(cases_dir.glob("*.json")) if cases_dir.is_dir() else []
        diagnostics["candidates"].append(
            {"dir": str(cases_dir), "exists": cases_dir.is_dir(), "files": len(files)}
        )
        if files:
            packets = [json.loads(path.read_text(encoding="utf-8")) for path in files]
            return packets, f"files:{cases_dir}", diagnostics
    return DEFAULT_CASES, "embedded", diagnostics
