"""Witness API - Stage 0 skeleton.

Stable surface even at Stage 0: the app reads PORT from the environment so the
Alternate Clouds Source-tab port can never drift from what the app listens on.
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from app import __version__

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Witness", version=__version__)

STAGE = int(os.getenv("WITNESS_STAGE", "0"))


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "witness",
        "version": __version__,
        "stage": STAGE,
    }


@app.get("/api/info")
def info() -> dict:
    return {
        "name": "Witness",
        "tagline": "AI proposes, an independent check audits, a human decides.",
        "stage": STAGE,
        "version": __version__,
    }


@app.get("/")
def index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"error": "ui not found"}, status_code=500)
    return FileResponse(page)
