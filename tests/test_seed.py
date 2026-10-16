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

    check_embedded_golden()
    check_embedded_policy()
    check_generator_sync()
    return 0


def check_generator_sync() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("embed_tool", REPO / "tools" / "embed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rendered = module.render()
    actual = (REPO / "app" / "embedded.py").read_text(encoding="utf-8")
    assert rendered == actual, "app/embedded.py is stale — run: python tools/embed.py"
    print("OK: app/embedded.py is in sync with data/ (regenerate with python tools/embed.py)")


def check_embedded_golden() -> None:
    from app.evaluation import DEFAULT_GOLDEN

    golden_path = REPO / "data" / "eval" / "golden.json"
    assert golden_path.exists(), "data/eval/golden.json missing"
    file_cases = json.loads(golden_path.read_text(encoding="utf-8"))["cases"]
    assert file_cases == DEFAULT_GOLDEN, "embedded golden drifted from data/eval/golden.json"
    print(f"OK: {len(file_cases)} embedded golden expectations match data/eval/golden.json")


def check_embedded_policy() -> None:
    from app.policy import POLICY_MARKDOWN

    policy_path = REPO / "data" / "policy" / "rules.md"
    assert policy_path.exists(), "data/policy/rules.md missing"
    assert policy_path.read_text(encoding="utf-8").strip() == POLICY_MARKDOWN.strip(), (
        "embedded policy drifted from data/policy/rules.md"
    )
    print("OK: embedded policy matches data/policy/rules.md")


if __name__ == "__main__":
    raise SystemExit(main())
