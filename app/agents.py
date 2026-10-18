"""Three agents. They share state only by reading and writing FalkorDB."""

from __future__ import annotations

import time
import uuid

from app import cypher_book as q
from app.db import fetch, is_true, query

AGENT_COPY = {
    "archivist": {
        "name": "Archivist",
        "focus": "Memory",
        "track": "Agent memory and coordination",
    },
    "cartographer": {
        "name": "Cartographer",
        "focus": "Action",
        "track": "Agents that act on connected data",
    },
    "liaison": {
        "name": "Liaison",
        "focus": "Handoff",
        "track": "Company brain",
    },
}


def _now() -> int:
    return int(time.time() * 1000)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _service(graph, service: str) -> dict:
    rows = fetch(graph, q.SERVICE_ROW, {"service": service}, ["id", "name", "tier", "summary"])
    if not rows:
        raise LookupError(f"No service '{service}' in this company graph.")
    return rows[0]


def _blocked(graph, service: str, symptom: str) -> list[dict]:
    return fetch(
        graph,
        q.FAILED_ATTEMPTS,
        {"service": service, "symptom": symptom},
        ["procedure_id", "procedure_name", "result", "episode", "person_name", "impact_minutes"],
    )


def _cause(graph, service: str, symptom: str) -> dict | None:
    rows = fetch(
        graph,
        q.PRIOR_CAUSE,
        {"service": service, "symptom": symptom},
        ["episode", "summary", "impact_minutes", "cause", "cause_name", "started_at"],
    )
    return rows[0] if rows else None


def _open_handoff(graph, service: str) -> dict | None:
    rows = fetch(
        graph,
        q.OPEN_HANDOFF,
        {"service": service},
        ["id", "summary", "session_id", "person_id", "person_name", "available", "procedure_id", "procedure_name"],
    )
    return rows[0] if rows else None


def _owner_choice(graph, service: str) -> dict | None:
    rows = fetch(
        graph,
        q.OWNER_POLICY,
        {"service": service},
        ["person_id", "person_name", "role", "procedure_id", "procedure_name", "naive_rank", "dep_id", "dep_name"],
    )
    return rows[0] if rows else None


def _link(graph, agent_id: str, rel: str, node_id: str, session_id: str) -> None:
    if rel not in {"WROTE", "READ"}:
        raise ValueError(rel)
    query(
        graph,
        f"""
        MATCH (agent:Agent {{id: $agent}}), (n {{id: $node}})
        CREATE (agent)-[:{rel} {{session_id: $session_id, at: $at}}]->(n)
        """,
        {"agent": agent_id, "node": node_id, "session_id": session_id, "at": _now()},
    )


def _write_memory(graph, session_id: str, kind: str, text: str, about: str) -> str:
    memory_id = _id("mem")
    query(
        graph,
        """
        CREATE (:Memory {
            id: $id, kind: $kind, text: $text, session_id: $session_id,
            agent: 'archivist', about: $about, created_at: $created_at
        })
        """,
        {
            "id": memory_id,
            "kind": kind,
            "text": text,
            "session_id": session_id,
            "about": about,
            "created_at": _now(),
        },
    )
    _link(graph, "archivist", "WROTE", memory_id, session_id)
    return memory_id


def archivist(graph, session_id: str, service: str, symptom: str) -> str:
    """Write episodic, semantic, and procedural memory. Return the Recall id."""
    cause = _cause(graph, service, symptom)
    blocked = _blocked(graph, service, symptom)
    handoff = _open_handoff(graph, service)
    blocked_ids = "|".join(dict.fromkeys(row["procedure_id"] for row in blocked))
    prior = cause["episode"] if cause else ""
    suspected = cause["cause"] if cause else ""
    summary_bits = []
    if cause:
        summary_bits.append(
            f"{cause['episode']} caused this symptom at {cause['cause_name']} "
            f"({cause['impact_minutes']} min)."
        )
    if blocked:
        names = ", ".join(f"{row['procedure_name']} ({row['result']})" for row in blocked)
        summary_bits.append(f"Blocked procedures: {names}.")
    if handoff:
        summary_bits.append(
            f"Open handoff {handoff['id']} assigns {handoff['person_name']} "
            f"to {handoff['procedure_name']}."
        )
    if not summary_bits:
        summary_bits.append("No prior episode for this symptom.")
    summary = " ".join(summary_bits)
    recall_id = _id("recall")
    query(
        graph,
        """
        CREATE (:Recall {
            id: $id, session_id: $session_id, service: $service, symptom: $symptom,
            suspected_cause: $suspected, prior_episode: $prior,
            blocked_procedures: $blocked, handoff_id: $handoff_id,
            handoff_procedure_id: $handoff_procedure_id, handoff_person_id: $handoff_person_id,
            summary: $summary, created_at: $created_at
        })
        """,
        {
            "id": recall_id,
            "session_id": session_id,
            "service": service,
            "symptom": symptom,
            "suspected": suspected,
            "prior": prior,
            "blocked": blocked_ids,
            "handoff_id": handoff["id"] if handoff else "",
            "handoff_procedure_id": handoff["procedure_id"] if handoff else "",
            "handoff_person_id": handoff["person_id"] if handoff else "",
            "summary": summary,
            "created_at": _now(),
        },
    )
    _link(graph, "archivist", "WROTE", recall_id, session_id)
    if cause:
        _write_memory(
            graph,
            session_id,
            "episodic",
            f"{cause['episode']}: {cause['summary']}",
            prior,
        )
        _write_memory(
            graph,
            session_id,
            "semantic",
            f"{service} / {symptom} has previously been caused by {cause['cause_name']}.",
            suspected,
        )
    if blocked:
        _write_memory(
            graph,
            session_id,
            "procedural",
            "Do not repeat " + ", ".join(sorted({row["procedure_name"] for row in blocked})) + ".",
            service,
        )
    return recall_id


def _load_recall(graph, session_id: str) -> dict:
    rows = fetch(
        graph,
        q.RECALL_ROW,
        {"session_id": session_id},
        [
            "id",
            "service",
            "symptom",
            "suspected_cause",
            "prior_episode",
            "blocked_procedures",
            "handoff_id",
            "handoff_procedure_id",
            "handoff_person_id",
            "summary",
        ],
    )
    if not rows:
        raise LookupError("Cartographer found no Recall. Archivist has not written shared memory.")
    return rows[0]


def _choose_action(graph, recall: dict) -> dict:
    blocked = {item for item in (recall.get("blocked_procedures") or "").split("|") if item}
    cause = recall.get("suspected_cause") or ""
    service = recall["service"]
    path_notes = []

    if cause:
        procedures = fetch(
            graph,
            q.PROCEDURES_FOR,
            {"service": cause},
            ["id", "name", "summary", "naive_rank"],
        )
        successes = fetch(
            graph,
            q.SUCCESSFUL_ATTEMPTS,
            {"cause": cause},
            ["procedure_id", "procedure_name", "person_id", "person_name", "available", "role", "attempt"],
        )
        knowers = fetch(graph, q.KNOWERS, {"service": cause}, ["id", "name", "role", "available"])
    else:
        procedures, successes, knowers = [], [], []

    open_proc = recall.get("handoff_procedure_id") or ""
    open_person = recall.get("handoff_person_id") or ""
    procedure = None
    person = None
    continued = False

    if open_proc and open_proc not in blocked and open_person:
        person_rows = fetch(
            graph,
            q.PERSON_ROW,
            {"id": open_person},
            ["id", "name", "role", "available", "on_call"],
        )
        proc_rows = [row for row in procedures if row["id"] == open_proc]
        if person_rows and is_true(person_rows[0]["available"]) and proc_rows:
            person = person_rows[0]
            procedure = proc_rows[0]
            continued = True
            path_notes.append(
                f"Open handoff {recall.get('handoff_id')} is still valid, so the crew continues it."
            )

    if procedure is None:
        wins: dict[str, int] = {}
        names: dict[str, str] = {}
        for row in successes:
            if row["procedure_id"] in blocked or not is_true(row["available"]):
                continue
            wins[row["procedure_id"]] = wins.get(row["procedure_id"], 0) + 1
            names[row["procedure_id"]] = row["procedure_name"]
        if wins:
            best = sorted(wins, key=lambda item: (-wins[item], item))[0]
            procedure = {"id": best, "name": names[best], "summary": "", "naive_rank": 0}
            path_notes.append(
                f"{procedure['name']} has {wins[best]} successful attempt(s) on the suspected cause."
            )
        else:
            remaining = [row for row in procedures if row["id"] not in blocked]
            procedure = remaining[0] if remaining else None
            if procedure:
                path_notes.append(
                    f"No unblocked success remains. Next procedure is {procedure['name']}."
                )

    if procedure and person is None:
        winners = [
            row
            for row in successes
            if row["procedure_id"] == procedure["id"] and is_true(row["available"])
        ]
        if winners:
            person = {
                "id": winners[0]["person_id"],
                "name": winners[0]["person_name"],
                "role": winners[0]["role"],
            }
            path_notes.append(f"{person['name']} is the available person who has done this successfully.")
        else:
            available = [row for row in knowers if is_true(row["available"])]
            person = available[0] if available else None
            if person:
                path_notes.append(
                    f"{person['name']} knows the cause service. Nobody available has a success on this procedure yet."
                )

    considered = [row["name"] for row in knowers if not person or row["id"] != person["id"]]
    return {
        "procedure": procedure,
        "person": person,
        "cause": cause,
        "blocked": sorted(blocked),
        "continued": continued,
        "considered": considered,
        "notes": path_notes,
    }


def cartographer(graph, session_id: str) -> str:
    """Read the Recall from the graph, then write an Action. Algorithms rank the blast."""
    recall = _load_recall(graph, session_id)
    _link(graph, "cartographer", "READ", recall["id"], session_id)
    choice = _choose_action(graph, recall)
    service = _service(graph, recall["service"])
    cause_id = choice["cause"]
    cause_name = ""
    if cause_id:
        cause_name = _service(graph, cause_id)["name"]
    procedure = choice["procedure"] or {"id": "", "name": "Investigate manually", "summary": ""}
    person = choice["person"] or {"id": "", "name": "Unassigned", "role": ""}
    summary = _decision_summary(service["name"], person["name"], procedure["name"], cause_name, choice["blocked"])
    action_id = _id("action")
    episode_id = f"ep-{session_id}"
    query(
        graph,
        """
        CREATE (:Action {
            id: $id, session_id: $session_id, policy: 'memory',
            procedure_id: $procedure_id, procedure_name: $procedure_name,
            assignee_id: $assignee_id, assignee_name: $assignee_name,
            cause: $cause, service: $service, summary: $summary,
            episode_id: $episode_id, created_at: $created_at
        })
        """,
        {
            "id": action_id,
            "session_id": session_id,
            "procedure_id": procedure["id"],
            "procedure_name": procedure["name"],
            "assignee_id": person["id"],
            "assignee_name": person["name"],
            "cause": cause_id,
            "service": recall["service"],
            "summary": summary,
            "episode_id": episode_id,
            "created_at": _now(),
        },
    )
    if person["id"]:
        query(
            graph,
            """
            MATCH (a:Action {id: $action}), (p:Person {id: $person})
            CREATE (a)-[:ASSIGNED_TO]->(p)
            """,
            {"action": action_id, "person": person["id"]},
        )
    if procedure["id"]:
        query(
            graph,
            """
            MATCH (a:Action {id: $action}), (proc:Procedure {id: $proc})
            CREATE (a)-[:USES]->(proc)
            """,
            {"action": action_id, "proc": procedure["id"]},
        )
    _link(graph, "cartographer", "WROTE", action_id, session_id)
    return action_id


def _decision_summary(service, person, procedure, cause, blocked) -> str:
    blocked_txt = ", ".join(blocked) if blocked else "none"
    where = f" on {cause}" if cause else ""
    return f"Assign {person} to {procedure}{where}. Alert is {service}. Blocked: {blocked_txt}."


def _load_action(graph, session_id: str) -> dict:
    rows = fetch(
        graph,
        q.ACTION_ROW,
        {"session_id": session_id},
        [
            "id",
            "procedure_id",
            "procedure_name",
            "assignee_id",
            "assignee_name",
            "cause",
            "service",
            "summary",
            "episode_id",
        ],
    )
    if not rows:
        raise LookupError("Liaison found no Action. Cartographer has not written shared state.")
    return rows[0]


def liaison(graph, session_id: str) -> str:
    """Read the Action from the graph and write the handoff the next session will find."""
    action = _load_action(graph, session_id)
    recall = _load_recall(graph, session_id)
    _link(graph, "liaison", "READ", action["id"], session_id)
    sources = []
    if recall.get("prior_episode"):
        sources = fetch(
            graph,
            q.DECISION_SOURCE,
            {"episode": recall["prior_episode"]},
            ["title", "rationale", "doc_title", "doc_kind", "decided_by"],
        )
    owners = fetch(graph, q.OWNERS_OF, {"service": action["service"]}, ["id", "name", "on_call", "available"])
    owner_names = ", ".join(row["name"] for row in owners) or "nobody"
    source_txt = ""
    if sources:
        source_txt = (
            f" Decision '{sources[0]['title']}' by {sources[0]['decided_by']} "
            f"is sourced from {sources[0]['doc_title']}."
        )
    summary = (
        f"{action['summary']} Service owner is {owner_names}, "
        f"which is a different fact from who should act.{source_txt}"
    )
    if recall.get("handoff_id"):
        query(
            graph,
            "MATCH (h:Handoff {id: $id}) SET h.status = 'continued'",
            {"id": recall["handoff_id"]},
        )
    handoff_id = _id("handoff")
    query(
        graph,
        """
        CREATE (:Handoff {
            id: $id, session_id: $session_id, status: 'open', summary: $summary,
            created_at: $created_at, continued_from: $continued_from
        })
        """,
        {
            "id": handoff_id,
            "session_id": session_id,
            "summary": summary,
            "created_at": _now(),
            "continued_from": recall.get("handoff_id") or "",
        },
    )
    query(
        graph,
        """
        MATCH (h:Handoff {id: $handoff}), (s:Service {id: $service})
        CREATE (h)-[:ABOUT]->(s)
        """,
        {"handoff": handoff_id, "service": action["service"]},
    )
    if action["assignee_id"]:
        query(
            graph,
            """
            MATCH (h:Handoff {id: $handoff}), (p:Person {id: $person})
            CREATE (h)-[:ASSIGNS]->(p)
            """,
            {"handoff": handoff_id, "person": action["assignee_id"]},
        )
    if action["procedure_id"]:
        query(
            graph,
            """
            MATCH (h:Handoff {id: $handoff}), (proc:Procedure {id: $proc})
            CREATE (h)-[:RECOMMENDS]->(proc)
            """,
            {"handoff": handoff_id, "proc": action["procedure_id"]},
        )
    _link(graph, "liaison", "WROTE", handoff_id, session_id)
    return handoff_id


def _algorithms(graph, source: str, cause: str) -> dict:
    report: dict = {"pagerank": [], "betweenness": [], "components": [], "shortest_path": [], "notes": []}
    try:
        report["pagerank"] = fetch(graph, q.PAGE_RANK, None, ["name", "score"])
        report["notes"].append("algo.pageRank on Service-DEPENDS_ON")
    except RuntimeError as exc:
        report["pagerank"] = fetch(
            graph,
            """
            MATCH (s:Service)
            OPTIONAL MATCH (s)<-[:DEPENDS_ON]-(other:Service)
            WITH s, count(other) AS score
            RETURN s.name, score
            ORDER BY score DESC
            LIMIT 8
            """,
            None,
            ["name", "score"],
        )
        report["notes"].append(f"PageRank fallback to incoming degree ({exc.__cause__})")
    try:
        report["betweenness"] = fetch(graph, q.BETWEENNESS, None, ["name", "score"])
        report["notes"].append("algo.betweenness on Service-DEPENDS_ON")
    except RuntimeError as exc:
        report["notes"].append(f"betweenness unavailable ({exc.__cause__})")
    try:
        report["components"] = fetch(graph, q.COMPONENTS, None, ["name", "component"])
        report["notes"].append("algo.WCC on the service topology")
    except RuntimeError as exc:
        report["notes"].append(f"WCC unavailable ({exc.__cause__})")
    replica = fetch(graph, q.REPLICA, {"cause": cause}, ["id", "name"]) if cause else []
    target = replica[0]["id"] if replica else cause
    if source and target:
        try:
            rows = fetch(graph, q.SHORTEST_ACTION_PATH, {"source": source, "target": target}, ["names"])
            if rows:
                report["shortest_path"] = rows[0]["names"]
                report["notes"].append("shortestPath along DEPENDS_ON and ROUTES_TO")
        except RuntimeError as exc:
            report["notes"].append(f"shortestPath unavailable ({exc.__cause__})")
    return report


def _blast(graph, service: str) -> list[dict]:
    return fetch(graph, q.BLAST, {"service": service}, ["id", "name", "tier"])


def _upstream(graph, service: str) -> list[dict]:
    return fetch(graph, q.UPSTREAM, {"service": service}, ["id", "name"])


def _coordination(graph, session_id: str) -> list[dict]:
    return fetch(
        graph,
        """
        MATCH (agent:Agent)-[r]->(n)
        WHERE r.session_id = $session_id
        RETURN agent.name, type(r), labels(n)[0], n.id
        ORDER BY r.at ASC
        """,
        {"session_id": session_id},
        ["agent", "rel", "label", "node_id"],
    )


def _open_episode(graph, session_id: str, service: str, symptom: str) -> None:
    query(
        graph,
        """
        CREATE (:Episode {
            id: $id, name: $name, symptom: $symptom, live: true,
            started_at: $started_at, impact_minutes: 0,
            summary: 'Live incident opened by the crew.'
        })
        """,
        {
            "id": f"ep-{session_id}",
            "name": f"LIVE-{session_id[-4:]}",
            "symptom": symptom,
            "started_at": _now(),
        },
    )
    query(
        graph,
        """
        MATCH (e:Episode {id: $episode}), (s:Service {id: $service})
        CREATE (e)-[:AFFECTED]->(s)
        """,
        {"episode": f"ep-{session_id}", "service": service},
    )


def run_incident(graph, service: str, symptom: str, policy: str = "memory") -> dict:
    if policy not in {"memory", "owner"}:
        raise ValueError("Policy must be 'memory' or 'owner'.")
    if not symptom or len(symptom) > 60:
        raise ValueError("Symptom is required.")
    service_row = _service(graph, service)
    session_id = _id("ses")
    owner = _owner_choice(graph, service)
    owner_view = None
    if owner:
        owner_view = {
            "assignee_id": owner["person_id"],
            "assignee_name": owner["person_name"],
            "assignee_role": owner["role"],
            "procedure_id": owner["procedure_id"],
            "procedure_name": owner["procedure_name"],
            "via": owner["dep_name"],
        }

    if policy == "owner":
        if not owner:
            raise LookupError("No available owner for that service.")
        return {
            "session_id": session_id,
            "policy": "owner",
            "service": service_row,
            "symptom": symptom,
            "decision": {
                "assignee_id": owner["person_id"],
                "assignee_name": owner["person_name"],
                "assignee_role": owner["role"],
                "procedure_id": owner["procedure_id"],
                "procedure_name": owner["procedure_name"],
                "cause_id": owner["dep_id"],
                "cause_name": owner["dep_name"],
                "summary": (
                    f"Owner policy pages {owner['person_name']} and runs "
                    f"{owner['procedure_name']}. It does not read incident memory."
                ),
            },
            "owner_would_have": owner_view,
            "blocked": _blocked(graph, service, symptom),
            "path": [
                {
                    "title": "Owner edge",
                    "detail": f"{owner['person_name']} OWNS {service_row['name']}.",
                },
                {
                    "title": "First-line runbook",
                    "detail": (
                        f"{owner['procedure_name']} applies to {owner['dep_name']} "
                        f"and has the lowest naive rank."
                    ),
                },
            ],
            "agents": [],
            "coordination": [],
            "algorithms": _algorithms(graph, service, ""),
            "blast": _blast(graph, service),
            "upstream": _upstream(graph, service),
            "handoff_id": "",
            "continued_from": "",
            "recall_summary": "",
        }

    _open_episode(graph, session_id, service, symptom)
    archivist(graph, session_id, service, symptom)
    cartographer(graph, session_id)
    handoff_id = liaison(graph, session_id)
    recall = _load_recall(graph, session_id)
    action = _load_action(graph, session_id)
    person_rows = (
        fetch(graph, q.PERSON_ROW, {"id": action["assignee_id"]}, ["id", "name", "role", "available", "on_call"])
        if action["assignee_id"]
        else []
    )
    person = person_rows[0] if person_rows else {"role": "", "on_call": False}
    cause_name = _service(graph, action["cause"])["name"] if action["cause"] else ""
    blocked = _blocked(graph, service, symptom)
    algorithms = _algorithms(graph, service, action["cause"])
    sources = []
    if recall.get("prior_episode"):
        sources = fetch(
            graph,
            q.DECISION_SOURCE,
            {"episode": recall["prior_episode"]},
            ["title", "rationale", "doc_title", "doc_kind", "decided_by"],
        )
    path = _explain(service_row, recall, action, cause_name, blocked, owner_view, sources, algorithms)
    return {
        "session_id": session_id,
        "policy": "memory",
        "service": service_row,
        "symptom": symptom,
        "decision": {
            "assignee_id": action["assignee_id"],
            "assignee_name": action["assignee_name"],
            "assignee_role": person.get("role", ""),
            "procedure_id": action["procedure_id"],
            "procedure_name": action["procedure_name"],
            "cause_id": action["cause"],
            "cause_name": cause_name,
            "summary": action["summary"],
            "on_call": is_true(person.get("on_call")),
        },
        "owner_would_have": owner_view,
        "blocked": blocked,
        "path": path,
        "sources": sources,
        "agents": [
            {**AGENT_COPY["archivist"], "summary": recall["summary"]},
            {**AGENT_COPY["cartographer"], "summary": action["summary"]},
            {
                **AGENT_COPY["liaison"],
                "summary": "Wrote a handoff the next session can read without this process.",
            },
        ],
        "coordination": _coordination(graph, session_id),
        "algorithms": algorithms,
        "blast": _blast(graph, service),
        "upstream": _upstream(graph, service),
        "handoff_id": handoff_id,
        "continued_from": recall.get("handoff_id") or "",
        "recall_summary": recall["summary"],
    }


def _explain(service, recall, action, cause_name, blocked, owner, sources, algorithms) -> list[dict]:
    steps = [
        {"title": "Shared recall", "detail": recall["summary"]},
    ]
    if recall.get("prior_episode"):
        steps.append(
            {
                "title": "Cause hop",
                "detail": (
                    f"{recall['prior_episode']} AFFECTED {service['name']} and "
                    f"CAUSED_BY {cause_name or recall.get('suspected_cause')}."
                ),
            }
        )
    if blocked:
        steps.append(
            {
                "title": "Blocked procedures",
                "detail": ", ".join(
                    f"{row['procedure_name']} {row['result']} in {row['episode']}" for row in blocked
                ),
            }
        )
    steps.append(
        {
            "title": "Action written to the graph",
            "detail": f"{action['assignee_name']} assigned to {action['procedure_name']}.",
        }
    )
    if owner and owner["assignee_id"] != action["assignee_id"]:
        steps.append(
            {
                "title": "Why not the on-call owner",
                "detail": (
                    f"{owner['assignee_name']} OWNS {service['name']} and would run "
                    f"{owner['procedure_name']}. That path ignores the failed attempt."
                ),
            }
        )
    if algorithms.get("shortest_path"):
        steps.append(
            {
                "title": "Shortest action path",
                "detail": " → ".join(algorithms["shortest_path"]),
            }
        )
    if algorithms.get("pagerank"):
        top = ", ".join(row["name"] for row in algorithms["pagerank"][:3])
        steps.append({"title": "PageRank", "detail": f"Most central dependencies: {top}."})
    components = algorithms.get("components") or []
    if components:
        ids = {row["component"] for row in components}
        isolated = [row["name"] for row in components if _is_isolated(row, components)]
        detail = f"{len(ids)} weakly connected components."
        if isolated:
            detail += " Isolated: " + ", ".join(isolated) + "."
        steps.append({"title": "Connected components", "detail": detail})
    if sources:
        steps.append(
            {
                "title": "Source of the decision",
                "detail": (
                    f"{sources[0]['decided_by']} wrote '{sources[0]['title']}' "
                    f"in {sources[0]['doc_title']}: {sources[0]['rationale']}"
                ),
            }
        )
    return steps


def _is_isolated(row, components) -> bool:
    same = [item for item in components if item["component"] == row["component"]]
    return len(same) == 1


def record_outcome(graph, session_id: str, result: str, note: str = "") -> dict:
    if result not in {"success", "failed"}:
        raise ValueError("Result must be success or failed.")
    action = _load_action(graph, session_id)
    existing = fetch(
        graph,
        "MATCH (:Episode {id: $id})-[:ATTEMPTED]->(a:Attempt) RETURN a.id",
        {"id": action["episode_id"]},
        ["id"],
    )
    if existing:
        raise ValueError("This session already has an outcome.")
    attempt_id = _id("att")
    query(
        graph,
        """
        CREATE (:Attempt {id: $id, result: $result, impact_minutes: 0, note: $note})
        """,
        {"id": attempt_id, "result": result, "note": note[:240]},
    )
    query(
        graph,
        """
        MATCH (e:Episode {id: $episode}), (a:Attempt {id: $attempt})
        CREATE (e)-[:ATTEMPTED]->(a)
        """,
        {"episode": action["episode_id"], "attempt": attempt_id},
    )
    if action["procedure_id"]:
        query(
            graph,
            """
            MATCH (a:Attempt {id: $attempt}), (proc:Procedure {id: $proc})
            CREATE (a)-[:USED]->(proc)
            """,
            {"attempt": attempt_id, "proc": action["procedure_id"]},
        )
    if action["assignee_id"]:
        query(
            graph,
            """
            MATCH (a:Attempt {id: $attempt}), (p:Person {id: $person})
            CREATE (a)-[:BY]->(p)
            """,
            {"attempt": attempt_id, "person": action["assignee_id"]},
        )
    if action["cause"]:
        query(
            graph,
            """
            MATCH (a:Attempt {id: $attempt}), (s:Service {id: $service})
            CREATE (a)-[:ON]->(s)
            """,
            {"attempt": attempt_id, "service": action["cause"]},
        )
    status = "done" if result == "success" else "blocked"
    query(
        graph,
        """
        MATCH (h:Handoff {session_id: $session_id, status: 'open'})
        SET h.status = $status
        """,
        {"session_id": session_id, "status": status},
    )
    _write_memory(
        graph,
        session_id,
        "episodic",
        f"Session {session_id} {result}: {action['procedure_name']} by {action['assignee_name']}. {note}".strip(),
        action["episode_id"],
    )
    return {"attempt_id": attempt_id, "result": result, "session_id": session_id}


def memory_feed(graph) -> dict:
    rows = fetch(
        graph,
        """
        MATCH (m:Memory)
        RETURN m.kind, m.text, m.session_id, m.created_at
        ORDER BY m.created_at DESC
        LIMIT 24
        """,
        None,
        ["kind", "text", "session_id", "created_at"],
    )
    grouped = {"episodic": [], "semantic": [], "procedural": []}
    for row in rows:
        grouped.setdefault(row["kind"], []).append(row)
    return grouped


def graph_view(graph) -> dict:
    nodes = fetch(
        graph,
        q.GRAPH_NODES,
        None,
        ["id", "label", "name", "x", "y", "tier", "role", "available", "on_call"],
    )
    edges = fetch(graph, q.GRAPH_EDGES, None, ["source", "target", "type"])
    counts = fetch(graph, "MATCH (n) RETURN count(n)", None, ["nodes"])
    rels = fetch(graph, "MATCH ()-[r]->() RETURN count(r)", None, ["edges"])
    return {
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "nodes": counts[0]["nodes"] if counts else 0,
            "edges": rels[0]["edges"] if rels else 0,
        },
    }
