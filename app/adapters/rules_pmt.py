"""Deterministic eligibility rules (PMT-inspired, simplified and synthetic).

The model never decides a rule: plain Python compares grounded facts against a
published threshold. Any missing or contradictory evidence yields UNKNOWN, which
forces the case to a human rather than a guess.

This is a demonstration rule set for the Agentika hackathon. It is NOT official
policy of BISP or any government.
"""

from __future__ import annotations

from typing import Any

from app.models import Fact, RuleResult

POLICY = {
    "name": "Income Support Screening (simplified, synthetic)",
    "min_age": 18,
    "income_threshold_pkr": 60000,
    "min_household_size": 1,
    "provinces": [
        "punjab",
        "sindh",
        "khyber pakhtunkhwa",
        "balochistan",
        "gilgit-baltistan",
        "azad kashmir",
        "islamabad capital territory",
    ],
    "asset_car_allowed": False,
}


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit() or ch == "-")
        if digits not in ("", "-"):
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "y", "1"):
            return True
        if low in ("false", "no", "n", "0"):
            return False
    if isinstance(value, int):
        return bool(value)
    return None


class PmtRules:
    name = "pmt"

    def evaluate(self, facts: list[Fact]) -> list[RuleResult]:
        index = self._index(facts)
        return [
            self._age(index),
            self._income(index),
            self._residency(index),
            self._household(index),
            self._asset(index),
        ]

    def _index(self, facts: list[Fact]) -> dict[str, Any]:
        grouped: dict[str, list[Fact]] = {}
        for fact in facts:
            grouped.setdefault(fact.key, []).append(fact)
        resolved: dict[str, Any] = {}
        for key, items in grouped.items():
            values = {repr(item.value) for item in items}
            if len(values) > 1:
                resolved[key] = ("conflict", items)
            else:
                resolved[key] = ("ok", items[0].value)
        return resolved

    def _get(self, index: dict[str, Any], key: str) -> tuple[str, Any]:
        if key not in index:
            return "missing", None
        state, value = index[key]
        if state == "conflict":
            return "conflict", None
        return "ok", value

    def _age(self, index: dict[str, Any]) -> RuleResult:
        state, value = self._get(index, "age")
        if state != "ok":
            return RuleResult("AGE_ADULT", "Applicant is 18 or older", "UNKNOWN", self._missing_detail("age", state), None, POLICY["min_age"])
        age = _as_int(value)
        if age is None:
            return RuleResult("AGE_ADULT", "Applicant is 18 or older", "UNKNOWN", "Age could not be read as a number.", value, POLICY["min_age"])
        status = "PASS" if age >= POLICY["min_age"] else "FAIL"
        return RuleResult("AGE_ADULT", "Applicant is 18 or older", status, f"Age {age} vs minimum {POLICY['min_age']}.", age, POLICY["min_age"])

    def _income(self, index: dict[str, Any]) -> RuleResult:
        state, value = self._get(index, "monthly_income_pkr")
        if state != "ok":
            return RuleResult("INCOME_LIMIT", "Monthly income within threshold", "UNKNOWN", self._missing_detail("monthly income", state), None, POLICY["income_threshold_pkr"])
        income = _as_int(value)
        if income is None:
            return RuleResult("INCOME_LIMIT", "Monthly income within threshold", "UNKNOWN", "Income could not be read as a number.", value, POLICY["income_threshold_pkr"])
        status = "PASS" if income <= POLICY["income_threshold_pkr"] else "FAIL"
        return RuleResult("INCOME_LIMIT", "Monthly income within threshold", status, f"PKR {income} vs threshold PKR {POLICY['income_threshold_pkr']}.", income, POLICY["income_threshold_pkr"])

    def _residency(self, index: dict[str, Any]) -> RuleResult:
        state, value = self._get(index, "province")
        if state != "ok":
            return RuleResult("RESIDENCY", "Resident in a covered region", "UNKNOWN", self._missing_detail("province", state), None, POLICY["provinces"])
        province = str(value).strip().lower()
        status = "PASS" if province in POLICY["provinces"] else "FAIL"
        return RuleResult("RESIDENCY", "Resident in a covered region", status, f"Province '{value}' {'is' if status == 'PASS' else 'is not'} in the covered list.", value, POLICY["provinces"])

    def _household(self, index: dict[str, Any]) -> RuleResult:
        state, value = self._get(index, "household_size")
        if state != "ok":
            return RuleResult("HOUSEHOLD_SIZE", "Household size recorded", "UNKNOWN", self._missing_detail("household size", state), None, POLICY["min_household_size"])
        size = _as_int(value)
        if size is None:
            return RuleResult("HOUSEHOLD_SIZE", "Household size recorded", "UNKNOWN", "Household size could not be read as a number.", value, POLICY["min_household_size"])
        status = "PASS" if size >= POLICY["min_household_size"] else "FAIL"
        return RuleResult("HOUSEHOLD_SIZE", "Household size recorded", status, f"Household of {size} vs minimum {POLICY['min_household_size']}.", size, POLICY["min_household_size"])

    def _asset(self, index: dict[str, Any]) -> RuleResult:
        state, value = self._get(index, "owns_car")
        if state != "ok":
            return RuleResult("ASSET_CAR", "No car declared", "UNKNOWN", self._missing_detail("car ownership", state), None, POLICY["asset_car_allowed"])
        owns_car = _as_bool(value)
        if owns_car is None:
            return RuleResult("ASSET_CAR", "No car declared", "UNKNOWN", "Car ownership could not be read as yes/no.", value, POLICY["asset_car_allowed"])
        status = "PASS" if owns_car is False else "FAIL"
        return RuleResult("ASSET_CAR", "No car declared", status, f"Owns a car: {owns_car}.", owns_car, POLICY["asset_car_allowed"])

    def _missing_detail(self, label: str, state: str) -> str:
        if state == "conflict":
            return f"No decision: conflicting values for {label}."
        return f"No decision: {label} evidence is missing or ungrounded."
