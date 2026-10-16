# Witness

**AI proposes. An independent check audits. A human decides.**

Witness is a human-in-the-loop decision desk for high-stakes eligibility screening.
It is built for the *Agentika 2.0* hackathon (theme: **Human + AI: Better Together**)
and deployed on **Alternate Clouds**.

## What it does

1. **Intake** — a case packet (text/JSON) is read into documents.
2. **Extract** — facts are pulled out with a citation (verbatim quote + span).
3. **Rules** — a deterministic rules engine returns `PASS` / `FAIL` / `UNKNOWN` per rule. The model never decides a rule.
4. **Verify** — an independent check re-audits the recommendation and **abstains** on missing fields, contradictions, or unfound citations.
5. **Human decision** — an officer approves, denies, or requests more info, **with a required reason**. A case cannot reach a final state without this step.
6. **Audit** — every decision is hash-chained into an append-only ledger with an integrity check.

The pipeline can **never** emit a final denial on its own; the lowest it can reach is `NEEDS_REVIEW`.

> The rule set is **simplified, synthetic, and BISP-inspired**. It is a demonstration and does
> **not** represent official policy of any government or agency.

## Architecture

Single deployable service, single port, single Dockerfile. Every swappable step is a
port behind an environment flag, so components can be upgraded without a rewrite:

| Flag | Values | Meaning |
|---|---|---|
| `READER` | `pdf`, `text` | document reader (`pdf` also reads plain text) |
| `EXTRACTOR` | `fixture`, `labels`, `llm` | fact extraction |
| `VERIFIER` | `det`, `llm` | abstain / audit |
| `AUDIT` | `sqlite`, `postgres` | audit storage |
| `LLM_PROVIDER` | `groq`, `gemini` | which free provider the LLM adapters use |
| `WITNESS_STRICT` | `0`, `1` | refuse to serve if the evaluation gate fails |
| `WITNESS_SLA_HOURS` | number | case queue SLA threshold |

`EXTRACTOR=llm` asks a model for a value **plus the exact quote**; Witness then grounds
that quote verbatim, so an invented quote yields no citation and the verifier abstains.
`VERIFIER=llm` re-reads each citation and may only make the verdict **more** cautious —
it can add an abstain but never clears a deterministic failure. If a key is missing or a
call fails, both fall back to the deterministic path so a case is never dropped.
`GET /api/adapters` reports which adapters are live.

The app reads `PORT` from the environment, so the Alternate Clouds Source-tab port
always matches what the app listens on.

## Run locally (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PORT="8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — the page polls `/health` and shows a live status dot.

## Deploy on Alternate Clouds

See `DEPLOY.md`.

## Stage log

- **Stage 0** — skeleton, `/health`, static landing page. Deployed and reachable.
- **Stage 1** — walking skeleton: 5 seeded synthetic cases, deterministic rules,
  independent verifier that can abstain, human decision gate (approve/deny/request
  info with a required reason), and a hash-chained SQLite audit ledger with an
  integrity check. Cases load from `data/cases/*.json` with an embedded fallback
  (`app/seed_cases.py`) so the service is never empty; `/api/diag` reports which
  source was used.
- **Stage 2** — optional LLM adapters: `EXTRACTOR=llm` (Groq or Gemini) proposes
  values **with the exact quote**, which Witness grounds verbatim; `VERIFIER=llm`
  re-audits each citation and may only add an abstain. No SDKs (stdlib HTTP), and any
  missing key or API failure degrades to the deterministic path, so the live demo
  cannot break.
- **Stage 3** — runtime intake (`POST /api/cases`): a case pasted as plain text is
  read by a deterministic label-aware extractor (`app/adapters/extractor_labels.py`,
  or the model when a key is set), grounded to the matched substrings, and pushed
  through the same rules/verifier gate. The UI adds a new-case panel, a
  conflicting-evidence view, a policy view, an evaluation view, and a
  `request_info → resubmit → re-run` loop. Every artifact that lives under `data/`
  has an embedded fallback, so the service is fully functional even if a build does
  not copy `data/` into the image.
- **Stage 4** — hardening and breadth:
  - Policy is now **7 clauses** with traceable rule ids; each rule cites the clause
    it implements and the UI shows it.
  - **PDF intake** (`READER=pdf`): a PDF is read page-by-page and flows through the
    same grounding/rules/verify pipeline.
  - **Postgres audit** (`AUDIT=postgres`) via a linked database service, with a
    SQLite fallback so the app never dies if the database is unreachable.
  - **Fail-closed evaluation gate**: with `WITNESS_STRICT=1` the app refuses to
    serve unless the gate passes; `/health` reports the gate.
  - **Tamper demo** (`POST /api/audit/tamper-demo`) shows a forged ledger copy
    breaking the hash chain while the real ledger stays intact.
  - Officer **assignment + SLA/aging**; **observability** with `x-request-id`,
    JSON access logs, and `/api/metrics`.

## Tests

Pure-Python, no network, no API key required:

```powershell
.\.venv\Scripts\python.exe tests\test_seed.py
.\.venv\Scripts\python.exe tests\test_llm.py
.\.venv\Scripts\python.exe tests\test_intake.py
.\.venv\Scripts\python.exe tests\test_gate.py
.\.venv\Scripts\python.exe tests\test_pdf.py
.\.venv\Scripts\python.exe tests\test_ops.py
.\.venv\Scripts\python.exe tests\test_regressions.py
```

`tools/embed.py` regenerates `app/embedded.py` from `data/`; `tests/test_seed.py`
fails if it is stale. `tests/test_regressions.py` covers concurrency (only one human
decision can win), intake-id uniqueness across reseeds, provider-key redaction,
abstention-override recording, invalid-transition rejection and the tamper demo.

## Persistence

The seeded cases and decisions are held in memory; the audit ledger is stored by the
`AUDIT` backend. These have **different durability**:

- **SQLite (default):** survives a *process restart* on the same filesystem, and the
  chain verifies unchanged. It does **not** survive a *redeploy* (the container
  filesystem is ephemeral; no persistent volume is mounted).
- **Postgres:** would survive redeploys, but the linked database in the current
  deployment is on a different provider/cluster and is unreachable, so the app runs
  the SQLite fallback and reports `audit_degraded: true`.

A verifying hash chain proves **integrity**, not durability. See `DEPLOY.md` for the
verified persistence table.

## Docker image

`Dockerfile` installs `requirements.txt` and copies both `app/` and `data/`, so the
seeded cases, golden expectations and policy ship in the image. Every `data/` artifact
still has an embedded fallback (`app/embedded.py`), so the service also runs if only
`app/` is present. `GET /api/diag` reports which source was used.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + stage |
| GET | `/api/info` | service metadata |
| GET | `/api/policy` | rule set as Markdown |
| GET | `/api/cases` | officer queue + stats |
| POST | `/api/cases` | intake a new case from pasted text and run the pipeline |
| GET | `/api/cases/{id}` | full case (facts, citations, rules, verification) |
| POST | `/api/cases/{id}/decision` | human decision `{officer, action, reason}` |
| POST | `/api/cases/{id}/resubmit` | supply new evidence after `request_info`; re-runs the pipeline |
| GET | `/api/cases/{id}/audit` | audit entries for a case |
| POST | `/api/cases/{id}/assign` | assign a case to an officer |
| GET | `/api/audit/verify` | recompute the hash chain |
| POST | `/api/audit/tamper-demo` | show a forged copy breaking the chain (real ledger untouched) |
| GET | `/api/eval` | run the evaluation gate over the seeded set |
| GET | `/api/metrics` | request counts, latency, request IDs |
| POST | `/api/reseed` | idempotent reseed of seeded cases |
| GET | `/api/diag` | where cases were loaded from (files vs embedded fallback) |
| GET | `/api/adapters` | which reader/extractor/verifier/audit are active, and whether an LLM key is set |

## Evaluation gate

`GET /api/eval` re-runs the pipeline over the seeded set and compares it against
`data/eval/golden.json` (embedded fallback in `app/evaluation.py`). It reports the
**grounding rate** (facts with a verbatim citation), the **abstain rate** (cases
escalated instead of guessed), per-case rule agreement, and the hard invariant that
**no case is ever auto-denied** — the pipeline's highest states before a human are
`VERIFIED` and `NEEDS_REVIEW`.

