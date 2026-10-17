# Deploying Witness on Alternate Clouds

Alternate Clouds routes to **one port**. The app reads `PORT` (default `8000`) and the
Dockerfile `EXPOSE`s `8000`, so the dashboard port must be **8000**.

Two places carry the port and **both** matter:

1. **Source** tab — the framework port (Nixpacks detected `8000`).
2. **Settings → Ports** — the *container port to expose*. This must list `8000`
   (protocol `http`, Public left blank). **If this list is empty the public URL
   returns an nginx `404 Not Found` even though the app is running and healthy.**

Golden rule: **set variables → Rebuild → Deploy**. Pushing to GitHub does *not* update the
live app on its own.

---

## 1. Push the code

```powershell
cd D:\Agentika\GlueSticks-agentika
git add .
git commit -m "Stage 0: skeleton, /health, static landing"
git push origin main
```

## 2. Web app flow (the event-mandated path)

1. Sign in at <https://clouds.alternatefutures.ai> (email → code, passwordless).
2. Create or open a **project**.
3. **Deploy GitHub Repo** → **Install GitHub App** → *Only select repositories* →
   `anithepani/GlueSticks-agentika` → **Save**.
4. Enter a **Project Name**.
5. **Source** tab → branch `main` → **Connect & Build**.
6. **Overview** tab → set a **Budget Cap** of `$0.50`–`$1.00`.
7. **Settings → Environment Variables** → add:
   ```
   PORT=8000
   ```
   (Keys for Stage 2+ go here later: `GROQ_API_KEY`, `GEMINI_API_KEY`. Never commit them.)
8. Confirm the **port** is `8000`.
9. Click **Rebuild**, wait for a successful build, then click **Deploy**.
10. Open `https://<your-slug>-app.alternatefutures.ai` and check `…/health` returns
    `{"status":"ok", ...}`.

## 3. CLI alternative
```powershell
npm install -g @alternatefutures/acc
acc login --email
acc projects create --name witness
acc services create --kind github --repo anithepani/GlueSticks-agentika --branch main --port 8000 --env PORT=8000 --name witness -y
acc services list
acc services logs witness --tail 100
```

Redeploy after a new push:

```powershell
acc services rebuild witness
acc services deploy witness
```

### Live service (current)

| | |
|---|---|
| Project | `witness-agentika` (`cmvbc3drs06eue41rcjczutc9`) |
| Service | `alternate-echo-whale-5578-github` (`cmvbc3e5706exe41rs9g87kmn`) |
| URL | https://alternate-echo-whale-5578-github-app.alternatefutures.ai |
| Port | `8000` (the k8s Service in front is on `80` → `8000`; app listens on `8000`) |
| Status | **ACTIVE & HEALTHY** (HTTP 200 on `/health`, `/api/info`, `/api/adapters`, `/api/cases`, `/api/eval`, `/api/audit/verify`) |
| Deployed image | `ghcr.io/alternatefutures/2kteivvoteglelskxdyhg--anithepani-gluesticks-agentika:7e67c98933d5` (commit `7e67c98`) |

> **Operational note:** If the lease ever expires or encounters provider-ingress issues (`503 No active deployment` or `404 Not Found`), run `powershell -ExecutionPolicy Bypass -File tools/redeploy.ps1` from an authenticated terminal, or click **Rebuild → Deploy** in the Alternate Clouds web dashboard.

Working cheat sheet (no global install needed — `npx` works):

> **Prerequisite:** the CLI must be authenticated. If `npx -y @alternatefutures/acc whoami --json`
> returns `{"authenticated": false}`, run `npx -y @alternatefutures/acc login --email` first
> (browser/email code). Unauthenticated commands start an interactive login and **hang**, so
> always check `whoami --json` before scripted CLI use.

```powershell
npx -y @alternatefutures/acc whoami --json
npx -y @alternatefutures/acc services -p witness-agentika list
npx -y @alternatefutures/acc services -p witness-agentika info cmvbc3e5706exe41rs9g87kmn
npx -y @alternatefutures/acc services -p witness-agentika logs cmvbc3e5706exe41rs9g87kmn --tail 100
powershell -ExecutionPolicy Bypass -File tools/redeploy.ps1
```

`acc ssh --command` execs argv directly (no shell), so use single commands
(`cat /proc/net/tcp`) or space-free Python
(`python -c print(__import__('urllib.request').request.urlopen('http://127.0.0.1:8000/health').read())`).

## Environment variables for the demo build
Set these in **Settings → Environment Variables**, then **Rebuild → Deploy**:

```
PORT=8000
WITNESS_STAGE=4
READER=pdf
EXTRACTOR=llm
VERIFIER=llm
AUDIT=postgres
LLM_PROVIDER=groq
GROQ_API_KEY=<paste the key — never commit it>
GROQ_MODEL=llama-3.3-70b-versatile
WITNESS_STRICT=1
WITNESS_SLA_HOURS=24
```

`EXTRACTOR=llm`/`VERIFIER=llm` need no key to be safe: with no key — or if the API
errors or rate-limits mid-demo — Witness falls back to the deterministic
label/fixture path, so a case is never dropped. Check `GET /api/adapters` to confirm
what is live, and `GET /api/eval` to confirm the gate still passes.

## Docker architecture

- **Image build:** The application is built from `Dockerfile` on `python:3.12-slim`.
- **Port:** The container exposes port `8000` and starts `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
- **Context protection:** `.dockerignore` excludes `.venv`, `.git`, `.db`, `my-session.json`, `tests/`, and `tools/` from the build context sent to remote builders.
- **Service boundary:** The app runs as a single self-contained stateless container. PostgreSQL is NOT embedded in the container image; it is configured via environment variables (`DATABASE_URL`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`).

## Postgres audit ledger & platform networking

The SQLite ledger lives inside the container filesystem, which is **ephemeral**: it
survives a process restart (verified) but **not** a redeploy / container replacement
(no persistent volume is mounted). For a durable ledger, deploy the managed Postgres
template and link it:

```powershell
npx -y @alternatefutures/acc services create --kind template --template postgres --name witness-db -y
npx -y @alternatefutures/acc services -p witness-agentika link witness-db alternate-echo-whale-5578-github
npx -y @alternatefutures/acc services -p witness-agentika info cmvbc3e5706exe41rs9g87kmn
```

Linking injects the connection parameters into the app service (as `DATABASE_URL` /
`POSTGRES_URL` / `PG*`). Set `AUDIT=postgres`, **Rebuild → Deploy**, then confirm with:

- `GET /api/adapters` → `audit_active` is `postgres` or `postgres(fallback:sqlite)` and `audit_degraded` is `false`
- `GET /api/audit/verify` → `{"ok": true, "ledger": "postgres", ...}`

### Root cause of Postgres degradation on Alternate Clouds

1. **Service status:** Both `witness-db` and `alternate-echo-whale-5578-github` are running.
2. **Namespace isolation:** Alternate Clouds runs on Akash Network. Each service deployment is isolated into its own distinct Kubernetes tenant lease and namespace (e.g., app namespace `ulj7ldepe3ghk36ecsd711l3emb3kju20im68912c5f2i` vs db namespace `c5mrj2jl9jg59d3t9mqg3pk2qgimh4s95n2l0rtbmhruc`).
3. **DNS failure:** The linked hostname `witness-db.witness-agentika.internal` is cluster-local and cannot resolve across disparate Akash tenant namespaces (`socket.gaierror: [Errno -2] Name or service not known`).
4. **NetworkPolicy block:** Even direct connection between pod IPs (e.g., `10.233.89.133:5432`) times out (`errno 11`) due to Akash's tenant-isolation NetworkPolicy.
5. **Ingress limitation:** Database port 5432 is internal only; the platform's Cloudflare edge forwards only HTTP/HTTPS traffic.

### How Witness handles degradation

Because `try_postgres()` catches connection errors and `ResilientAudit` guards ledger writes:
- The service **never crashes** when Postgres is unreachable.
- The service **never drops a case** or suppresses audit records.
- `/api/adapters` truthfully reports `audit_requested: "postgres"`, `audit_active: "sqlite"`, `audit_degraded: true`, and `audit_note: "requested 'postgres' but running 'sqlite' (backend unreachable)"`.
- `/api/audit/verify` re-computes the tamper-evident hash chain on the active SQLite ledger (`ledger: "sqlite"`).

### Root cause (evidence, re-verified from the running deployments)

1. **Both services exist and are on different Akash providers.** The app runs on
   `akash1aaul837r7en7hpk9wv2svg8u78fdq0t2j2e82z` (`provider.h6i-dedicated.eu-se-1.digitalfrontier.so`,
   pod CIDR `10.42.x`); `witness-db` runs on `akash16yr3wxt97ae045a06kr3ycde9srcgpg8syjxxm`
   (`provider.zencloud.eu`, pod CIDR `10.233.x`). Two providers = two independent
   Kubernetes clusters with no shared private network.
2. **The link only injects environment variables.** AF's own glossary: *"Service link -
   a connection between two services in the same project that exposes the target's
   address to the source as environment variables."* It does not create a route. The
   injected `DATABASE_URL`/`PGHOST` is `witness-db.witness-agentika.internal`.
3. **That name cannot resolve outside the database's own cluster.**
   From the app: `socket.gaierror: [Errno -2] Name or service not known`. The same name
   is NXDOMAIN from the public internet. Inside the DB's cluster the service is
   `witness-db-np` (`10.233.47.52:5432`), and its DNS zone is the provider's own
   (`zc.internal`), which the app's cluster does not share.
4. **The declared public port is not actually reachable.** The template catalog lists
   Postgres as `5432 (public)`, but from the app (which has working egress - it reaches
   `api.groq.com:443`) and from the public internet, `provider.zencloud.eu:5432` times
   out, and `witness-db-app.alternatefutures.ai:5432` is unreachable (Cloudflare fronts
   HTTP only). No working public TCP endpoint exists for this deployment.
5. **AF has no provider pinning.** `acc services deploy` offers only `--region`; there is
   no flag to place a service on a specific provider or to attach two existing services
   to one private network. The only supported shared-network mechanism is a **composite
   template** (several services deployed *together*), which the docs state is **web-app
   only** and which builds a fixed template stack, not our custom app.

Conclusion: with the existing two separate services, there is **no supported way** to
give the app private access to `witness-db`. This is a platform placement limitation,
not a Witness defect and not a credential problem.

### Database state (checked, read-only)

`psql -U witness -d appdb -c '\dt'` in the DB container returns
`Did not find any relations.` - `appdb` has **no tables**, so the app has never written
and **there is no audit data at risk**. (The DB is otherwise healthy: `select(1)` -> `1`,
and it accepts local socket connections.)

### How Witness handles degradation

Because `try_postgres()` catches connection errors and `ResilientAudit` guards ledger writes:
- The service **never crashes** when Postgres is unreachable.
- The service **never drops a case** or suppresses audit records.
- `/api/adapters` truthfully reports `audit_requested: "postgres"`, `audit_active: "sqlite"`, `audit_degraded: true`, and an `audit_note`.
- `/api/audit/verify` re-computes the tamper-evident hash chain on the active SQLite ledger (`ledger: "sqlite"`).

### Options for cross-redeploy persistence (no external provider, no DB replacement)

Ordered by risk. **None is applied by default; each needs approval.**

1. **Keep SQLite (current state).** No production change. Honest, safe, but the ledger
   does not survive a redeploy. This is the recommended default until AF supports
   cross-provider linking.
2. **Ask AF support for same-provider placement.** The real fix is for the platform to
   place linked services on one provider (or expose a supported private endpoint). This
   is the only path that keeps the existing `witness-db`.
3. **Re-create the pair as one composite deployment.** A composite template shares one
   network, so the `.internal` name resolves. It creates a *new* Postgres (the current
   one is empty, so no data is lost) and is **web-app only**; it would not run our custom
   app image unless AF publishes a suitable composite. Needs approval and is not
   achievable with the current CLI.

Do **not** point `DATABASE_URL` at Neon/Supabase/RDS or any external provider: that is a
different architecture and was explicitly out of scope.


## Persistence — what actually survives (verified)

The audit ledger and the in-memory case store have **different** durability, and they
must not be conflated:

| Event | In-memory cases/decisions | Audit ledger (SQLite) |
|---|---|---|
| Process restart (same container, same `AUDIT_DB` on disk) | **Lost** — re-seeded fresh | **Retained** — same chain head, prior entries verified |
| Container replacement / rebuild / redeploy (ephemeral FS) | Lost — re-seeded fresh | **Lost** — new empty chain |
| External Postgres active and reachable | Lost — re-seeded fresh | **Retained** — survives restart and redeployment |

Evidence (verified):

```
run1: decision -> APPROVED; chain ok, 6 entries, head 48a29db2...
      [process stopped]
run2: cases recreated (5), decided 0; case1 in-memory VERIFIED (decision cleared)
      case1 ledger events: ['pipeline_run', 'human_decision']   <- persisted
      chain ok, 6 entries, head 48a29db2...                     <- identical head
```

So: a **hash chain that verifies proves integrity, not durability.** Durability across
redeployments requires the Postgres backend (or a mounted persistent volume).

## Confidential (TEE) deployment — attempted

`--confidential` must be set on a *redeploy* (a GitHub create cannot take it):

```powershell
npx -y @alternatefutures/acc services -p witness-agentika create --kind github ^
  --repo anithepani/GlueSticks-agentika --branch main --name witness-tee -y
npx -y @alternatefutures/acc services -p witness-agentika deploy witness-tee --confidential -y
npx -y @alternatefutures/acc services -p witness-agentika attest witness-tee
```

On this account the confidential redeploy failed twice with `CVM failed` (no viable
confidential VM offer at the time), so the TEE deployment is documented as a
**supported path, not a live one**. The proven `alternate-echo-whale-5578-github`
service is never used as the guinea pig for this: TEE is always tried on a
duplicate service so the submission URL stays up.

**Current status: DEFERRED (blocked on hardware).** Two attempts failed with `CVM failed`;
an unchanged configuration was not retried a third time. The failure is at provider
placement/start of a Confidential VM, not in Witness code.

TODO (CVM/TEE) - requirements for a future retry:
1. a region/provider that actually offers a TEE-capable node (`acc regions` shows
   availability), and
2. the same duplicate-service approach so the production URL is untouched.

The CLI is authenticated now, so the remaining blocker is hardware availability only.
If a retry succeeds, verify with `npx -y @alternatefutures/acc attest <tee-service-id>`
(add `--verify` if the installed CLI supports it). Until then, **do not claim TEE
protection or remote attestation.** The application never depends on confidential
compute.

---

## Troubleshooting (from the organizers' guide)

| Symptom | Fix |
|---|---|
| Cloudflare **502 Bad Gateway** | Port mismatch. Ensure the app listens on `8000` and the Source tab port is `8000`. |
| Live URL returns nginx **404 Not Found** while logs show the app started | The **provider ingress** is stale/misconfigured. The app is fine (verify inside the container with `acc ssh <id> --command "python -c print(__import__('urllib.request').request.urlopen('http://127.0.0.1:8000/health').read())"`). Fix: **force a fresh deployment** — `acc services deploy <id> -y` (new lease/provider), or the dashboard **Redeploy**. Editing Ports does *not* fix this. |
| Live URL returns nginx **404 Not Found** and Settings → Ports is empty | The container port was never exposed. Add `8000` / `http` (Public blank), Save, Redeploy. |
| Pushed but live app unchanged | Building and deploying are separate. **Rebuild**, then **Deploy**. |
| `503` with `{"error":"Service Unavailable","message":"This service exists but has no active deployment."}` | The lease is gone (provider died / lease closed / auto-stop). The service and URL still exist but nothing is running. **Recover:** `acc login --email` then `acc services -p witness-agentika rebuild cmvbc3e5706exe41rs9g87kmn` ΓåÆ `acc services -p witness-agentika deploy cmvbc3e5706exe41rs9g87kmn -y`; or the dashboard **Rebuild ΓåÆ Deploy**. Requiring a login is why this cannot be done by a non-interactive agent. |
| Live URL flips between `200`, nginx `404`, and `503` | Provider-ingress instability. Confirm the platform edge itself is healthy by probing a random subdomain (it returns `{"error":"Not Found",...}` when the edge works). Fix with a fresh deploy onto a new lease/provider. |
| Build succeeds, app crashes with `KeyError` | A required env var is missing. Add it under **Variables**, Rebuild, Deploy. |
| Anything else | Read the **Logs** tab first; then post logs (as text, keys removed) in the AF Discord `#support`. |
