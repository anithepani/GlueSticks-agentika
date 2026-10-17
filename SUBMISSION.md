# Witness - Submission Pack

Everything here describes **actually implemented and verified** behaviour. Where something
is not verified, it is labelled. Nothing in this file claims TEE or a live PostgreSQL ledger.

- **Live service:** https://alternate-echo-whale-5578-github-app.alternatefutures.ai
- **Version:** `0.4.0`
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
                 [ AUDIT LEDGER ]  sqlite (active) | postgres (adapter ready)
                                   append-only SHA-256 hash chain + /api/audit/verify
```

Adapters are selected by environment flags and every LLM/storage step has a deterministic
fallback:

| Flag | Values | Notes |
|---|---|---|
| `READER` | `pdf`, `text` | `pdf` also reads plain text |
| `EXTRACTOR` | `fixture`, `labels`, `llm` | `llm` proposes value + quote; quote is re-grounded verbatim |
| `VERIFIER` | `det`, `llm` | `llm` can only add abstention, never clear a deterministic failure |
| `AUDIT` | `sqlite`, `postgres` | resilient: falls back to sqlite and reports degradation |
| `LLM_PROVIDER` | `groq`, `gemini` | key sent as a header, never in a URL; redacted from errors |

**Live adapters (verified):** `reader=pdf`, `extractor=llm(fallback:fixture)`,
`verifier=llm(fallback:det)`, `audit=sqlite` (requested `postgres`, degraded - see section 5).

---

## 2. Demo video script (2-3 minutes)

Target length ~2:40. Speak plainly; do not show any API keys on screen.

| Time | Screen | Narration |
|---|---|---|
| 0:00-0:15 | Landing page `/` | "Witness is a decision desk for high-stakes benefits screening. The AI proposes, an independent check audits, and a human decides. The AI can never deny anyone." |
| 0:15-0:35 | Officer queue, case **CASE-2026-0001** open | "Five synthetic cases are loaded. Case 1 extracts seven facts. Every fact carries the exact quote it came from - here, 'Age: 34 years' at a specific span." |
| 0:35-0:55 | Rule table + "Pipeline recommendation: ELIGIBLE" | "Seven policy clauses run as ordinary code - income, land, car, savings, residency, age, household. The model never decides a rule. All pass, so the case is VERIFIED - but still pending a human." |
| 0:55-1:20 | Approve with a reason | "I am the officer. I approve, with a written reason, and the decision is recorded. Try to approve again or submit an empty reason - the backend rejects it." |
| 1:20-1:55 | **CASE-2026-0003** (contradiction) | "Case 3 has two different income figures. The verifier flags the contradiction and abstains. Note the state is NEEDS_REVIEW, not DENIED - the system refuses to guess and escalates to a person." |
| 1:55-2:15 | **CASE-2026-0004** (missing evidence) + request_info -> resubmit | "Case 4 is missing income. It stays UNKNOWN. I request more information, then paste a new document; the pipeline re-runs and the case moves forward." |
| 2:15-2:35 | "Evaluation" panel + "Tamper demo" | "The evaluation gate re-runs the whole set: 55 of 55 expectations, grounding 0.97, and the invariant that no case is ever auto-denied. Finally, the audit ledger is hash-chained - if I alter a copy, verification breaks exactly at the changed entry, while the real ledger stays intact." |
| 2:35-2:45 | `/api/adapters` | "The app reports honestly which adapters are live, including when the requested database is degraded to the safe fallback." |

---

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
8. **Honesty about limits.** The app reports the requested vs active storage backend and
   flags degraded operation instead of pretending. A verifying hash chain proves
   *integrity*, not *durability* - that distinction is stated explicitly.

---

## 4. Screenshot checklist (proof)

| # | Screen / endpoint | Shows |
|---|---|---|
| 1 | `GET /health` | `status ok`, `version 0.4.0`, `gate.all_passed: true` |
| 2 | Landing page `/` | The decision desk loads; live status dot |
| 3 | Officer queue | Five seeded cases with statuses |
| 4 | Case 1 detail | Grounded citations with quotes and spans; all rules PASS; "rec: ELIGIBLE"; human decision form |
| 5 | Case 3 detail | "Conflicting evidence" panel; verifier `ABSTAIN`; state `NEEDS_REVIEW` |
| 6 | Case 4 detail | Missing income -> `UNKNOWN`; no auto-deny |
| 7 | After approving case 1 | Status `APPROVED`, reason shown, audit entries appended |
| 8 | Evaluation panel | grounding 0.971, abstain 0.6, 55/55, `no_auto_deny PASS` |
| 9 | Tamper demo result | intact -> "forged copy detected at #N" -> real ledger untouched |
| 10 | `GET /api/adapters` | requested `postgres`, active `sqlite`, `audit_degraded: true` (honest degradation) |
| 11 | PDF intake | A PDF form run through the pipeline (one page -> grounded facts) |
| 12 | CLI `acc services info` | Service running, image tag = deployed commit, port 8000 |

Capture 1, 8, 9 and 10 as the "reliability/verifiability" set; 4, 5 and 6 as the
"human-in-the-loop" set.

---

## 5. Verified production status (17 Oct 2026, 07:40 PKT)

| Check | Result |
|---|---|
| Deployed image | `8c0478e9dbb6` (`8c0478e`, `v0.4.0`) |
| Repository HEAD | `8c0478e` - UI "System & Adapters" view is live |
| `/health` | 200, `gate.all_passed: true` (55/55), grounding 0.971, abstain 0.6, `no_auto_deny: true` |
| All GET endpoints (`/`, `/api/info`, `/api/adapters`, `/api/cases`, `/api/policy`, `/api/eval`, `/api/metrics`, `/api/audit/verify`, `/api/diag`) | 200 |
| Intake -> assign -> decision (approve) | 200, status `APPROVED`, audit entries written |
| Unknown-case audit | 404 |
| Decision with empty reason | 400 |
| Tamper demo | intact -> forged copy detected at the changed entry -> real ledger intact |
| Seed source | `files:/app/data/cases` (data ships in the image) |
| `/api/metrics` | `requests_total`, `by_status`, `latency_ms.p50/p95`, gate and case counters |
| Local test suites | 7/7 pass (adds `tests/test_regressions.py`) |
| Failover URL (not submitted) | `https://witness-tee-app.alternatefutures.ai` - same image, plain deployment, **no TEE attestation** |

**Storage:** `audit_requested=postgres`, `audit_active=sqlite`, `audit_degraded=true`.
The Postgres service exists and runs, but sits on a different Akash provider from the app,
so the cluster-local `.internal` name does not resolve. See `DEPLOY.md` for the full
evidence and the supported options. **SQLite survives a process restart but not a
redeploy** (verified both ways).

---

## 6. CVM / TEE - TODO (deferred)

Status: **deferred, not running, no attestation.**

- Two `--confidential` redeploys of a duplicate service (`witness-tee`) failed with
  `CVM failed` - no viable confidential VM offer at the time.
- The failure is at provider placement/start of a Confidential VM, not in application code.
- Retry requirements: (a) a region/provider that actually offers a TEE-capable node
  (`acc regions` shows availability), and (b) the duplicate-service approach so the
  production URL is untouched.
- If a retry succeeds: `npx -y @alternatefutures/acc attest <tee-service-id>` (add
  `--verify` if supported).
- **Do not claim TEE protection or remote attestation until that succeeds.** The
  application never depends on confidential compute.
