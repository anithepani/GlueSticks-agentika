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
| Project | `witness-agentika` |
| Service | `alternate-echo-whale-5578-github` (`cmvbc3e5706exe41rs9g87kmn`) |
| URL | https://alternate-echo-whale-5578-github-app.alternatefutures.ai |
| Port | `8000` (the k8s Service in front is on `80` → `8000`; app must listen on `8000`) |

Working cheat sheet (no global install needed — `npx` works):

> **Prerequisite:** the CLI must be authenticated. If `npx -y @alternatefutures/acc whoami --json`
> returns `{"authenticated": false}`, run `npx -y @alternatefutures/acc login --email` first
> (browser/email code). Unauthenticated commands start an interactive login and **hang**, so
> always check `whoami --json` before scripted CLI use.

```powershell
npx -y @alternatefutures/acc services -p witness-agentika list
npx -y @alternatefutures/acc services -p witness-agentika info cmvbc3e5706exe41rs9g87kmn
npx -y @alternatefutures/acc services -p witness-agentika logs cmvbc3e5706exe41rs9g87kmn --tail 100
npx -y @alternatefutures/acc services -p witness-agentika rebuild cmvbc3e5706exe41rs9g87kmn
npx -y @alternatefutures/acc services -p witness-agentika deploy  cmvbc3e5706exe41rs9g87kmn -y
npx -y @alternatefutures/acc ssh cmvbc3e5706exe41rs9g87kmn --command "whoami"
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

## Postgres audit ledger (optional; prerequisites for cross-redeploy durability)

The SQLite ledger lives inside the container filesystem, which is **ephemeral**: it
survives a process restart (verified) but **not** a redeploy / container replacement
(no persistent volume is mounted). For a durable ledger, deploy the managed Postgres
template and link it:

```powershell
npx -y @alternatefutures/acc services create --kind template --template postgres --name witness-db -y
npx -y @alternatefutures/acc services -p witness-agentika link witness-db alternate-echo-whale-5578-github
npx -y @alternatefutures/acc services -p witness-agentika info cmvbc3e5706exe41rs9g87kmn
```

Linking injects the connection string into the app service (as `DATABASE_URL` /
`POSTGRES_URL`). Set `AUDIT=postgres`, **Rebuild → Deploy**, then confirm with:

- `GET /api/adapters` → `audit_active` is `postgres` or `postgres(fallback:sqlite)` and `audit_degraded` is `false`
- `GET /api/audit/verify` → `{"ok": true, "ledger": "postgres", ...}`

**In the current deployment this is NOT active.** The linked database landed on a
different provider/cluster, so the app runs the SQLite fallback and reports
`audit_degraded: true`, `audit_runtime_degraded`, and an `audit_note`. Durability
holds only once `audit_active` reports Postgres.

> **Placement caveat (observed).** Service linking resolves the target as
> `<name>.<project>.internal`, which is a **cluster-local** name. If the app and the
> database land on different providers (as ours did: app `10.43.x`, database
> `10.233.x`), that name does not resolve and the app **degrades to the embedded
> SQLite ledger** instead of failing. `GET /api/adapters` reports this honestly via
> `audit_requested` / `audit_active` / `audit_degraded` / `audit_note`. To get a
> durable ledger, the two services must be co-located on the same provider/cluster.
> Witness is built so that a missing or unreachable database never drops a case.

## Persistence — what actually survives (verified)

The audit ledger and the in-memory case store have **different** durability, and they
must not be conflated:

| Event | In-memory cases/decisions | Audit ledger (SQLite) |
|---|---|---|
| Process restart (same container, same `AUDIT_DB` on disk) | **Lost** — re-seeded fresh | **Retained** — same chain head, prior entries verified |
| Container replacement / rebuild / redeploy (ephemeral FS) | Lost — re-seeded fresh | **Lost** — new empty chain |
| Postgres active and reachable | Lost — re-seeded fresh | Retained (not currently active; see above) |

Evidence (local, two separate `uvicorn` processes sharing one `AUDIT_DB`):

```
run1: decision -> APPROVED; chain ok, 6 entries, head 48a29db2...
      [process stopped]
run2: cases recreated (5), decided 0; case1 in-memory VERIFIED (decision cleared)
      case1 ledger events: ['pipeline_run', 'human_decision']   <- persisted
      chain ok, 6 entries, head 48a29db2...                     <- same head
```

So: a **hash chain that verifies proves integrity, not durability.** Durability across
redeploys requires the Postgres backend (or a mounted persistent volume), neither of
which is active in the current deployment.

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

**Current status (this environment): not verified, blocked.** Two attempts, identical
incorrect configuration was not repeated a third time. The failure is at provider
placement/start of a Confidential VM, not in Witness code. Retrying requires:

1. `acc login --email` (the CLI in this workspace is currently **unauthenticated**, so
   no deploy/attest/log command can run),
2. a region/provider that actually offers a TEE-capable node, and
3. the same duplicate-service approach so the production URL is untouched.

If it succeeds, verify with `npx -y @alternatefutures/acc attest <tee-service-id>` (add
`--verify` if the installed CLI supports it). Until then, **do not claim TEE protection
or remote attestation.** The application never depends on confidential compute.

---

## Troubleshooting (from the organizers' guide)

| Symptom | Fix |
|---|---|
| Cloudflare **502 Bad Gateway** | Port mismatch. Ensure the app listens on `8000` and the Source tab port is `8000`. |
| Live URL returns nginx **404 Not Found** while logs show the app started | The **provider ingress** is stale/misconfigured. The app is fine (verify inside the container with `acc ssh <id> --command "python -c print(__import__('urllib.request').request.urlopen('http://127.0.0.1:8000/health').read())"`). Fix: **force a fresh deployment** — `acc services deploy <id> -y` (new lease/provider), or the dashboard **Redeploy**. Editing Ports does *not* fix this. |
| Live URL returns nginx **404 Not Found** and Settings → Ports is empty | The container port was never exposed. Add `8000` / `http` (Public blank), Save, Redeploy. |
| Pushed but live app unchanged | Building and deploying are separate. **Rebuild**, then **Deploy**. |
| Build succeeds, app crashes with `KeyError` | A required env var is missing. Add it under **Variables**, Rebuild, Deploy. |
| Anything else | Read the **Logs** tab first; then post logs (as text, keys removed) in the AF Discord `#support`. |
