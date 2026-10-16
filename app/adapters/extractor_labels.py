"""Deterministic label-aware extractor for the standard intake form.

Used for cases pasted at runtime, where there are no pre-authored extraction specs.
It scans each document for the form's labels, records the matched substring verbatim
as the citation, and derives the value from it. A label that is absent produces no
fact, so the corresponding rule becomes UNKNOWN and the case goes to a human.
"""

from __future__ import annotations

import re

from app.models import Citation, Document, Fact

_PATTERNS: tuple[tuple[str, str, str, str], ...] = (
    ("age", "Age", "int", r"\bage\b\s*[:\-]\s*(\d{1,3})"),
    ("province", "Province", "str", r"\bprovince(?:\s+of\s+residence)?\b\s*[:\-]\s*([^\n]+)"),
    ("household_size", "Household size", "int", r"\bhousehold\s+size\b\s*[:\-]\s*(\d{1,4})"),
    (
        "monthly_income_pkr",
        "Monthly income (PKR)",
        "int",
        r"\bmonthly\s+(?:household\s+)?income\b(?:\s*\([^)]*\))?\s*[:\-]\s*(?:pkr|rs\.?|₨)?\s*([\d,]+)",
    ),
    ("owns_car", "Owns a car", "bool", r"\bowns\s+a\s+car\b\s*[:\-]\s*(yes|no|true|false)"),
    ("land_acres", "Land owned (acres)", "int", r"\bland\s+owned\b(?:\s*\([^)]*\))?\s*[:\-]\s*(\d{1,4})"),
    ("bank_balance_pkr", "Bank balance (PKR)", "int", r"\bbank\s+balance\b(?:\s*\([^)]*\))?\s*[:\-]\s*(?:pkr|rs\.?|₨)?\s*([\d,]+)"),
)


def _coerce(kind: str, raw: str):
    if kind == "int":
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else None
    if kind == "bool":
        return raw.strip().lower() in ("yes", "true")
    return raw.strip()


class LabelsExtractor:
    name = "labels"

    def extract(self, documents: list[Document], packet: dict) -> list[Fact]:
        facts: list[Fact] = []
        for document in documents:
            for key, label, kind, pattern in _PATTERNS:
                for match in re.finditer(pattern, document.text, re.IGNORECASE):
                    value = _coerce(kind, match.group(1))
                    if value is None:
                        continue
                    quote = match.group(0).strip()
                    start = document.text.find(quote)
                    citation = (
                        Citation(document.doc_id, quote, start, start + len(quote), True)
                        if start >= 0
                        else None
                    )
                    facts.append(
                        Fact(key=key, label=label, value=value, citation=citation, method=self.name)
                    )
        return facts
