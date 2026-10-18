"""FalkorDB connection, tenant graphs, and result helpers."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TENANT_RE = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
SERVICE_RE = re.compile(r"^[a-z0-9-]{1,48}$")

_lock = threading.Lock()
_db = None
_backend = None


def open_db():
    """Connect to a FalkorDB server, or start the embedded FalkorDBLite runtime."""
    host = os.getenv("FALKORDB_HOST", "").strip()
    if host:
        from falkordb import FalkorDB

        port = int(os.getenv("FALKORDB_PORT", "6379"))
        return FalkorDB(host=host, port=port), "falkordb"

    from redislite.falkordb_client import FalkorDB

    path = os.getenv("FALKORDB_PATH", str(ROOT / "data" / "relay.db"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return FalkorDB(path), "falkordblite"


def reset_connection() -> None:
    global _db, _backend
    _db = None
    _backend = None


def get_db():
    global _db, _backend
    if _db is None:
        _db, _backend = open_db()
    return _db


def backend_name() -> str:
    get_db()
    return _backend or "unknown"


def require_tenant(tenant: str) -> str:
    if not TENANT_RE.match(tenant or ""):
        raise ValueError("Tenant ids are lowercase letters, numbers, and underscores.")
    return tenant


def require_service(service: str) -> str:
    if not SERVICE_RE.match(service or ""):
        raise ValueError("Unknown service id.")
    return service


def graph_name(tenant: str) -> str:
    return f"relay_{require_tenant(tenant)}"


def tenant_graph(tenant: str):
    return get_db().select_graph(graph_name(tenant))


def _execute(graph, cypher: str, params: dict | None):
    try:
        if params:
            return graph.query(cypher, params)
        return graph.query(cypher)
    except Exception as exc:  # noqa: BLE001 — surface the failing query
        raise RuntimeError(f"{exc}\n{cypher.strip()}") from exc


def query(graph, cypher: str, params: dict | None = None):
    """Run one Cypher query.

    The embedded runtime is single-process, so those calls take a lock.
    A FalkorDB server is the concurrency path: readers and writers do not wait
    on that lock.
    """
    if os.getenv("FALKORDB_HOST", "").strip():
        return _execute(graph, cypher, params)
    with _lock:
        return _execute(graph, cypher, params)


def convert(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [convert(item) for item in value]
    props = getattr(value, "properties", None)
    labels = getattr(value, "labels", None)
    if props is not None and labels is not None:
        return {
            "id": getattr(value, "id", None),
            "labels": list(labels),
            "properties": {key: convert(val) for key, val in dict(props).items()},
        }
    return str(value)


def fetch(graph, cypher: str, params: dict | None, columns: list[str]) -> list[dict]:
    result = query(graph, cypher, params)
    rows = []
    for raw in getattr(result, "result_set", None) or []:
        rows.append(
            {
                column: convert(raw[index]) if index < len(raw) else None
                for index, column in enumerate(columns)
            }
        )
    return rows


def is_true(value) -> bool:
    return value is True or value == 1 or value == "true"
