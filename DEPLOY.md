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
AUDIT=sqlite
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
- **Service boundary:** The app runs as a single self-contained container: one process, one port, one read-only image. All state lives inside the container (in-memory case store plus a SQLite ledger).

## Storage and persistence

The decision ledger is an append-only, hash-chained SQLite database at `data/audit.db`
inside the container. `GET /api/audit/verify` recomputes the whole chain.

| Event | Case state (in memory) | Ledger (`data/audit.db`) |
|---|---|---|
| Process restart | resets and reseeds | **retained**, chain verifies unchanged |
| Redeploy | resets and reseeds | reset with the container filesystem |

This is deliberate for the demonstration: the five sample cases are restored on start,
and the ledger proves the integrity of every decision taken during a session. The
database file is not committed (`*.db` is ignored).

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
