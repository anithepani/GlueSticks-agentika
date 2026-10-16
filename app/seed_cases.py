"""Case packet loading with an embedded fallback.

The JSON files under data/cases are the source of truth, but not every build
system copies a data directory into the image. If no case files are found, the
pipeline seeds from the embedded packets below so the service is never empty.
`tests/test_seed.py` asserts the two stay in sync.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_DIR, ROOT

DEFAULT_CASES: list[dict] = [
    {
        "id": "CASE-2026-0001",
        "applicant_name": "Ayesha Bibi",
        "applicant_cnic": "61101-1234567-8",
        "province": "Punjab",
        "documents": [
            {
                "doc_id": "d1",
                "title": "Form B-1 — Income Support Application",
                "text": "Form B-1: Income Support Application\nName: Ayesha Bibi\nCNIC: 61101-1234567-8\nAge: 34 years\nProvince of residence: Punjab\nHousehold size: 5 persons\nMonthly household income: PKR 45,000\nOwns a car: No\nDeclaration: I declare the above is true and complete.",
            }
        ],
        "extraction": [
            {"key": "age", "label": "Age", "quote": "Age: 34 years", "value": 34, "doc_id": "d1"},
            {"key": "province", "label": "Province", "quote": "Province of residence: Punjab", "value": "Punjab", "doc_id": "d1"},
            {"key": "household_size", "label": "Household size", "quote": "Household size: 5 persons", "value": 5, "doc_id": "d1"},
            {"key": "monthly_income_pkr", "label": "Monthly income (PKR)", "quote": "Monthly household income: PKR 45,000", "value": 45000, "doc_id": "d1"},
            {"key": "owns_car", "label": "Owns a car", "quote": "Owns a car: No", "value": False, "doc_id": "d1"},
        ],
    },
    {
        "id": "CASE-2026-0002",
        "applicant_name": "Bilal Khan",
        "applicant_cnic": "42101-7654321-9",
        "province": "Sindh",
        "documents": [
            {
                "doc_id": "d1",
                "title": "Form B-1 — Income Support Application",
                "text": "Form B-1: Income Support Application\nName: Bilal Khan\nCNIC: 42101-7654321-9\nAge: 41 years\nProvince of residence: Sindh\nHousehold size: 7 persons\nOwns a car: No\nDeclaration: I declare the above is true and complete.",
            }
        ],
        "extraction": [
            {"key": "age", "label": "Age", "quote": "Age: 41 years", "value": 41, "doc_id": "d1"},
            {"key": "province", "label": "Province", "quote": "Province of residence: Sindh", "value": "Sindh", "doc_id": "d1"},
            {"key": "household_size", "label": "Household size", "quote": "Household size: 7 persons", "value": 7, "doc_id": "d1"},
            {"key": "owns_car", "label": "Owns a car", "quote": "Owns a car: No", "value": False, "doc_id": "d1"},
        ],
    },
    {
        "id": "CASE-2026-0003",
        "applicant_name": "Nadia Rehman",
        "applicant_cnic": "35202-1111111-2",
        "province": "Punjab",
        "documents": [
            {
                "doc_id": "d1",
                "title": "Form B-1 — Income Support Application",
                "text": "Form B-1: Income Support Application\nName: Nadia Rehman\nCNIC: 35202-1111111-2\nAge: 29 years\nProvince of residence: Punjab\nHousehold size: 3 persons\nMonthly household income: PKR 45,000\nOwns a car: No",
            },
            {
                "doc_id": "d2",
                "title": "Income Verification Note",
                "text": "Income Verification Note\nApplicant: Nadia Rehman\nMonthly household income (revised): PKR 90,000\nSource: employer certificate received after initial intake.",
            },
        ],
        "extraction": [
            {"key": "age", "label": "Age", "quote": "Age: 29 years", "value": 29, "doc_id": "d1"},
            {"key": "province", "label": "Province", "quote": "Province of residence: Punjab", "value": "Punjab", "doc_id": "d1"},
            {"key": "household_size", "label": "Household size", "quote": "Household size: 3 persons", "value": 3, "doc_id": "d1"},
            {"key": "monthly_income_pkr", "label": "Monthly income (PKR)", "quote": "Monthly household income: PKR 45,000", "value": 45000, "doc_id": "d1"},
            {"key": "monthly_income_pkr", "label": "Monthly income (PKR)", "quote": "Monthly household income (revised): PKR 90,000", "value": 90000, "doc_id": "d2"},
            {"key": "owns_car", "label": "Owns a car", "quote": "Owns a car: No", "value": False, "doc_id": "d1"},
        ],
    },
    {
        "id": "CASE-2026-0004",
        "applicant_name": "Imran Shah",
        "applicant_cnic": "17301-2222222-3",
        "province": "Khyber Pakhtunkhwa",
        "documents": [
            {
                "doc_id": "d1",
                "title": "Form B-1 — Income Support Application",
                "text": "Form B-1: Income Support Application\nName: Imran Shah\nCNIC: 17301-2222222-3\nAge: 52 years\nProvince of residence: Khyber Pakhtunkhwa\nHousehold size: 6 persons\nOwns a car: No\nNote: income section left blank at intake.",
            }
        ],
        "extraction": [
            {"key": "age", "label": "Age", "quote": "Age: 52 years", "value": 52, "doc_id": "d1"},
            {"key": "province", "label": "Province", "quote": "Province of residence: Khyber Pakhtunkhwa", "value": "Khyber Pakhtunkhwa", "doc_id": "d1"},
            {"key": "household_size", "label": "Household size", "quote": "Household size: 6 persons", "value": 6, "doc_id": "d1"},
            {"key": "monthly_income_pkr", "label": "Monthly income (PKR)", "quote": "Monthly household income: PKR 30,000", "value": 30000, "doc_id": "d1"},
            {"key": "owns_car", "label": "Owns a car", "quote": "Owns a car: No", "value": False, "doc_id": "d1"},
        ],
    },
    {
        "id": "CASE-2026-0005",
        "applicant_name": "Sana Malik",
        "applicant_cnic": "33100-3333333-4",
        "province": "Punjab",
        "documents": [
            {
                "doc_id": "d1",
                "title": "Form B-1 — Income Support Application",
                "text": "Form B-1: Income Support Application\nName: Sana Malik\nCNIC: 33100-3333333-4\nAge: 38 years\nProvince of residence: Punjab\nHousehold size: 4 persons\nMonthly household income: PKR 120,000\nOwns a car: Yes\nDeclaration: I declare the above is true and complete.",
            }
        ],
        "extraction": [
            {"key": "age", "label": "Age", "quote": "Age: 38 years", "value": 38, "doc_id": "d1"},
            {"key": "province", "label": "Province", "quote": "Province of residence: Punjab", "value": "Punjab", "doc_id": "d1"},
            {"key": "household_size", "label": "Household size", "quote": "Household size: 4 persons", "value": 4, "doc_id": "d1"},
            {"key": "monthly_income_pkr", "label": "Monthly income (PKR)", "quote": "Monthly household income: PKR 120,000", "value": 120000, "doc_id": "d1"},
            {"key": "owns_car", "label": "Owns a car", "quote": "Owns a car: Yes", "value": True, "doc_id": "d1"},
        ],
    },
]


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
