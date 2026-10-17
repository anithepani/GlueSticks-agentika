# Session Summary & Agent Handoff: Project "Witness"

> **Purpose:** This document extracts and condenses the full session trajectory from `my-session.json` (~323 messages, 3.5 MB JSON) into a comprehensive reference for any AI agent or collaborator continuing work on this codebase.

---

## 1. Session & Environment Metadata

* **Session ID:** `ses_eba06890cffe6aF5AA0LwYWVGG` (`slug: hidden-island`)
* **Base Workspace Directory:** `D:\Agentika\GlueSticks-agentika` (Mapped to `d:\Hackathons\GlueSticks-agentika`)
* **GitHub Repository:** [`https://github.com/anithepani/GlueSticks-agentika.git`](https://github.com/anithepani/GlueSticks-agentika.git)
* **Model Used in Session:** `deepseek-v4-flash` via `agentrouter` (high variant)
* **Token Consumption:**
  * **Input Tokens:** 1,762,882
  * **Output Tokens:** 201,158
  * **Reasoning Tokens:** 69,149
  * **Cache Read:** 41,354,752 tokens
* **Session Lifetime:** 2026-10-16T18:28:59.251Z to 2026-10-16T21:45:42.480Z (Session closed around 02:45 AM PKT on 17 Oct 2026)
* **Competition Deadline:** 17 Oct 2026, 12:45 PM PKT (No code or deployment changes permitted after this cutoff).

---

## 2. Project Executive Summary

* **Project Name:** **Witness**
* **Hackathon:** *Agentika 2.0* (NaSCon'26, FAST NUCES Islamabad).
* **Theme:** **"Human + AI: Better Together"** (Core rule: AI must never be fully autonomous; the human step must be architectural/structural, not cosmetic).
* **Domain / Framing:** High-stakes public benefits eligibility screening (BISP-inspired synthetic social protection rules for Pakistan).
* **Deployment Target:** **Alternate Clouds** ([clouds.alternatefutures.ai](https://clouds.alternatefutures.ai)) on decentralized Akash compute. Local-only or Vercel/Railway deployments disqualify.
* **Current Live Service:**
  * **Live URL:** [https://alternate-echo-whale-5578-github-app.alternatefutures.ai](https://alternate-echo-whale-5578-github-app.alternatefutures.ai)
  * **Project ID:** `witness-agentika`
  * **Service ID:** `alternate-echo-whale-5578-github` (`cmvbc3e5706exe41rs9g87kmn`)
  * **Repository HEAD:** `8c0478e` (`feat(ui): System & Adapters view`)
  * **Deployed image:** `8c0478e9dbb6` (`8c0478e`, `v0.4.0`) — verified 17 Oct 2026, 07:47 PKT
  * **Evaluation Gate:** 55/55 expectations passed (`all_passed: true`, `no_auto_deny: true`)
  * **Last verified:** 17 Oct 2026, 07:40 PKT — `/health` 200, all GET endpoints 200,
    `seed_source: files:/app/data/cases`, audit `sqlite` (requested `postgres`, degraded).

> Status numbers below (rubric scores, live commit, "data/ not copied") are a **snapshot at
> the end of the first session** and are kept for history. The block above is the current,
> re-verified state.

---

## 3. Architecture & Contract Matrix

Witness runs as a single FastAPI service listening on `PORT=8000` inside a Docker container. Every subsystem is behind an environment variable flag (Ports & Adapters pattern):

| Flag | Configured Values | Active Default | Role |
|---|---|---|---|
| `READER` | `text`, `pdf` | `pdf` | Ingests raw text or extracted PDF pages |
| `EXTRACTOR` | `fixture`, `labels`, `llm` | `llm` | Pulls facts with verbatim quotes & document spans |
| `VERIFIER` | `det`, `llm` | `llm` | Audits recommendation; abstains on contradictions/missing facts |
| `AUDIT` | `sqlite`, `postgres` | `postgres` (degrades to `sqlite`) | Append-only SHA-256 hash-chained ledger |
| `LLM_PROVIDER` | `groq`, `gemini` | `groq` | Free inference provider (`llama-3.3-70b-versatile`) |
| `WITNESS_STRICT` | `0`, `1` | `1` | Startup gate: refuses to serve if evaluation tests fail |
| `WITNESS_SLA_HOURS` | Number | `24` | Case queue aging and SLA breach indicator |

---

## 4. Completed Phases & Deliverables

### Stage 0: Foundation & First Deploy
* Basic FastAPI application, Dockerfile, requirements, and health check.
* Established Alternate Clouds deployment pipeline on branch `main`.

### Stage 1: Walking Skeleton & Core HITL Pipeline
* **Synthetic Cases:** 5 seeded demo cases in [`data/cases/`](https://github.com/anithepani/GlueSticks-agentika/tree/main/data/cases/) with static embedded fallbacks in [`app/embedded.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/embedded.py).
* **Deterministic Rules:** [`app/adapters/rules_pmt.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/rules_pmt.py) checks rule passes/fails deterministically without LLM hallucinations.
* **Deterministic Verifier:** [`app/adapters/verifier_det.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/verifier_det.py) enforces abstention (`NEEDS_REVIEW`) on missing mandatory fields or contradictions.
* **Immutable Audit Ledger:** [`app/adapters/audit_sqlite.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/audit_sqlite.py) hash-chains human approvals/denials. Tampering sequence or content breaks the chain (`/api/audit/verify`).
* **Human Gate:** Decisions require mandatory written reasons; double-decisions and automated rejections are blocked.

### Stage 2: Grounded Fact Extraction & Adversarial Verifier
* **LLM Extractor:** [`app/adapters/extractor_llm.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/extractor_llm.py) extracts key-value pairs with exact verbatim quotes.
* **Verbatim Verification:** Deterministic matcher ensures extracted quotes exist identically in the source text; invented quotes are stripped.
* **Adversarial LLM Verifier:** [`app/adapters/verifier_llm.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/verifier_llm.py) re-audits citations. Can add abstentions/flags, but cannot clear a deterministic failure.
* **Safe Fallbacks:** Degrades seamlessly to label/fixture extractors if LLM keys are unset or rate-limited.

### Stage 3: Runtime Intake & UI Decision Desk
* **Intake API:** `POST /api/cases` takes plain text or structured JSON packets.
* **Decision Desk UX:** [`app/static/index.html`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/static/index.html) single-page dashboard featuring evidence panels, conflict highlights, rule checklists, and a `request_info → resubmit` loop.

### Stage 4: Hardening, Breadth & Platform Integrations (P1–P7)
* **P4 — Policy Traceability:** Expanded to **7 statutory clauses** in [`data/policy/rules.md`](https://github.com/anithepani/GlueSticks-agentika/tree/main/data/policy/rules.md) and [`app/policy.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/policy.py). Each rule row in the UI cites its specific clause.
* **P5 — Fail-Closed Evaluation Gate & Tamper Demo:** 
  * Startup test suite verifies 55 golden cases and invariant tests.
  * `POST /api/audit/tamper-demo` demonstrates cryptographic ledger failure on an isolated temporary clone.
* **P1 — Resilient Multi-Service Postgres:** [`app/adapters/audit_postgres.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/audit_postgres.py) with [`app/adapters/resilient.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/resilient.py) (`ResilientAudit`), automatically falling back to SQLite if Postgres is unreachable.
* **P3 — PDF Intake:** [`app/adapters/reader_pdf.py`](https://github.com/anithepani/GlueSticks-agentika/tree/main/app/adapters/reader_pdf.py) using `pypdf` for page-aware extraction.
* **P6 — Case Assignment & SLA Aging:** Caseworker assignments, due timestamps, and queue SLA breach indicators.
* **P7 — Observability:** Request tracing via `x-request-id`, structured JSON access logs, and `/api/metrics`.

---

## 5. Failed Implementations, Glitches, & Root Causes

| # | Event / Failure | Phase & Time | Root Cause | Resolution / Status |
|---|---|---|---|---|
| **1** | **Initial Deploy 404 (nginx)** | Stage 0 (Msgs 34–77, ~12:17 AM) | Alternate Clouds gateway routes subdomains strictly to ports declared under **Settings → Ports**. Uvicorn was listening on `8000`, but container ports were empty. | User added port `8000` (`http`), rebuilt and deployed. |
| **2** | **Provider Ingress 404** | Stage 3 (Msgs 162–193, ~01:20 AM) | Container was healthy on `0.0.0.0:8000` and internal k8s service responded `200 OK`, but public domain returned 404. Cause: Akash provider edge ingress routing corruption. | Triggered fresh lease deployment via `acc services deploy`. Survived transient on-chain `code 32` error on retry. |
| **3** | **Live Postgres Link Network Partition** | Stage 4 (Msgs 281–309, ~02:25 AM) | `witness-db` and app were scheduled on different Akash providers (CIDRs `10.43.x.x` vs `10.233.x.x`). Internal `.internal` DNS is cluster-local and cannot bridge distinct Akash providers. External NodePort 5432 was also blocked. | Handled gracefully: `ResilientAudit` caught DNS resolution error and automatically degraded to SQLite. Surfaced as `audit_degraded: true` in `/api/adapters`. |
| **4** | **Confidential Compute / TEE Deploy (`CVM failed`)** | Stage 4 Stretch (Msgs 310–315, ~02:35 AM) | Duplicate service `witness-tee` deployed with `--confidential` failed twice with `CVM failed`. Cause: No Akash provider had available hardware TEE nodes (AMD SEV/Intel TDX) to bid. | Timeboxed and safely abandoned to protect the live service. Documented in `DEPLOY.md`. |

---

## 6. Current System Health & Endpoints

All 6 test suites pass cleanly locally:
```powershell
python tests/test_gate.py      # PASS: Evaluation gate & tamper demo
python tests/test_intake.py    # PASS: Ingestion & golden eval suite
python tests/test_llm.py       # PASS: LLM adapters & fallback behaviors
python tests/test_ops.py       # PASS: Observability & SLA assignment
python tests/test_pdf.py       # PASS: PDF reader & text extraction
python tests/test_seed.py      # PASS: Embedded cache synchronization
```

Active Production Endpoints:
* `GET /health`: System status, gate status (`all_passed: true`), stage, active adapters.
* `GET /api/cases`: Seeded and submitted applicant queue with statuses and SLA flags.
* `GET /api/adapters`: Active runtime adapters and audit degradation status.
* `GET /api/eval`: Detailed evaluation breakdown across the 55 golden invariants.
* `GET /api/audit/verify`: Cryptographic verification of the current audit hash chain.
* `POST /api/audit/tamper-demo`: Demonstrates ledger tampering and detection.
* `GET /api/metrics`: In-memory request counters and latency statistics.

---

## 7. Remaining Work & What to Proceed With Next

The application code is complete and stable. At the end of the first session the rubric
self-assessment was ~89–91/100 (historical; see the current status block at the top). The
remaining points are almost exclusively in the **mandatory submission deliverables** due
before **12:45 PM PKT**:

### Immediate Priority Tasks (Deliverables)
1. **2–3 Minute Demo Video:**
   * Script a concise walkthrough:
     1. Show Case 1 (Standard Pass, Human Approves).
     2. Show Case 3 & 4 (Abstention on Contradiction & Missing Info; system refuses to auto-deny).
     3. Show Case 5 (Rule Failure; mandatory human review).
     4. Show `/api/audit/tamper-demo` (Tamper-evident hash chain validation).
     5. Show PDF ingestion and 7-clause policy traceability.
2. **Submission PDF Document ("Where the Human Comes In"):**
   * Write and export the explanatory document showing how the human gate is structural (in-pipeline gate) rather than cosmetic.
3. **Proof Screenshots:**
   * Capture live deployment URL, clean health check, 55/55 eval gate, and tamper demo outputs.
4. **Human LinkedIn Post:**
   * Drafted and posted by the team (per hackathon rules, must be human-authored).
