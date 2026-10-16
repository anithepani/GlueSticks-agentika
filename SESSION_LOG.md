# Witness ΓÇö Session Log

Complete history of the build session for **Witness, a human-in-the-loop decision desk**,
built for the *Agentika 2.0* hackathon (NaSCon'26, FAST NUCES Islamabad; theme
**"Human + AI: Better Together"**) and deployed on **Alternate Clouds**.

> Secrets shown in terminal output during debugging are **redacted** below
> (`<redacted>`). Rotate the Groq key and the database password after the event.

---

## 1. Starting point

The repo `anithepani/GlueSticks-agentika` already contained a **Stage 0 skeleton**:

- `app/main.py` ΓÇö FastAPI with `/health`, `/api/info`, `/` (static page), PORT-aware.
- `app/static/index.html` ΓÇö landing page polling `/health`.
- `Dockerfile`, `Procfile`, `DEPLOY.md`, `README.md`, `.env.example`, `.gitignore`.
- Commit `2692f6b` ("Stage 0: skeleton, /health, static landing").

Live deploy existed in name but the public URL returned **`404 Not Found ΓÇö nginx`**.
The goal was to advance the project stage-by-stage (always deployable) and keep it
deployed on Alternate Clouds for the submission deadline (12:45 PM).

---

## 2. Diagnosing the first 404

### Evidence gathered

- `https://alternate-echo-whale-5578-github-app.alternatefutures.ai/health` ΓåÆ `404` with an
  nginx HTML body and an `x-af-trace-id` header (so the request reached the AF gateway).
- Control probe on a **non-existent** subdomain ΓåÆ `404` JSON
  `{"error":"Not Found","message":"No service found for this app subdomain."}`
- The real subdomain returned **nginx HTML**, not that JSON ΓåÆ the gateway knew the
  service but had no working upstream.

### Dashboard facts (pasted by the user)

- Status: Active; ~$0.0022/hr; port `8000`; FastAPI; branch `main`; build succeeded.
- Logs showed `Uvicorn running on http://0.0.0.0:8000`.
- **Settings ΓåÆ Ports (container ports to expose) was empty.**

### Fix #1 (worked)

Added a container port in the dashboard: **`8000` / protocol `http` / Public blank ΓåÆ Save
ΓåÆ Redeploy**. The site then loaded and `/health` returned Stage 0/1 data.

Documented in `DEPLOY.md` (still valid for the "empty Ports list" case).

### The two AF hostnames

`acc services info` later revealed each service has **two** hostnames:
`<slug>-app.alternatefutures.ai` and `<slug>-agent.alternatefutures.ai`. Both were probed
and behaved the same.

---

## 3. `/api/cases` was empty ΓåÆ embedded fallbacks

After Stage 1 was built, the live app returned `{"cases":[],"stats":{"total":0}}` ΓÇö the
build did **not** copy the `data/` directory into the image.

**Fix:** `app/seed_cases.py` gained an **embedded fallback** (`DEFAULT_CASES`) and a
`/api/diag` endpoint reporting the seed source. Later this was generalized:
`tools/embed.py` generates `app/embedded.py` from `data/`, and `tests/test_seed.py`
fails if it is stale. The same fallback pattern was applied to the policy text and the
golden expectations. Result: the service works even with no `data/` directory
(`/api/diag` reports `seed_source: embedded` live).

---

## 4. Stages built

| Commit | Stage | Summary |
|---|---|---|
| `2692f6b` | 0 | skeleton, `/health`, static landing |
| `9ba8af1` | 1 | walking skeleton: 5 seeded cases, deterministic rules, abstaining verifier, human decision gate, hash-chained audit |
| `ff0695a` | ΓÇö | embedded seed fallback + `/api/diag` |
| `99df161` | 2 | key-gated LLM extractor + LLM verifier with deterministic fallback |
| `adca7b3` | 3 | runtime intake (labels extractor), `request_info ΓåÆ resubmit`, evaluation gate, embedded policy/golden, richer UI |
| `e416889` | ΓÇö | docs: live deployment + provider-ingress root cause + CLI cheat sheet |
| `9a51ea6` | 4 | 7-clause policy traceability, PDF intake, Postgres audit adapter, fail-closed gate, tamper demo, assignment/SLA, observability |
| `7f8df3f` | ΓÇö | evaluation gate scores the deterministic path (independent of LLM) |
| `7aec20d` | ΓÇö | report audit degradation explicitly when a linked DB is unreachable |
| `e7904e2` | ΓÇö | docs: confidential/TEE deploy attempt + outcome |

### Stage 1 ΓÇö walking skeleton

- `app/models.py` ΓÇö `Document`, `Fact`, `Citation`, `RuleResult`, `Verification`,
  `Recommendation`, `Decision`, `Case`, status/outcome constants.
- `app/interfaces.py` ΓÇö `Reader`, `Extractor`, `RulesEngine`, `Verifier`, `AuditLog` protocols.
- `app/adapters/` ΓÇö `reader_text`, `extractor_fixture`, `rules_pmt`, `verifier_det`,
  `audit_sqlite`.
- `app/pipeline.py` ΓÇö intake ΓåÆ extract ΓåÆ rules ΓåÆ verify ΓåÆ recommend.
- `app/store.py` ΓÇö in-memory store, idempotent seeding, the human decision gate.
- `data/cases/*.json` (5 synthetic packets) + `data/policy/rules.md`.
- API: `/api/cases`, `/api/cases/{id}`, `POST /decision`, `/api/cases/{id}/audit`,
  `/api/audit/verify`, `POST /api/reseed`, `/api/stats`.
- **Invariant:** the pipeline can reach `VERIFIED`/`NEEDS_REVIEW` but **never** auto-denies.

The 5 seeded cases demonstrate: eligible, missing evidence (UNKNOWN), contradiction,
ungrounded ("invented") quote, and rule failure ΓÇö the last four all escalate to a human.

### Stage 2 ΓÇö LLM adapters

- `app/adapters/llm_client.py` ΓÇö stdlib-only Groq/Gemini client returning strict JSON.
- `app/adapters/extractor_llm.py` ΓÇö asks for a value **plus the exact quote**; the quote is
  then grounded verbatim. An invented quote yields **no citation**, so the verifier abstains.
- `app/adapters/verifier_llm.py` ΓÇö re-reads each citation; it can only make the verdict
  **more** cautious (add an abstain), never clear a deterministic failure.
- `app/adapters/resilient.py` ΓÇö `ResilientExtractor`/`ResilientVerifier` fall back on failure.
- Flags `EXTRACTOR=llm`, `VERIFIER=llm`; with no key (or on error) the deterministic path is used.

### Stage 3 ΓÇö intake, resubmit, evaluation

- `app/adapters/extractor_labels.py` ΓÇö deterministic label-aware extractor for pasted text
  (grounds each fact by the matched substring).
- `POST /api/cases` ΓÇö intake a case and run the pipeline live.
- `POST /api/cases/{id}/resubmit` ΓÇö after `request_info`, append evidence and re-run.
- `app/evaluation.py` + `data/eval/golden.json` ΓÇö the evaluation gate (grounding rate,
  abstain rate, per-rule agreement, `no_auto_deny` invariant).
- UI panels: new-case intake, conflicting-evidence view, policy view, evaluation view.

### Stage 4 ΓÇö hardening and breadth

- **7 policy clauses** (`Clause 1..7`) with traceable rule ids; every `RuleResult` carries
  `policy_ref`, shown in the UI. New rules: `ASSET_LAND`, `BANK_BALANCE`.
- **PDF intake** (`READER=pdf`, `pypdf`) ΓÇö pages become documents (`<doc_id>p<n>`); text
  packets still pass through. Size/page caps.
- **Postgres audit** (`AUDIT=postgres`, `psycopg[binary]`) with the same hash-chain
  semantics, plus a `ResilientAudit` SQLite fallback.
- **Fail-closed gate** ΓÇö `WITNESS_STRICT=1` makes the app refuse to serve if the gate fails;
  `/health` reports the gate.
- **Tamper demo** ΓÇö `POST /api/audit/tamper-demo` tampers with an **in-memory copy**, shows
  the chain break, and re-verifies the untouched ledger.
- **Assignment + SLA/aging** ΓÇö `POST /api/cases/{id}/assign`, queue aging, SLA breach flag.
- **Observability** ΓÇö `x-request-id` middleware, JSON access logs, `/api/metrics`.
- `tools/embed.py` + `app/embedded.py` ΓÇö generated embedded copies of cases/golden/policy.

---

## 5. The second 404 ΓÇö real root cause

After a dashboard rebuild the URL regressed to `503`, then to nginx `404`. Re-adding the
port did **not** help. Using the `acc` CLI (`npx @alternatefutures/acc`) we got
`services info`, `logs`, and non-interactive `ssh --command`.

### Evidence from inside the container

- `/proc/1/cmdline` ΓåÆ `sh -c uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- `/proc/net/tcp` ΓåÆ one listener on `0.0.0.0:8000` (`1F40`).
- `http://127.0.0.1:8000/health` ΓåÆ **our JSON, 200**.
- `http://10.233.44.135:80/health` (the k8s Service) ΓåÆ **our JSON, 200**.
- Env showed `PORT=8000`, plus the k8s Service exposed on port **80** ΓåÆ forwards to 8000.

So the app and Kubernetes routing were healthy. The break was the **Akash provider
ingress** in front.

### Fix #2 (worked)

A forced fresh deployment onto a **new lease/provider**:

```powershell
npx -y @alternatefutures/acc services -p witness-agentika deploy <service-id> -y
```

The first attempt failed on-chain with `lease-create: tx rejected on-chain (code 32)`
(and briefly left the service stopped); a retry succeeded and the URL went green.

**Key lesson recorded:** nginx `404` on a live URL with our app running and listening is a
**provider-ingress** problem, fixed by a fresh deploy ΓÇö **not** a port-setting problem.

---

## 6. Deployment operations learned

- Pushing to GitHub does **not** rebuild or redeploy; a build is explicit.
- Flow: `services rebuild <id>` ΓåÆ wait for the new image tag ΓåÆ `services deploy <id> -y`.
- Builds reuse a builder volume; `rebuild` can fail with
  `Fly rejected the builder machine request (HTTP 412): volume already claimed` ΓÇö retry.
- Deploys can fail transiently (`code 32`) ΓÇö retry.
- `acc ssh <id> --command` execs **argv directly (no shell)**; use single commands
  (`cat /proc/net/tcp`) or space-free Python
  (`python -c print(__import__('urllib.request').request.urlopen('http://127.0.0.1:8000/health').read())`).
- `acc services -p <project>` avoids interactive project prompts.
- GitHub create cannot take `--region`/`--confidential`; those must be applied on a redeploy.

---

## 7. Postgres (durable ledger) ΓÇö wired, but degraded live

- Created the managed Postgres template:
  `services create --kind template --template postgres --name witness-db` (password generated at runtime).
- Linked it: `services link alternate-echo-whale-5578-github witness-db --alias DATABASE`
  ΓåÆ injected `DATABASE_URL`, `PGHOST`, ΓÇª into the app.
- Set `AUDIT=postgres`. `psycopg` installed (3.3.6) and the env was correct, **but** the app
  failed to resolve `witness-db.witness-agentika.internal`.
- Diagnosis: app pod CIDR `10.43.x`, DB pod CIDR `10.233.x` ΓåÆ **different clusters**.
  Service linking is **cluster-local**; a redeploy of the DB into `eu` did not co-locate them.
- The DB's port `5432` is not publicly reachable either (Cloudflare fronts only HTTP;
  the Akash NodePort is not exposed).

**Outcome:** Witness **degrades to the embedded SQLite ledger** instead of failing, and
reports it honestly at `/api/adapters`
(`audit_requested`, `audit_active`, `audit_degraded`, `audit_note`). Documented in `DEPLOY.md`.

---

## 8. Confidential / TEE ΓÇö attempted, not viable

- Created a duplicate service (`witness-tee`) so the proven URL was never at risk.
- `services deploy witness-tee --confidential -y` failed twice with **`CVM failed`**
  (no viable confidential VM offer).
- Abandoned per the timebox; documented as a supported path, not a live one.

---

## 9. Final live state

- **URL:** `https://alternate-echo-whale-5578-github-app.alternatefutures.ai`
- **Version:** `0.4.0` (image tag `e7904e2c1cae`), service `cmvbc3e5706exe41rs9g87kmn`.
- Verified live:

| Endpoint | Result |
|---|---|
| `/health` | `status ok`, `gate.all_passed true` |
| `/api/adapters` | `extractor llm(fallback:fixture)`, `verifier llm(fallback:det)`, `llm_configured true`, `audit_degraded true` |
| `/api/cases` | 5 seeded cases with `assignee`, `age_minutes`, `sla_breached` |
| `/api/eval` | `all_passed true`, grounding `0.971`, abstain `0.6`, `no_auto_deny true` |
| `/api/metrics` | request counts, latency, request IDs |
| `/api/audit/verify` | chain intact |

> Cosmetic: `/health` reported `stage 3` because the dashboard still had
> `WITNESS_STAGE=3`; the app default is now `4`. Bumping it applies at the next deploy.

---

## 10. Local test suites (all green)

Pure-Python, no network, no API key required:

```powershell
.\.venv\Scripts\python.exe tests\test_seed.py     # embedded data == data/ (and generator in sync)
.\.venv\Scripts\python.exe tests\test_llm.py      # grounded extraction, abstain-only verifier, fallbacks
.\.venv\Scripts\python.exe tests\test_intake.py   # labels extractor, intake, resubmit, evaluation gate
.\.venv\Scripts\python.exe tests\test_gate.py     # fail-closed gate, tamper detection, strict mode
.\.venv\Scripts\python.exe tests\test_pdf.py      # hand-built PDF -> grounded -> eligible
.\.venv\Scripts\python.exe tests\test_ops.py      # assignment, SLA/aging, metrics, request IDs
```

Additional throwaway integration harnesses (HTTP-level, no-data mode, LLM-flag fallback)
were also run during the session and passed.

---

## 11. Architecture (final)

```
app/
  main.py            FastAPI app, middleware, all routes
  config.py          env flags, adapter wiring, describe_adapters()
  models.py          typed contracts + status constants
  interfaces.py      Reader / Extractor / RulesEngine / Verifier / AuditLog
  pipeline.py        intake -> extract -> rules -> verify -> recommend
  store.py           in-memory case store, decision gate, assignment, SLA
  evaluation.py      the evaluation gate (deterministic path)
  embedded.py        GENERATED from data/ (cases, golden, policy)
  policy.py          re-exports embedded policy
  seed_cases.py      case loading with embedded fallback
  observability.py   metrics + JSON logs
  tamper_demo.py     tamper-evident ledger demo
  adapters/
    reader_text.py reader_pdf.py
    extractor_fixture.py extractor_labels.py extractor_llm.py
    rules_pmt.py
    verifier_det.py verifier_llm.py
    audit_sqlite.py audit_postgres.py
    resilient.py llm_client.py
data/
  cases/*.json  eval/golden.json  policy/rules.md
tools/embed.py     regenerates app/embedded.py from data/
tests/*.py
```

---

## 12. Final API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, version, stage, evaluation gate |
| GET | `/api/info` | service metadata |
| GET | `/api/adapters` | active adapters, LLM status, audit requested/active/degraded |
| GET | `/api/policy` | rule set Markdown (file or embedded) |
| GET | `/api/cases` | officer queue + stats (incl. unassigned, SLA) |
| POST | `/api/cases` | intake a case (text or PDF) and run the pipeline |
| GET | `/api/cases/{id}` | full case (facts, citations, rules, verification) |
| POST | `/api/cases/{id}/decision` | human decision `{officer, action, reason}` |
| POST | `/api/cases/{id}/resubmit` | supply evidence after `request_info` |
| POST | `/api/cases/{id}/assign` | assign a case to an officer |
| GET | `/api/cases/{id}/audit` | audit entries for a case |
| GET | `/api/audit/verify` | recompute the hash chain |
| POST | `/api/audit/tamper-demo` | show a forged copy breaking the chain |
| GET | `/api/eval` | run the evaluation gate |
| GET | `/api/metrics` | request counts, latency, gate summary |
| POST | `/api/reseed` | idempotent reseed |
| GET | `/api/diag` | seed source + gate |

---

## 13. Environment variables (live demo build)

```
PORT=8000
WITNESS_STAGE=4
READER=pdf
EXTRACTOR=llm
VERIFIER=llm
LLM_PROVIDER=groq
GROQ_API_KEY=<redacted>
GROQ_MODEL=llama-3.3-70b-versatile
AUDIT=postgres
WITNESS_STRICT=1
WITNESS_SLA_HOURS=24
```

---

## 14. Rubric self-assessment (at end of session)

| Criterion | Max | Score | Notes |
|---|---|---|---|
| Technical execution / reliability | 25 | ~23 | fail-closed gate, 6 suites, request IDs, graceful DB degradation |
| Usefulness / impact | 20 | ~18 | 7 clauses, PDF intake, SLA/assignment, policy traceability |
| Theme alignment | 15 | ~14 | the human gate is structural and audited |
| Creativity / uniqueness | 15 | ~13 | grounded extraction, abstention, tamper demo, attested path |
| Automation depth / integration | 15 | ~12 | Postgres service + adapter + link (degraded), PDF parse, LLM adapters |
| UX / presentation | 10 | ~9 | intake/conflict/policy/eval panels, SLA badges |
| **Total** | **100** | **~89** | |

---

## 15. Known limitations

- **Live ledger is SQLite**, not Postgres: AF service linking is cluster-local and the two
  services landed on different clusters. The Postgres adapter exists and degrades safely.
- **TEE not live**: `CVM failed` on confidential placement; documented as a supported path.
- `data/` is not copied into the image; the embedded fallbacks cover it.
- The seeded rule set is **simplified, synthetic and BISP-inspired** ΓÇö not official policy.
- The intake label extractor assumes the standard form labels; anything else becomes
  `UNKNOWN` and correctly escalates to a human.
- A manual tamper of the live ledger is only detectable via `/api/audit/verify` and
  `POST /api/audit/tamper-demo` (which operates on a copy).

---

## 16. Remaining work

- **Deliverables:** proof screenshots, a 2ΓÇô3 minute demo video (no keys on screen), and the
  PDF explaining where the human comes in.
- Rotate the **Groq API key** and the **Postgres password** after the event (both appeared
  in terminal output during debugging).
- Optional: bump the dashboard `WITNESS_STAGE` to `4` (applies at the next deploy).

---

## 17. Session 2 ΓÇö continuation (audit, fixes, verification)

Repository was moved to `D:\Hackathons\GlueSticks-agentika` (was `D:\Agentika\...`); branch
`main`, base commit `e7904e2`. A fresh `.venv` (Python 3.10.11) was created because none was
present. All six original suites passed at baseline.

### Confirmed defects fixed

| # | Defect | Root cause | Fix |
|---|---|---|---|
| 1 | Provider key could leak into API/UI | Gemini key was placed in the request **URL**; generic transport errors were passed through as `str(exc)` into verification notes | Key sent as `x-goog-api-key` header, `redact()` applied to every error string, `api_key` hidden from the dataclass repr |
| 2 | Concurrent human decisions could double-apply | `CaseStore` had no locking; status check and mutation were not atomic (TOCTOU) | `threading.RLock` around seed/add_case/resubmit/assign/decide/reseed/reads |
| 3 | Intake id could collide with the persistent ledger | `_next_intake_id` only considered in-memory cases; after a restart/reseed the ledger still held `INTK-0001`, so a new case reused it and its `pipeline_run` was suppressed as a duplicate | Counter now unions in-memory ids with `audit.case_ids()` (new method on SQLite/Postgres/Resilient) |
| 4 | Audit errors not surfaced | `verify()` returned no ledger name; resilience degradation was inferred only from the adapter name | `ledger` added to verdicts; `audit_runtime_degraded` + accurate `audit_degraded`/`audit_note` in `/api/adapters` |
| 5 | Unknown-case audit returned 200 | Missing existence check | `GET /api/cases/{id}/audit` now 404s for unknown cases |
| 6 | SQLite lock contention risk | No busy timeout / WAL | `timeout=30`, `PRAGMA busy_timeout`, `journal_mode=WAL` |
| 7 | `data/` missing from image | `Dockerfile` copied only `app/` | `COPY data ./data` added (embedded fallback still present) |
| 8 | Abstention overrides invisible | Decision payload did not distinguish an override | `overrode_abstention` recorded in the audit entry |
| 9 | Tamper demo crashed on an empty ledger in the UI | Frontend assumed `tampered` was non-null | Guard added |
| 10 | Stale module docstring in `main.py` | "Stage 1" text | Rewritten |

### New tests

`tests/test_regressions.py` (all passing): 8-thread concurrent decision (exactly one wins,
one ledger entry, chain intact); intake-id uniqueness across reseed with correct audit
linkage; provider-key non-leakage (URL/header/repr/error redaction); abstention-override
recording; invalid transition / duplicate decision / malformed intake / unknown case
rejection; tamper demo on an empty ledger.

### Persistence ΓÇö verified locally

Two separate `uvicorn` processes sharing one `AUDIT_DB`:

```
run1: decision -> APPROVED; chain ok, 6 entries, head 48a29db2...
      [stopped]
run2: cases recreated (5), decided 0; case1 in-memory VERIFIED (decision cleared)
      case1 ledger events: ['pipeline_run','human_decision']   <- persisted
      chain ok, 6 entries, head 48a29db2...                    <- identical head
```

Conclusion: **SQLite survives a process restart, not a redeploy**; in-memory case state is
never durable. A verifying chain proves integrity, not durability.

### Postgres ΓÇö re-verified

The live app still reports `audit_requested: postgres`, `audit_active: sqlite`,
`audit_degraded: true` ΓÇö i.e. the linked database remains unreachable from the app's
cluster (app `10.43.x` vs database `10.233.x`). Fixing it needs co-located placement, which
requires an authenticated CLI or the dashboard. The SQLite fallback is preserved.

### CVM / TEE ΓÇö status

Not re-attempted: the CLI in this workspace is **unauthenticated**
(`acc whoami --json` ΓåÆ `{"authenticated": false}`) and unauthenticated commands start an
interactive login and hang. The two prior `CVM failed` attempts are documented; no third
attempt was made with an unchanged configuration. Requirements for a retry and the
attestation command are recorded in `DEPLOY.md`. No TEE claim is made.

