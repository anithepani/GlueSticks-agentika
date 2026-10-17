# Witness - demo runbook (video + screenshots)

Written against the redesigned console (v0.5.0). Every navigation step below matches the
live interface.

- **Primary URL:** https://alternate-echo-whale-5578-github-app.alternatefutures.ai
- **Fallback URL:** https://witness-tee-app.alternatefutures.ai (a second deployment of the
  same application; use only if the primary URL misbehaves)
- **Top bar:** `Witness` · Cases · Policy · Quality · About · `New case` · `Live`
- **Target length:** 2:30-2:55

> **Never show** the Alternate Clouds dashboard environment-variables tab, a terminal with
> keys, or the CLI `printenv` output. Record only the browser app.

---

## 0. Pre-flight (2 minutes)

1. Open the primary URL in a fresh window. Close other tabs; hide the bookmarks bar.
2. Zoom to 100-110% so tables are legible at 1080p.
3. Confirm the top-right indicator reads **Live**.
4. Open **About** once to confirm it renders, then return to **Cases**.
5. Open **About → Reset demonstration data** so the queue is back to 5 cases, none decided.
   - This resets the in-memory cases only. The audit ledger is not erased; the demo decides
     a case and then shows the ledger, so existing entries are fine.
6. If anything looks wrong, switch to the fallback URL and repeat.

**Recording:** 1440x900 or 1920x1080, 30 fps, system audio optional.

---

## 1. Case facts you can state confidently

| Case | State | Check | What it demonstrates |
|---|---|---|---|
| `CASE-2026-0001` Ayesha Bibi | Verified | Passed | 7 facts, all 7 clauses met, assessment Eligible - still needs a person |
| `CASE-2026-0002` Bilal Khan | Needs review | Abstained | income missing -> "Monthly income could not be found in the documents" -> escalate; **best case for request-info/resubmit** |
| `CASE-2026-0003` Nadia Rehman | Needs review | Abstained | two income values (45,000 and 90,000) -> **Conflicting evidence** |
| `CASE-2026-0004` Imran Shah | Needs review | Abstained | income fact has **no supporting quote**; every clause still reads **Met** |
| `CASE-2026-0005` Sana Malik | Needs review | Passed | four clauses **Not met** - state is still Needs review, never Denied |

---

## 2. Demo video - click by click

### 0:00-0:12 | Case queue
- Stay on **Cases**.
- Say: *"Witness is a decision desk for high-stakes benefits screening. The pipeline
  proposes an assessment, an independent check audits it, and an officer decides. The
  pipeline cannot deny anyone."*

### 0:12-0:35 | Grounded evidence - `CASE-2026-0001`
- Click **Ayesha Bibi** in the queue.
- You land on **Evidence**. Point at a fact row: age `34 years`, the quoted text
  "Age: 34 years", the source link, and **Verified**.
- Click one **source link**. It opens the **Documents** tab and highlights the quoted span
  in the form.
- Say: *"Every value is tied to the exact sentence it came from. A value without a
  quotation cannot be endorsed."*

### 0:35-0:55 | Clauses in code
- Click the **Rules** tab.
- Point at the seven rows, the **Clause** column, and the **Met** labels.
- Say: *"Seven policy clauses run as ordinary code. The model never decides a clause.
  All seven are met, so the assessment is Eligible - but the case is only Verified. It is
  waiting for a person."*

### 0:55-1:15 | The human decision
- In the right panel, choose **Approve**.
- Officer: `Officer A. Raza`.
- Reason: `All seven clauses are met and every fact is quoted from the application.`
- Click **Approve application**.
- Say: *"A decision needs an officer and a written reason. The backend rejects an empty
  reason, and a decided case cannot be decided twice."*

### 1:15-1:35 | The ledger
- You are taken to the **Activity** tab. Point at the timeline entries.
- Click **Verify ledger** - it reports the ledger is intact.
- Click **Simulate tampering** - it reports the forged copy was rejected at a specific
  entry, and that the original ledger is intact.
- Say: *"Every change is appended to a hash chain. Tampering is detected exactly where the
  change was made."*

### 1:35-1:55 | Abstention on conflicting evidence - `CASE-2026-0003`
- Click **Back to queue**, open **Nadia Rehman**.
- Point at **Conflicting evidence**: monthly income with 45,000 and 90,000, both quoted.
- Click **Verification**: the result is **Abstained**, with the reason.
- Say: *"Two documents disagree. The verifier refuses to guess and escalates. The state is
  Needs review, not Denied."*

### 1:55-2:15 | Request information -> resubmit - `CASE-2026-0002`
- Open **Bilal Khan**.
- In the panel, choose **Request information**, officer `Officer A. Raza`, reason
  `Income statement was not attached.`
- Click **Request information**.
- In the resubmit panel, paste: `Monthly household income: PKR 40,000`
- Click **Resubmit and re-run**.
- The case returns as **Verified**, 7 grounded facts, no decision carried over.
- Say: *"New evidence re-runs the whole pipeline. The case reopens."*

### 2:15-2:25 | An uncited fact is enough - `CASE-2026-0004`
- Open **Imran Shah** and click **Verification**.
- Point at: `Monthly income (PKR) has no supporting quote in the documents.`
- Then click **Rules**: every clause still says **Met**.
- Say: *"The clause passed, but the fact had no quotation. The verifier still refuses to
  endorse the case."*

### 2:25-2:35 | Failures are not denials - `CASE-2026-0005`
- Open **Sana Malik**, **Rules** tab.
- Point at four **Not met** clauses and the assessment callout.
- Say: *"Even here the automated state is Needs review. A denial only exists if an officer
  writes one."*

### 2:35-2:47 | Quality gate
- Click **Quality** in the top bar.
- Point at 55/55 expectations, grounding 97%, abstention 60%, and **No automatic denial:
  Holds**.
- Say: *"The service re-runs this gate at start-up and refuses to serve if it fails."*

### 2:47-2:57 | About
- Click **About**.
- Point at the pipeline summary and the deployment table (reader, model, verifier, ledger).
- Say: *"The About page states exactly what is running. Nothing is hidden behind a
  dashboard."*
- Stop recording.

---

## 3. Screenshots (12 + 2 proof shots)

Save as `shot-01-...png`. Capture at the same zoom as the video.

| # | Where | What must be visible |
|---|---|---|
| 1 | `/health` in browser | `"status":"ok"`, `"version":"0.5.0"`, `"gate":{"all_passed":true...}` |
| 2 | Cases | 5 rows, status tags, filter chips, top bar |
| 3 | Case 1 · Evidence | Fact rows with value, quoted text, source link, Verified |
| 4 | Case 1 · Documents | The highlighted quotation inside the form text |
| 5 | Case 1 · Rules | 7 clauses, all Met, Clause column |
| 6 | Case 1 · decision panel | Approve / Deny / Request information + reason field |
| 7 | Case 1 after approval | Decision record with officer, reason, timestamp |
| 8 | Case 1 · Activity | Timeline + "Ledger intact" result |
| 9 | Case 3 · Evidence | Conflicting evidence with 45,000 and 90,000, both quoted |
| 10 | Case 3 · Verification | Abstained + reason list |
| 11 | Case 4 · Verification | "no supporting quote" reason |
| 12 | Quality | 55/55, 97%, 60%, "Holds" |
| 13 | About | Pipeline summary + deployment table |
| P1 | **Discord** | Both team members in the Alternate Futures server (display names visible) |
| P2 | **Alternate Clouds dashboard** | The service and deployment status (Overview/Source, **not** the env-vars tab) |

---

## 4. Optional live intake

**New case** accepts a PDF (file picker or drag-and-drop) or pasted text. The reader needs
these labels, one per line:

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

Result: **Verified**, assessment **Eligible**, 7 grounded facts. Use **Load a sample
packet** to fill the form in one click.

**Contradiction demo:** put the same form in "Form text", and in "Additional evidence":
`Monthly household income (revised): PKR 150,000` -> Needs review + conflict panel.

**Missing evidence:** delete the income line -> "Monthly income could not be found in the
documents" -> Needs review.

---

## 5. Contingencies

| Situation | What to do |
|---|---|
| Primary URL does not load or returns 404/503 | Switch to the fallback URL and continue. |
| Model rate-limited or unavailable | Extraction falls back to the deterministic reader; cases still ground and the gate still passes. Do not call it an error. |
| A case is already decided | About -> **Reset demonstration data**, then start from case 1. |
| Verification says "Earlier entry could not be..." | Not expected; use the fallback URL and tell the team. |
| You need a clean ledger for the take | A ledger resets only on a new deployment. For the demo it is enough to reset cases; the ledger showing prior entries is realistic. |

---

## 6. Post-record checklist

- [ ] Video 2:30-2:57, no keys or dashboard env vars visible.
- [ ] 12 interface screenshots + Discord + dashboard proof shots saved and legible.
- [ ] Primary URL still online after recording; `/api/eval` still `all_passed: true`.
- [ ] PDF `Witness_Submission.pdf` attached.
- [ ] LinkedIn post and teammate reshare links copied into the PDF.
- [ ] Submitted before 12:45 PM PKT.
