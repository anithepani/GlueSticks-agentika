"""Embedded copy of the policy document.

data/policy/rules.md is the source of truth, but a build may not copy the data
directory into the image. Serving this fallback keeps /api/policy working anyway.
tests/test_seed.py asserts the two stay in sync.
"""

from __future__ import annotations

POLICY_MARKDOWN = """# Witness eligibility rules (simplified, synthetic)

> **Disclaimer.** This rule set is a demonstration for the Agentika 2.0 hackathon.
> It is **simplified, synthetic and BISP-inspired** and does **not** represent the
> official policy of BISP or of any government or agency. Thresholds are illustrative.

## How a rule is decided

Rules are ordinary Python code in `app/adapters/rules_pmt.py`. They compare
**grounded facts** (a value plus the verbatim quote it came from) against a published
threshold. A language model never decides a rule, and a rule can only produce:

- `PASS` — the evidence satisfies the rule,
- `FAIL` — the evidence violates the rule,
- `UNKNOWN` — the value is missing, unreadable, or contradictory.

`FAIL` never closes a case. `UNKNOWN` never closes a case. Both route the case to a
human officer. The pipeline's lowest state is `NEEDS_REVIEW`; `DENIED` is reachable
only through an explicit human decision.

## Thresholds

| Rule ID | Plain rule | Threshold |
|---|---|---|
| `AGE_ADULT` | Applicant is 18 or older | `age >= 18` |
| `INCOME_LIMIT` | Monthly household income within limit | `monthly_income_pkr <= 60,000` |
| `RESIDENCY` | Resident in a covered region | province in covered list |
| `HOUSEHOLD_SIZE` | Household size recorded | `household_size >= 1` |
| `ASSET_CAR` | No car declared | `owns_car == false` |

Covered regions: Punjab, Sindh, Khyber Pakhtunkhwa, Balochistan, Gilgit-Baltistan,
Azad Kashmir, Islamabad Capital Territory.

## Verification, independent of the pipeline

`app/adapters/verifier_det.py` re-checks the pipeline's own work and **abstains**
when:

1. a fact's citation quote is not found **verbatim** in its source document,
2. the same field carries **conflicting** values, or
3. any rule could not be decided (`UNKNOWN`).

An abstain sets the case to `NEEDS_REVIEW` regardless of the rule results.
"""
