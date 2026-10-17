# Witness - demo runbook (video + screenshots)

Everything below is written against the **live** service as of 17 Oct 2026, 07:50 PKT.

- **Primary URL:** https://alternate-echo-whale-5578-github-app.alternatefutures.ai
- **Fallback URL:** https://witness-tee-app.alternatefutures.ai (same app, separate in-memory
  data; not TEE-attested - never call it confidential)
- **Build:** v0.4.0, image `8c0478e`
- **Expected header:** `API online · v0.4.0 · stage 3` and a **clickable** status pill
  that opens **System & Adapters**.

> **Never show** the Alternate Clouds dashboard environment-variables tab, the CLI
> `printenv` output, or any terminal with keys. Record only the browser app.

---

## 0. Pre-flight (2 minutes, before recording)

1. Open the primary URL in a fresh window. Close other tabs; hide the bookmarks bar.
2. Zoom to 100-110% so the case table is legible at 1080p.
3. Confirm the status pill reads `API online · v0.4.0 · stage 3`.
4. Click **System & Adapters** once and confirm it renders, then go back (click a case).
5. Press **Reseed cases** once so the queue is in a known state (5 cases, none decided).
   - Reseeding does **not** clear the audit ledger. That is intentional; the demo script
     decides a case and then shows the ledger, so a pre-existing ledger is fine.
6. In `/api/audit/verify` (open in a scratch tab, not on camera) confirm `"ok": true`.
7. If anything looks wrong, switch to the fallback URL and repeat steps 2-6.

**Recording settings:** 1440x900 or 1920x1080, 30 fps, system audio optional. Target 2:30-2:45.

---

## 1. Case facts you can state confidently

| Case | Status | Verification | What it demonstrates |
|---|---|---|---|
| `CASE-2026-0001` Ayesha Bibi | `VERIFIED` | `OK` | 7 facts, all 7 rules PASS, recommendation ELIGIBLE, still needs a human |
| `CASE-2026-0002` Bilal Khan | `NEEDS_REVIEW` | `ABSTAIN` | income missing -> `INCOME_LIMIT UNKNOWN` -> escalate; **best case for the request-info/resubmit beat** |
| `CASE-2026-0003` Nadia Rehman | `NEEDS_REVIEW` | `ABSTAIN` | two income figures (45,000 vs 90,000) -> **Conflicting evidence** panel |
| `CASE-2026-0004` Imran Shah | `NEEDS_REVIEW` | `ABSTAIN` | income fact has **no citation** -> grounding fails, `ABSTAIN` **even though every rule PASSes** |
| `CASE-2026-0005` Sana Malik | `NEEDS_REVIEW` | `OK` | 4 rule FAILs (income, car, land, savings) but **never DENIED** |

Every case shows a **Policy clause** column in the rules table (Clause 1-7).

---

## 2. Demo video - click-by-click (target 2:40)

### 0:00-0:12 | Landing page
- Stay on the queue. Say: *"Witness is a decision desk for high-stakes benefits screening.
  The AI proposes, an independent check audits, and a human decides. The pipeline cannot deny
  anyone."*
- Gesture at the status pill: *"Live on Alternate Clouds."*

### 0:12-0:35 | `CASE-2026-0001` - grounded evidence
- Click **CASE-2026-0001 (Ayesha Bibi)** in the left queue.
- Scroll to **Extracted facts & grounding**.
- Point at one row: age 34 with the quote `"Age: 34 years"`, the document id and the span,
  and the green **verified** mark. Say: *"Every fact carries the exact quote it came from.
  The extractor cannot smuggle in a value without a citation."*

### 0:35-0:55 | Rules and the recommendation
- Scroll to **Deterministic rules**. Point at the 7 rows and the **Policy clause** column.
- Say: *"Seven clauses run as ordinary code. The model never decides a rule. All pass, so the
  pipeline recommends ELIGIBLE - note it is still only VERIFIED. It is waiting for a person."*

### 0:55-1:12 | The human decides
- In **Human decision**, type officer: `Officer A. Raza`.
- Reason: `All seven clauses pass and every citation is grounded in the source form.`
- Choose **Approve** -> **Record human decision**.
- Say: *"The decision requires my name and a written reason. The backend rejects an empty
  reason, and a case cannot be decided twice."*

### 1:12-1:25 | The audit ledger
- Point at the **Audit ledger** entries (intake, pipeline_run, assigned if used,
  human_decision) and the short hashes.
- Click **Verify audit chain** in the sidebar. When it says **audit chain intact**, say:
  *"Every state change is hash-chained. Changing one entry breaks verification at that point."*

### 1:25-1:45 | Abstention - `CASE-2026-0003`
- Click **CASE-2026-0003 (Nadia Rehman)**.
- Point at the **Conflicting evidence** panel: `monthly_income_pkr` with two rows
  (45,000 in `d1`, 90,000 in `d2`) and both quotes.
- Then point at **Independent verification ABSTAIN** and the reason list.
- Say: *"Two sources disagree. The verifier refuses to guess and escalates. The state is
  NEEDS_REVIEW, not DENIED."*

### 1:45-2:05 | Missing evidence -> request info -> resubmit - `CASE-2026-0002`
- Click **CASE-2026-0002 (Bilal Khan)**.
- Point at `INCOME_LIMIT UNKNOWN` and the reason "monthly income evidence is missing".
- Fill officer `Officer A. Raza`, action **Request more info**, reason
  `Income statement was not attached; requesting it.` -> record.
- In the resubmit box, paste:
  `Monthly household income: PKR 40,000`
  -> **Resubmit and re-run pipeline**.
- The case becomes **VERIFIED / ELIGIBLE** with 7 grounded facts, no decision attached.
- Say: *"New evidence re-runs the whole pipeline. The case reopens; no decision was carried over."*

### 2:05-2:15 | An uncited fact is enough to abstain - `CASE-2026-0004`
- Click **CASE-2026-0004 (Imran Shah)**.
- Point at the **verification** reason: `Grounding failed for 'Monthly income (PKR)': no
  citation attached to this fact.`
- Point at the rule table: every rule still says **PASS**.
- Say: *"This is the subtle one: the rule passed, but the fact had no citation. The verifier
  still refuses to endorse the case. Grounding is checked independently of the rule outcome."*

### 2:15-2:25 | Rule failures are still not denials - `CASE-2026-0005`
- Click **CASE-2026-0005 (Sana Malik)**.
- Point at the four FAIL rows (income, car, land, savings).
- Say: *"Even here the automated state is NEEDS_REVIEW. A denial exists only if an officer
  writes one."*

### 2:25-2:35 | Evaluation gate
- Click **Evaluation** in the top bar.
- Point at: **55/55 expectations**, grounding **0.971**, abstain **0.6**, and
  **Invariant: no case auto-denied PASS**.
- Say: *"The service refuses to start if this gate fails in strict mode."*

### 2:35-2:45 | Tamper demo
- Click **Tamper demo** in the sidebar.
- Read the three lines: chain intact -> **forged copy detected at #N** -> real ledger untouched.
- Say: *"Tampering is detected exactly at the changed entry, and the real ledger is untouched."*

### 2:45-2:55 | System & Adapters (honesty)
- Click the status pill (or **System & Adapters**).
- Point at the **Audit Ledger** banner: requested `postgres`, active `sqlite`, degraded.
- Say: *"We wired a managed Postgres ledger and linked it, but the two services landed on
  different decentralized providers, so the cluster-local name cannot resolve. Witness
  degrades to SQLite and says so instead of pretending. That is the reliability story."*
- Stop recording.

---

## 3. Screenshots (12) - exact capture list

Save as `shot-01-...png` etc. Capture at the same zoom as the video.

| # | Where | What must be visible |
|---|---|---|
| 1 | `/health` in browser | `"status":"ok"`, `"version":"0.4.0"`, `"gate":{"all_passed":true...}` |
| 2 | `/` landing | Queue with 5 cases, status pill `API online`, all top-bar buttons |
| 3 | `CASE-2026-0001` top | Name, `VERIFIED`, recommendation `ELIGIBLE`, "pipeline cannot deny" note |
| 4 | `CASE-2026-0001` facts | At least two rows with quote + doc id + span + green verified |
| 5 | `CASE-2026-0001` rules | 7 rows, statuses, **Policy clause** column |
| 6 | `CASE-2026-0003` | **Conflicting evidence** panel with both income values and quotes |
| 7 | `CASE-2026-0003` verification | `ABSTAIN` badge plus the reason list |
| 8 | `CASE-2026-0004` | Grounding-failure reason for income, with every rule still `PASS` |
| 9 | `CASE-2026-0001` after approve | Status `APPROVED`, officer + reason shown, ledger entries |
| 10 | Evaluation panel | 55/55, 0.971, 0.6, `no_auto_deny PASS` |
| 11 | Tamper demo result | intact -> broken at #N -> real ledger untouched |
| 12 | System & Adapters | Audit banner (requested/active/degraded) + metrics cards |

Optional 13: a PDF intake result (see section 4).

---

## 4. Optional live intake (text or PDF)

**New case** takes a PDF (file picker) or pasted text. The deterministic label reader needs
these exact labels, one per line:

```
Form B-1: Income Support Application
Name: Fatima Noor
Age: 46 years
Province of residence: Punjab
Household size: 6 persons
Monthly household income: PKR 38,000
Owns a car: No
Land owned (acres): 0
Bank balance: PKR 9,000
```

Result: `VERIFIED` / `ELIGIBLE`, 7 grounded facts.

**Contradiction demo:** paste the same form as Document 1, and as Document 2:

```
Income Verification Note
Monthly household income (revised): PKR 150,000
```

Result: `NEEDS_REVIEW`, `ABSTAIN`, conflict panel.

**Missing evidence:** omit the income line entirely -> `INCOME_LIMIT UNKNOWN` -> `NEEDS_REVIEW`.

---

## 5. Contingencies

| Situation | What to do |
|---|---|
| Primary URL returns nginx 404 / 503 or does not load | Switch to the **fallback URL**, re-check the status pill, continue. Do not re-record unless the UI differs. |
| LLM rate-limited or key issue | The app falls back automatically; facts show `fixture(fallback)`. Do not call it an error - it is the designed degradation. Do not mention the key. |
| Audit badge says `Audit: SQLite fallback (degraded)` | Expected. Say the Postgres service is linked but cross-provider, so Witness degrades safely and reports it. |
| Tamper demo says "no entries" | Decide a case first (approve case 1), then press Tamper demo. |
| A case is already decided from a previous run | Press **Reseed cases** (queue resets; ledger history remains). |
| Metrics P50/P95 show `-` | Harmless: the live image predates the percentile fix. Do not focus on it; the other cards are populated. |
| You need to restart the demo | Press **Reseed cases**, then start from case 1. |

---

## 6. Post-record checklist

- [ ] Video is 2:30-2:50, no keys or dashboard env vars visible.
- [ ] All 12 screenshots saved and legible.
- [ ] Primary URL re-checked after recording: status pill online, `/api/eval` still
      `all_passed: true`.
- [ ] PDF (`Witness_Where_The_Human_Comes_In.pdf`) attached.
- [ ] Repo URL + live URL copied into the submission form.
- [ ] LinkedIn post written and posted by a human team member (not generated).
