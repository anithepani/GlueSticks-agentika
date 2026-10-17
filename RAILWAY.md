# Backup deployment on Railway

**Live backup URL:** https://witness-production-64ea.up.railway.app

> **Competition status:** the submitted deployment is the one on **Clouds by Alternate
> Futures**. The rules name it as the only accepted platform; this Railway deployment is a
> demonstration backup only, used if the primary platform is unavailable during a live demo.
> Do not submit the Railway URL as the project deployment link.

## Why Railway rather than Vercel

Witness keeps case state in the process and appends to a SQLite ledger. Railway runs the
container as a long-lived process, exactly like the primary deployment. Vercel runs
serverless functions, so the in-memory case store would reset between requests and the
officer decision flow would appear to lose state.

## Files involved

| File | Purpose |
|---|---|
| `Dockerfile` | unchanged; reads `PORT` from the environment |
| `railway.json` | tells Railway to build the Dockerfile, healthcheck on `/health` |
| `Procfile` | fallback start command (not used with the Dockerfile builder) |

## What was run (verified)

```powershell
npx -y @railway/cli login
npx -y @railway/cli init --name witness
npx -y @railway/cli up --detach
npx -y @railway/cli service witness
npx -y @railway/cli variables --set "READER=pdf" --set "EXTRACTOR=fixture" `
  --set "VERIFIER=det" --set "AUDIT=sqlite" --set "WITNESS_STAGE=4"
npx -y @railway/cli domain
```

Verified on the Railway URL: `/health` 200 (`v0.5.0`, gate 55/55), `/api/cases` 5 cases,
`/api/eval` all_passed, the console renders, an approval returns 200 and the audit chain
verifies, and a reseed restores the five sample cases.

Optional, to run with the model enabled:

```powershell
npx -y @railway/cli variables --set "EXTRACTOR=llm" --set "VERIFIER=llm" `
  --set "LLM_PROVIDER=groq" --set "GROQ_MODEL=llama-3.3-70b-versatile"
# then set the key from the dashboard, or: railway variables --set "GROQ_API_KEY=<key>"
```

## Deploy from the dashboard instead

1. <https://railway.app/new> → **Deploy from GitHub repo** → `anithepani/GlueSticks-agentika`.
2. Railway detects `railway.json` and builds the Dockerfile.
3. **Variables** → add the five variables above.
4. **Settings → Networking → Generate Domain**.
5. Open `https://<domain>/health` and confirm `"status":"ok"`.

## Verify after deploy

```powershell
Invoke-WebRequest https://<domain>/health   -UseBasicParsing | % Content
Invoke-WebRequest https://<domain>/api/eval -UseBasicParsing | % Content
Invoke-WebRequest https://<domain>/api/cases -UseBasicParsing | % Content
```

Expected: `version 0.5.0`, `gate.all_passed: true`, five seeded cases.

## Notes

- Railway sets `PORT`; the image already binds `${PORT:-8000}`, so no change is needed.
- The ledger resets when the container is replaced, the same as on the primary platform.
- Do not put `GROQ_API_KEY` in the repository; use Railway variables.
