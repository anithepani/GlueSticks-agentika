"""Guards that the embedded fallback cases match the JSON source of truth.

Run: python tests/test_seed.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from app.seed_cases import DEFAULT_CASES, load_packets
import app.seed_cases as seed_cases

CASES_DIR = REPO / "data" / "cases"


def main() -> int:
    files = sorted(CASES_DIR.glob("*.json"))
    assert files, "no case JSON files found"
    from_files = {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8")) for p in files}
    from_embedded = {case["id"]: case for case in DEFAULT_CASES}

    assert set(from_files) == set(from_embedded), (set(from_files) ^ set(from_embedded))
    for case_id, packet in from_files.items():
        assert packet == from_embedded[case_id], f"embedded case drifted from JSON: {case_id}"
    print(f"OK: {len(from_files)} embedded cases match data/cases/*.json")

    packets, source, diagnostics = load_packets(CASES_DIR)
    assert source.startswith("files:") and len(packets) == len(from_files), (source, len(packets))
    print(f"OK: loader prefers files ({source}) with {len(packets)} packets")

    seed_cases.candidate_dirs = lambda: [Path("__definitely_missing__")]
    packets, source, diagnostics = load_packets(Path("__definitely_missing__"))
    assert source == "embedded" and len(packets) == len(from_files), (source, len(packets))
    print(f"OK: loader falls back to {source} with {len(packets)} packets when no files exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
