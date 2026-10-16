"""Witness API. Stage 1: a walking skeleton over an in-memory case store.

Stable surface: the app reads PORT from the environment so the Alternate Clouds
Source-tab port can never drift from what the app listens on.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app import __version__
from app.config import CASES_DIR, POLICY_DIR, STAGE, build_adapters, describe_adapters
from app.evaluation import evaluate
from app.policy import POLICY_MARKDOWN
from app.store import CaseStore

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = build_adapters()
    store = CaseStore(bundle, CASES_DIR)
    store.seed()
    app.state.bundle = bundle
    app.state.store = store
    yield


app = FastAPI(title="Witness", version=__version__, lifespan=lifespan)


class DecisionIn(BaseModel):
    officer: str
    action: str
    reason: str


class DocumentIn(BaseModel):
    doc_id: str | None = None
    title: str | None = None
    text: str


class IntakeIn(BaseModel):
    applicant_name: str
    applicant_cnic: str = ""
    province: str = ""
    documents: list[DocumentIn]


class ResubmitIn(BaseModel):
    documents: list[DocumentIn]


def _store(request: Request) -> CaseStore:
    return request.app.state.store


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "witness", "version": __version__, "stage": STAGE}


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
    entries = request.app.state.bundle.audit.entries(case_id)
    return {"case_id": case_id, "entries": entries}


@app.get("/api/audit/verify")
def audit_verify(request: Request) -> dict:
    return request.app.state.bundle.audit.verify()


@app.post("/api/reseed")
def reseed(request: Request) -> dict:
    created = _store(request).reseed()
    return {"reseeded": created, "stats": _store(request).stats()}


@app.get("/api/stats")
def stats(request: Request) -> dict:
    return _store(request).stats()


@app.get("/api/diag")
def diag(request: Request) -> dict:
    return _store(request).diag()


@app.get("/api/adapters")
def adapters(request: Request) -> dict:
    return describe_adapters(request.app.state.bundle)


@app.get("/")
def index():
    page = STATIC_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"error": "ui not found"}, status_code=500)
    return FileResponse(page)
