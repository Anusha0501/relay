"""Company-brain questions. Each answer is a Cypher traversal with a source."""

from __future__ import annotations

from app import cypher_book as q
from app.db import fetch

QUESTIONS = {
    "who_knows": {
        "title": "Who knows this system?",
        "needs_service": True,
        "cypher": q.WHO_KNOWS.strip(),
    },
    "who_worked": {
        "title": "Who has worked on this system?",
        "needs_service": True,
        "cypher": q.WHO_WORKED.strip(),
    },
    "blast": {
        "title": "What breaks if this service goes down?",
        "needs_service": True,
        "cypher": q.BLAST.strip(),
    },
    "last_time": {
        "title": "What happened last time?",
        "needs_service": True,
        "cypher": q.LAST_TIME.strip(),
    },
    "decision": {
        "title": "Where did this decision come from?",
        "needs_service": True,
        "cypher": q.DECISIONS_ABOUT.strip(),
    },
    "ownership": {
        "title": "Who owns what, and who knows it?",
        "needs_service": False,
        "cypher": q.OWNERSHIP.strip(),
    },
}


def ask(graph, question: str, service: str | None) -> dict:
    spec = QUESTIONS.get(question)
    if spec is None:
        raise ValueError("Unknown question.")
    params = {"service": service or ""}
    if question == "who_knows":
        rows = fetch(graph, q.WHO_KNOWS, params, ["person", "role", "available"])
    elif question == "who_worked":
        rows = fetch(graph, q.WHO_WORKED, params, ["person", "role", "project"])
    elif question == "blast":
        rows = fetch(graph, q.BLAST, params, ["id", "service", "tier"])
    elif question == "last_time":
        rows = fetch(
            graph,
            q.LAST_TIME,
            params,
            ["episode", "name", "symptom", "summary", "impact_minutes", "cause", "result", "procedure", "person"],
        )
    elif question == "decision":
        rows = fetch(
            graph,
            q.DECISIONS_ABOUT,
            params,
            ["title", "rationale", "document", "kind", "decided_by", "episode"],
        )
    else:
        rows = fetch(graph, q.OWNERSHIP, None, ["service", "owners", "experts"])
        for row in rows:
            row["owners"] = [name for name in row["owners"] if name]
            row["experts"] = [name for name in row["experts"] if name]
    return {
        "question": question,
        "title": spec["title"],
        "service": service,
        "cypher": spec["cypher"],
        "rows": rows,
    }
