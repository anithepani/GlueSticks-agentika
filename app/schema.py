"""The target field schema the extractor is asked to produce.

Kept separate from both extractors so the LLM extractor can be validated against
the same contract the fixture extractor already satisfies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str
    hint: str


SCHEMA: tuple[Field, ...] = (
    Field("age", "Age", "int", "Applicant age in whole years"),
    Field("province", "Province", "str", "Province or region of residence"),
    Field("household_size", "Household size", "int", "Number of people in the household"),
    Field("monthly_income_pkr", "Monthly income (PKR)", "int", "Monthly household income in PKR"),
    Field("owns_car", "Owns a car", "bool", "Whether the household owns a car (yes/no)"),
    Field("land_acres", "Land owned (acres)", "int", "Agricultural land owned, in whole acres"),
    Field("bank_balance_pkr", "Bank balance (PKR)", "int", "Liquid savings / bank balance in PKR"),
)

SCHEMA_BY_KEY = {field.key: field for field in SCHEMA}


def schema_block() -> str:
    return "\n".join(f"- {field.key} ({field.type}): {field.label} — {field.hint}" for field in SCHEMA)
