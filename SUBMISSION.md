# Witness - Submission Pack

Everything here describes **actually implemented and verified** behaviour. Where something
is not verified, it is labelled.

- **Live service:** https://alternate-echo-whale-5578-github-app.alternatefutures.ai
- **Version:** `0.5.0`
- **Platform:** Alternate Clouds (Akamai/Akash-backed decentralized compute)
- **Theme:** Human + AI: Better Together - the human decision is a structural stage in the pipeline.

---

## 1. Architecture

```
                 case packet (text / PDF)
                          |
                  [ READER ]  text | pdf            -> Documents
                          |
              [ EXTRACTOR ]  llm | labels | fixture  -> Facts + citations
                          |        (value + exact verbatim quote + span)
                          |
             [ RULES ENGINE ]  pmt (deterministic)    -> PASS / FAIL / UNKNOWN per clause
                          |        (the model never decides a rule)
                          |
              [ VERIFIER ]  llm | det                -> OK | ABSTAIN
                          |        (grounding, contradiction, undecided checks;
                          |         the model may only ADD an abstention)
                          |
                 recommendation: ELIGIBLE | NEEDS_REVIEW
                          |        (never a denial - lowest auto state is NEEDS_REVIEW)
                          |
        ================ HUMAN OFFICER (structural gate) ================
                          |   approve | deny | request_info
                          |   + mandatory written reason
                          |
                 [ AUDIT LEDGER ]  sqlite, append-only SHA-256 hash chain
                                   append-only SHA-256 hash chain + /api/audit/verify
```

Adapters are selected by environment flags and every LLM/storage step has a deterministic
fallback:

| Flag | Values | Notes |
|---|---|---|
| `READER` | `pdf`, `text` | `pdf` also reads plain text |
| `EXTRACTOR` | `fixture`, `labels`, `llm` | `llm` proposes value + quote; quote is re-grounded verbatim |
| `VERIFIER` | `det`, `llm` | `llm` can only add abstention, never clear a deterministic failure |
| `AUDIT` | `sqlite` | append-only, hash-chained decision ledger |
| `LLM_PROVIDER` | `groq`, `gemini` | key sent as a header, never in a URL; redacted from errors |

**Live adapters (verified):** `reader=pdf`, `extractor=llm(fallback:fixture)`,
`verifier=llm(fallback:det)`, `audit=sqlite`.

---

## 2. Demo video script (2-3 minutes)

Target length ~2:45. Speak plainly; do not show any API keys on screen.

| Time | Screen | Narration |
|---|---|---|
| 0:00-0:12 | Cases (queue) | "Witness is a decision desk for high-stakes benefits screening. The pipeline proposes an assessment, an independent check audits it, and an officer decides. The pipeline cannot deny anyone." |
| 0:12-0:35 | Case 1 - Evidence, then Documents | "Every fact is tied to the exact sentence it came from. Clicking the source opens the document and highlights the quotation." |
| 0:35-0:55 | Case 1 - Rules | "Seven clauses run as ordinary code. The model never decides a clause. All seven are met, so the assessment is Eligible - but the case is only Verified. It is waiting for a person." |
| 0:55-1:15 | Decision panel | "A decision needs an officer and a written reason. The backend rejects an empty reason, and a decided case cannot be decided twice." |
| 1:15-1:35 | Activity - Verify ledger, Simulate tampering | "Every change is appended to a hash chain. Tampering is detected exactly where the change was made, and the real ledger stays intact." |
| 1:35-1:55 | Case 3 - conflicting evidence, Verification | "Two documents disagree on income. The verifier refuses to guess and escalates. The state is Needs review, not Denied." |
| 1:55-2:15 | Case 2 - request information, then resubmit | "I request the missing income statement, paste it, and the whole pipeline re-runs. The case reopens with no decision carried over." |
| 2:15-2:25 | Case 4 - Verification, then Rules | "The clause passed, but the fact had no quotation. The verifier still refuses to endorse the case." |
| 2:25-2:35 | Case 5 - Rules | "Four clauses are not met, and the automated state is still Needs review. A denial only exists if an officer writes one." |
| 2:35-2:47 | Quality | "The gate re-runs 55 expectations: grounding, abstention, and the invariant that no case is ever automatically denied." |
| 2:47-2:57 | About | "The About page states exactly which reader, model, verifier and ledger are running." |

## 3. PDF content - "Where the Human Comes In"

**Title:** Where the Human Comes In - a structural human gate for high-stakes AI decisions.

1. **The problem.** Eligibility decisions affect people's lives. A model that can issue a
   final "no" is unacceptable, and a model that is merely asked to "be careful" is not a
   safeguard.
2. **The design rule.** In Witness the human is a **stage in the pipeline**, not a
   reviewer bolted on afterwards. The automated pipeline can reach `VERIFIED` or
   `NEEDS_REVIEW`. The string `DENIED` is only ever produced by an explicit human action.
3. **Abstention instead of guessing.** Missing evidence, contradictory evidence, or a
   citation that does not appear verbatim in the source text forces an `ABSTAIN`, which
   routes the case to a person. This is *verification that abstains* rather than guesses.
4. **Rules are code, not vibes.** Seven policy clauses are evaluated deterministically.
   Each rule cites its clause. The model never decides a rule, and a model opinion can
   only make the outcome *more* cautious - it can add an abstention but never clear a
   deterministic failure.
5. **The human decision is enforced by the backend.** A decision requires an officer name
   and a written reason (minimum length), the action must be one of
   `approve`/`deny`/`request_info`, and the case must be in a decidable state. Duplicate
   and invalid transitions are rejected. A human override of an abstention is recorded as
   `overrode_abstention` so it is visible rather than silent.
6. **Accountability.** Every state change is appended to a SHA-256 hash-chained ledger.
   Tampering with any entry breaks verification at that point. `POST /api/audit/tamper-demo`
   demonstrates this on a copy, leaving the real ledger untouched.
7. **Durability first.** The audit entry is written *before* the in-memory state changes, so
   a decision can never appear to succeed without a record. If the ledger cannot be
   written, the API returns `503` and the case is left unchanged.
8. **Honesty about limits.** The interface states its storage guarantees plainly. A
   verifying hash chain proves *integrity*, not *durability*, and the About page does not
   pretend otherwise.

---

## 4. Screenshot checklist (proof)

| # | Screen / endpoint | Shows |
|---|---|---|
| 1 | `GET /health` | `status ok`, `version 0.5.0`, `gate.all_passed: true` |
| 2 | Cases | The queue loads with five cases, status tags and filters |
| 3 | Case 1 - Evidence | Fact rows with value, quoted text, source link and Verified |
| 4 | Case 1 - Documents | The cited quotation highlighted inside the form text |
| 5 | Case 1 - Rules | Seven clauses, all Met, with the Clause column |
| 6 | Case 1 - decision panel | Approve / Deny / Request information with the reason field |
| 7 | Case 1 after approval | Decision record with officer, reason and timestamp |
| 8 | Case 1 - Activity | Timeline plus "Ledger intact" |
| 9 | Case 3 - Evidence | Conflicting income values, both quoted |
| 10 | Case 3 - Verification | Abstained with the reason list |
| 11 | Case 4 - Verification | "no supporting quote" reason while every clause reads Met |
| 12 | Quality | 55/55 expectations, 97% grounding, 60% abstention, "Holds" |
| 13 | About | Pipeline summary and deployment table |
| 14 | CLI `acc services info` | Service running, image tag = deployed commit, port 8000 |

Capture 1, 8 and 12 as the reliability set; 3, 6, 9 and 10 as the human-in-the-loop set.

---

## 5. Verified production status (17 Oct 2026, 09:35 PKT)

| Check | Result |
|---|---|
| Deployed image | `9f7ec40808eb` (`9f7ec40`, `v0.5.0`) |
| Repository HEAD | `9f7ec40` |
| `/health` | 200, `version 0.5.0`, `gate.all_passed: true` (55/55), grounding 0.971, abstain 0.6, `no_auto_deny: true` |
| All GET endpoints (`/`, `/api/info`, `/api/adapters`, `/api/cases`, `/api/policy`, `/api/eval`, `/api/metrics`, `/api/audit/verify`, `/api/diag`) | 200 |
| Intake -> assign -> decision (approve) | 200, status `APPROVED`, audit entries written |
| Unknown-case audit | 404 |
| Decision with empty reason | 400 |
| Tamper demo | intact -> forged copy detected at the changed entry -> real ledger intact |
| Seed source | `files:/app/data/cases` (data ships in the image) |
| Interface | New casework console: queue, tabs, sticky decision panel, policy, quality, about |
| Local test suites | 7/7 pass (adds `tests/test_regressions.py`) |

**Storage:** an append-only, hash-chained SQLite ledger stored beside the application.
It survives a process restart; it is reset when the service is redeployed, which is
stated plainly in the interface rather than hidden.

---
