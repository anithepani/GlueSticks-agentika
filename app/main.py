"""Witness API.

A human-in-the-loop decision desk over a swappable pipeline. The app reads PORT
from the environment so the Alternate Clouds Source-tab port can never drift from
what the app listens on. The pipeline can reach VERIFIED / NEEDS_REVIEW but never
auto-denies: DENIED is only reachable through an explicit human decision.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app import __version__
from app.config import CASES_DIR, POLICY_DIR, STAGE, build_adapters, describe_adapters
from app.evaluation import evaluate
from app.observability import Metrics, log_json
from app.policy import POLICY_MARKDOWN
from app.store import CaseStore
from app.tamper_demo import tamper_demo

STATIC_DIR = Path(__file__).parent / "static"
METRICS = Metrics()


@asynccontextmanager
async def lifespan(app: FastAPI):
    METRICS.reset()
    bundle = build_adapters()
    store = CaseStore(bundle, CASES_DIR)
    store.seed()
    report = evaluate(bundle)
    app.state.bundle = bundle
    app.state.store = store
    app.state.gate = {
        "all_passed": report["all_passed"],
        "metrics": report["metrics"],
        "invariants": report["invariants"],
    }
    if os.getenv("WITNESS_STRICT", "0") == "1" and not report["all_passed"]:
        raise RuntimeError(
            "evaluation gate failed and WITNESS_STRICT=1: refusing to serve. See /api/eval."
        )
    yield


app = FastAPI(title="Witness", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        METRICS.record(request.url.path, 500, elapsed)
        log_json(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "ms": round(elapsed, 1),
                "request_id": request_id,
            }
        )
        raise
    elapsed = (time.perf_counter() - started) * 1000
    response.headers["x-request-id"] = request_id
    METRICS.record(request.url.path, response.status_code, elapsed)
    log_json(
        {
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round(elapsed, 1),
            "request_id": request_id,
        }
    )
    return response


class DecisionIn(BaseModel):
    officer: str
    action: str
    reason: str


class DocumentIn(BaseModel):
    doc_id: str | None = None
    title: str | None = None
    text: str = ""
    pdf_base64: str | None = None


class IntakeIn(BaseModel):
    applicant_name: str
    applicant_cnic: str = ""
    province: str = ""
    documents: list[DocumentIn]


class ResubmitIn(BaseModel):
    documents: list[DocumentIn]


class AssignIn(BaseModel):
    officer: str


def _store(request: Request) -> CaseStore:
    return request.app.state.store


@app.get("/health")
def health(request: Request) -> dict:
    gate = getattr(request.app.state, "gate", None)
    return {
        "status": "ok",
        "service": "witness",
        "version": __version__,
        "stage": STAGE,
        "gate": gate,
    }


@app.get("/api/info")
def info() -> dict:
    return {
        "name": "Witness",
        "tagline": "AI proposes, an independent check audits, a human decides.",
        "stage": STAGE,
        "version": __version__,
    }


@app.get("/api/policy")
def policy() -> dict:
    path = POLICY_DIR / "rules.md"
    if path.exists():
        return {"rules_markdown": path.read_text(encoding="utf-8"), "source": "file"}
    return {"rules_markdown": POLICY_MARKDOWN, "source": "embedded"}


@app.get("/api/cases")
def list_cases(request: Request) -> dict:
    store = _store(request)
    return {"cases": store.summaries(), "stats": store.stats()}


@app.post("/api/cases")
def create_case(payload: IntakeIn, request: Request) -> dict:
    try:
        case = _store(request).add_case(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return case.to_dict()


@app.post("/api/cases/{case_id}/resubmit")
def resubmit(case_id: str, payload: ResubmitIn, request: Request) -> dict:
    try:
        case = _store(request).resubmit(case_id, [doc.model_dump() for doc in payload.documents])
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return case.to_dict()


@app.post("/api/cases/{case_id}/assign")
def assign(case_id: str, payload: AssignIn, request: Request) -> dict:
    try:
        case = _store(request).assign(case_id, payload.officer)
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return case.to_dict()


@app.get("/api/eval")
def eval_report(request: Request) -> dict:
    return evaluate(request.app.state.bundle)


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, request: Request) -> dict:
    case = _store(request).get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case.to_dict()


@app.post("/api/cases/{case_id}/decision")
def decide(case_id: str, payload: DecisionIn, request: Request) -> dict:
    try:
        case = _store(request).decide(case_id, payload.officer, payload.action, payload.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="case not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return case.to_dict()


@app.get("/api/cases/{case_id}/audit")
def case_audit(case_id: str, request: Request) -> dict:
    if _store(request).get(case_id) is None:
        raise HTTPException(status_code=404, detail="case not found")
    entries = request.app.state.bundle.audit.entries(case_id)
    return {"case_id": case_id, "entries": entries}


@app.get("/api/audit/verify")
def audit_verify(request: Request) -> dict:
    return request.app.state.bundle.audit.verify()


@app.post("/api/audit/tamper-demo")
def audit_tamper_demo(request: Request) -> dict:
    return tamper_demo(request.app.state.bundle.audit)


@app.post("/api/reseed")
def reseed(request: Request) -> dict:
    created = _store(request).reseed()
    return {"reseeded": created, "stats": _store(request).stats()}


@app.get("/api/stats")
def stats(request: Request) -> dict:
    return _store(request).stats()


@app.get("/api/metrics")
def metrics(request: Request) -> dict:
    snapshot = METRICS.snapshot()
    snapshot["gate"] = getattr(request.app.state, "gate", None)
    snapshot["cases"] = _store(request).stats()
    return snapshot


@app.get("/api/diag")
def diag(request: Request) -> dict:
    return {**_store(request).diag(), "gate": getattr(request.app.state, "gate", None)}


@app.get("/api/adapters")
def adapters(request: Request) -> dict:
    return describe_adapters(request.app.state.bundle)


@app.get("/")
def index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"error": "ui not found"}, status_code=500)
    return FileResponse(page)
