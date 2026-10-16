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

## Postgres audit ledger (durable across redeploys)

The SQLite ledger lives inside the container, so a redeploy starts a fresh chain.
For a durable ledger, deploy the managed Postgres template and link it:

```powershell
npx -y @alternatefutures/acc services create --kind template --template postgres --name witness-db -y
npx -y @alternatefutures/acc services -p witness-agentika link witness-db alternate-echo-whale-5578-github
npx -y @alternatefutures/acc services -p witness-agentika info cmvbc3e5706exe41rs9g87kmn
```

Linking injects the connection string into the app service (as `DATABASE_URL` /
`POSTGRES_URL`). Set `AUDIT=postgres`, **Rebuild → Deploy**, then confirm with:

- `GET /api/adapters` → `"audit": "postgres(fallback:sqlite)"`
- `GET /api/audit/verify` → `{"ok": true, "ledger": "postgres", ...}`

Because the ledger is now outside the container, a decision recorded before a
**Redeploy** is still there afterwards — the redeploy no longer resets the chain.

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
