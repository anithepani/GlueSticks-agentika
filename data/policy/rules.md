# Witness eligibility rules (simplified, synthetic)

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

## Clauses

Every rule cites the clause it implements, so a decision traces back to written policy.

- **Clause 1 — AGE_ADULT.** The applicant must be 18 years or older. `age >= 18`.
- **Clause 2 — RESIDENCY.** The household must reside in a covered region. Covered: Punjab, Sindh, Khyber Pakhtunkhwa, Balochistan, Gilgit-Baltistan, Azad Kashmir, Islamabad Capital Territory.
- **Clause 3 — HOUSEHOLD_SIZE.** A household size must be recorded and be at least 1. `household_size >= 1`.
- **Clause 4 — INCOME_LIMIT.** Monthly household income must not exceed the threshold. `monthly_income_pkr <= 60,000`.
- **Clause 5 — ASSET_CAR.** The household must not own a car. `owns_car == false`.
- **Clause 6 — ASSET_LAND.** Land holding must not exceed 2 acres. `land_acres <= 2`.
- **Clause 7 — BANK_BALANCE.** Liquid savings must not exceed PKR 50,000. `bank_balance_pkr <= 50,000`.

## Thresholds

| Rule ID | Clause | Plain rule | Threshold |
|---|---|---|---|
| `AGE_ADULT` | Clause 1 | Applicant is 18 or older | `age >= 18` |
| `RESIDENCY` | Clause 2 | Resident in a covered region | province in covered list |
| `HOUSEHOLD_SIZE` | Clause 3 | Household size recorded | `household_size >= 1` |
| `INCOME_LIMIT` | Clause 4 | Monthly income within threshold | `monthly_income_pkr <= 60,000` |
| `ASSET_CAR` | Clause 5 | No car declared | `owns_car == false` |
| `ASSET_LAND` | Clause 6 | Land holding within limit | `land_acres <= 2` |
| `BANK_BALANCE` | Clause 7 | Liquid savings within limit | `bank_balance_pkr <= 50,000` |

## Verification, independent of the pipeline

`app/adapters/verifier_det.py` re-checks the pipeline's own work and **abstains**
when:

1. a fact's citation quote is not found **verbatim** in its source document,
2. the same field carries **conflicting** values, or
3. any rule could not be decided (`UNKNOWN`).

An abstain sets the case to `NEEDS_REVIEW` regardless of the rule results.
