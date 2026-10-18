"""HTTP API and the demo UI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import cypher_book as book
from app.agents import graph_view, memory_feed, record_outcome, run_incident
from app.company import QUESTIONS, ask
from app.db import ROOT, backend_name, get_db, require_service, require_tenant, tenant_graph
from app.seed import SCENARIOS, TENANTS, ensure_seeded, reset_tenant

STATIC = Path(ROOT) / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_seeded(get_db())
    yield


app = FastAPI(title="Relay", lifespan=lifespan)


class IncidentIn(BaseModel):
    service: str
    symptom: str
    policy: str = "memory"


class OutcomeIn(BaseModel):
    result: str
    note: str = Field(default="", max_length=240)


class AskIn(BaseModel):
    question: str
    service: str | None = None


def _graph(tenant: str):
    try:
        require_tenant(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if tenant not in TENANTS:
        raise HTTPException(status_code=404, detail="Unknown company.")
    return tenant_graph(tenant)


def _run(fn):
    try:
        return fn()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc).splitlines()[0]) from exc


@app.get("/api/health")
def health():
    return {"ok": True, "backend": backend_name(), "tenants": list(TENANTS)}


@app.get("/api/cypher")
def cypher():
    names = [
        "PRIOR_CAUSE",
        "FAILED_ATTEMPTS",
        "SUCCESSFUL_ATTEMPTS",
        "OWNER_POLICY",
        "SHORTEST_ACTION_PATH",
        "PAGE_RANK",
        "BETWEENNESS",
        "COMPONENTS",
        "WHO_WORKED",
        "DECISION_SOURCE",
    ]
    return [{"name": name, "query": getattr(book, name).strip()} for name in names]


@app.get("/api/tenants/{tenant}")
def tenant_detail(tenant: str):
    spec = TENANTS.get(tenant)
    if spec is None:
        raise HTTPException(status_code=404, detail="Unknown company.")
    return {
        "id": tenant,
        "company": spec["company"],
        "blurb": spec["blurb"],
        "scenarios": SCENARIOS[tenant],
        "questions": [
            {"id": key, "title": value["title"], "needs_service": value["needs_service"]}
            for key, value in QUESTIONS.items()
        ],
    }


@app.post("/api/tenants/{tenant}/reset")
def reset(tenant: str):
    graph = _graph(tenant)
    reset_tenant(graph, tenant)
    return {"ok": True}


@app.get("/api/tenants/{tenant}/graph")
def company_graph(tenant: str):
    return graph_view(_graph(tenant))


@app.get("/api/tenants/{tenant}/memory")
def memory(tenant: str):
    return memory_feed(_graph(tenant))


@app.post("/api/tenants/{tenant}/incidents")
def incident(tenant: str, body: IncidentIn):
    graph = _graph(tenant)
    try:
        require_service(body.service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _run(lambda: run_incident(graph, body.service, body.symptom, body.policy))


@app.post("/api/tenants/{tenant}/sessions/{session_id}/outcome")
def outcome(tenant: str, session_id: str, body: OutcomeIn):
    graph = _graph(tenant)
    if not session_id.startswith("ses-"):
        raise HTTPException(status_code=400, detail="Unknown session.")
    return _run(lambda: record_outcome(graph, session_id, body.result, body.note))


@app.post("/api/tenants/{tenant}/ask")
def company_ask(tenant: str, body: AskIn):
    graph = _graph(tenant)
    if body.service:
        try:
            require_service(body.service)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _run(lambda: ask(graph, body.question, body.service))


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
