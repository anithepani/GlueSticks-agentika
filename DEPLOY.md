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

---

## Troubleshooting (from the organizers' guide)

| Symptom | Fix |
|---|---|
| Cloudflare **502 Bad Gateway** | Port mismatch. Ensure the app listens on `8000` and the Source tab port is `8000`. |
| Live URL returns nginx **404 Not Found** while logs show `Uvicorn running on 0.0.0.0:8000` | The gateway found the service but nothing is exposed. **Settings → Ports → Add Port**: container port `8000`, protocol `http`, Public blank → **Save** → **Redeploy**. |
| Pushed but live app unchanged | Building and deploying are separate. **Rebuild**, then **Deploy**. |
| Build succeeds, app crashes with `KeyError` | A required env var is missing. Add it under **Variables**, Rebuild, Deploy. |
| Anything else | Read the **Logs** tab first; then post logs (as text, keys removed) in the AF Discord `#support`. |
