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
| `READER` | `text` (later: `pdf`) | document reader |
| `EXTRACTOR` | `fixture` (later: `llm`) | fact extraction |
| `VERIFIER` | `det` (later: `llm`) | abstain / audit |
| `AUDIT` | `sqlite` (later: `postgres`) | audit storage |

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
