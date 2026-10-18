"""Click-through of the seeded incident when FalkorDB cannot start on this machine."""

from __future__ import annotations

from app.seed import TENANTS

_VIZ = {"DEPENDS_ON", "ROUTES_TO", "OWNS", "KNOWS", "MEMBER_OF"}


def graph_from_seed(tenant: str) -> dict:
    spec = TENANTS[tenant]
    nodes = []
    for label, props in spec["nodes"]:
        if label not in {"Service", "Person", "Team"}:
            continue
        nodes.append(
            {
                "id": props["id"],
                "label": label,
                "name": props.get("name"),
                "x": props.get("x"),
                "y": props.get("y"),
                "tier": props.get("tier"),
                "role": props.get("role"),
                "available": props.get("available"),
                "on_call": props.get("on_call"),
            }
        )
    edges = []
    for edge in spec["edges"]:
        src, _src_label, rel, dst, _dst_label = edge[:5]
        if rel in _VIZ:
            edges.append({"source": src, "target": dst, "type": rel})
    return {
        "nodes": nodes,
        "edges": edges,
        "counts": {"nodes": len(spec["nodes"]), "edges": len(spec["edges"])},
    }


class Walkthrough:
    def __init__(self) -> None:
        self._runs = {"northwind": 0, "brightpath": 0}
        self._failed = {"northwind": False, "brightpath": False}
        self._open: dict[str, str] = {}
        self._memory = {
            "northwind": {"episodic": [], "semantic": [], "procedural": []},
            "brightpath": {"episodic": [], "semantic": [], "procedural": []},
        }

    def reset(self, tenant: str) -> None:
        self._runs[tenant] = 0
        self._failed[tenant] = False
        self._open.pop(tenant, None)
        self._memory[tenant] = {"episodic": [], "semantic": [], "procedural": []}

    def memory(self, tenant: str) -> dict:
        return self._memory[tenant]

    def outcome(self, tenant: str, session_id: str, result: str) -> dict:
        if not session_id.startswith("ses-"):
            raise ValueError("Unknown session.")
        self._open.pop(tenant, None)
        self._failed[tenant] = result == "failed"
        kind = "episodic"
        text = (
            f"{session_id} failed. Do not repeat the last procedure."
            if result == "failed"
            else f"{session_id} recovered."
        )
        self._memory[tenant][kind].insert(0, {"kind": kind, "text": text, "session_id": session_id})
        return {"attempt_id": f"att-{session_id}", "result": result, "session_id": session_id}

    def run(self, tenant: str, policy: str) -> dict:
        self._runs[tenant] += 1
        number = self._runs[tenant]
        if tenant == "brightpath":
            return self._brightpath(policy, number)
        return self._northwind(policy, number)

    def _remember(self, tenant: str, session_id: str, episodic: str, semantic: str, procedural: str) -> None:
        bucket = self._memory[tenant]
        bucket["episodic"].insert(0, {"kind": "episodic", "text": episodic, "session_id": session_id})
        bucket["semantic"].insert(0, {"kind": "semantic", "text": semantic, "session_id": session_id})
        bucket["procedural"].insert(0, {"kind": "procedural", "text": procedural, "session_id": session_id})

    def _northwind(self, policy: str, number: int) -> dict:
        owner = {
            "assignee_id": "priya",
            "assignee_name": "Priya Shah",
            "assignee_role": "Payments lead",
            "procedure_id": "restart-payments",
            "procedure_name": "Restart payments gateway",
            "via": "Payments gateway",
        }
        session_id = f"ses-north-{number}"
        if policy == "owner":
            return self._pack(
                session_id=session_id,
                policy="owner",
                service={"id": "checkout-api", "name": "Checkout API", "tier": "critical"},
                symptom="latency_spike",
                decision={
                    **owner,
                    "cause_id": "payments-gateway",
                    "cause_name": "Payments gateway",
                    "summary": "Owner policy pages Priya Shah and runs Restart payments gateway.",
                },
                owner=owner,
                blocked=[],
                path=[
                    {"title": "Owner edge", "detail": "Priya Shah OWNS Checkout API."},
                    {"title": "First-line runbook", "detail": "Restart payments gateway has the lowest naive rank."},
                ],
                agents=[],
                coordination=[],
                handoff_id="",
                continued_from="",
            )
        continued = self._open.get("northwind", "")
        blocked = [
            {"procedure_id": "restart-payments", "procedure_name": "Restart payments gateway", "result": "failed", "episode": "inc-1042"},
            {"procedure_id": "scale-checkout", "procedure_name": "Scale checkout-api", "result": "no_effect", "episode": "inc-1042"},
        ]
        if self._failed["northwind"]:
            procedure_id, procedure_name = "promote-read-replica", "Promote read replica"
            blocked.append(
                {"procedure_id": "failover-replica", "procedure_name": "Fail over to replica", "result": "failed", "episode": continued or "live"}
            )
            continued = ""
        else:
            procedure_id, procedure_name = "failover-replica", "Fail over to replica"
        handoff_id = f"handoff-north-{number}"
        self._open["northwind"] = handoff_id
        summary = f"Assign Jordan Lee to {procedure_name} on Postgres primary. Blocked: restart-payments."
        self._remember(
            "northwind",
            session_id,
            "INC-1042: Checkout latency. Restarting payments ran 42 minutes and did not recover.",
            "checkout-api / latency_spike has previously been caused by Postgres primary.",
            "Do not repeat Restart payments gateway.",
        )
        return self._pack(
            session_id=session_id,
            policy="memory",
            service={"id": "checkout-api", "name": "Checkout API", "tier": "critical"},
            symptom="latency_spike",
            decision={
                "assignee_id": "jordan",
                "assignee_name": "Jordan Lee",
                "assignee_role": "SRE",
                "procedure_id": procedure_id,
                "procedure_name": procedure_name,
                "cause_id": "postgres-primary",
                "cause_name": "Postgres primary",
                "summary": summary,
                "on_call": False,
            },
            owner=owner,
            blocked=blocked,
            path=[
                {"title": "Shared recall", "detail": "INC-1042 caused this symptom at Postgres primary (42 min)."},
                {"title": "Cause hop", "detail": "INC-1042 AFFECTED Checkout API and CAUSED_BY Postgres primary."},
                {"title": "Blocked procedures", "detail": "Restart payments gateway failed in inc-1042."},
                {"title": "Action written to the graph", "detail": f"Jordan Lee assigned to {procedure_name}."},
                {"title": "Why not the on-call owner", "detail": "Priya Shah OWNS Checkout API and would restart payments."},
                {"title": "Shortest action path", "detail": "Checkout API → Postgres primary → Postgres replica"},
                {"title": "Source of the decision", "detail": "Priya Shah wrote the postmortem. Jordan is still the person who has done the failover."},
            ],
            agents=[
                {"name": "Archivist", "track": "Agent memory and coordination", "summary": "Wrote the recall, and the three memory kinds."},
                {"name": "Cartographer", "track": "Agents that act on connected data", "summary": summary},
                {"name": "Liaison", "track": "Company brain", "summary": "Wrote a handoff the next session can read."},
            ],
            coordination=[
                {"agent": "Archivist", "rel": "WROTE", "label": "Recall"},
                {"agent": "Cartographer", "rel": "READ", "label": "Recall"},
                {"agent": "Cartographer", "rel": "WROTE", "label": "Action"},
                {"agent": "Liaison", "rel": "READ", "label": "Action"},
                {"agent": "Liaison", "rel": "WROTE", "label": "Handoff"},
            ],
            handoff_id=handoff_id,
            continued_from=continued if number > 1 and not self._failed["northwind"] else ("" if number == 1 else continued),
        )

    def _brightpath(self, policy: str, number: int) -> dict:
        owner = {
            "assignee_id": "maya",
            "assignee_name": "Maya Chen",
            "assignee_role": "Search lead",
            "procedure_id": "clear-cache",
            "procedure_name": "Clear search cache",
            "via": "Elasticsearch",
        }
        session_id = f"ses-bright-{number}"
        if policy == "owner":
            return self._pack(
                session_id=session_id,
                policy="owner",
                service={"id": "search-api", "name": "Search API", "tier": "critical"},
                symptom="relevance_drop",
                decision={
                    **owner,
                    "cause_id": "elastic",
                    "cause_name": "Elasticsearch",
                    "summary": "Owner policy pages Maya Chen and clears the search cache.",
                },
                owner=owner,
                blocked=[],
                path=[{"title": "Owner edge", "detail": "Maya Chen OWNS Search API."}],
                agents=[],
                coordination=[],
                handoff_id="",
                continued_from="",
            )
        continued = self._open.get("brightpath", "") if number > 1 else ""
        handoff_id = f"handoff-bright-{number}"
        self._open["brightpath"] = handoff_id
        self._remember(
            "brightpath",
            session_id,
            "INC-B12: clearing the cache did not restore rankings.",
            "search-api / relevance_drop has previously been caused by the ranking model.",
            "Do not repeat Clear search cache.",
        )
        return self._pack(
            session_id=session_id,
            policy="memory",
            service={"id": "search-api", "name": "Search API", "tier": "critical"},
            symptom="relevance_drop",
            decision={
                "assignee_id": "noah",
                "assignee_name": "Noah Williams",
                "assignee_role": "ML engineer",
                "procedure_id": "rollback-ranking",
                "procedure_name": "Roll back ranking model",
                "cause_id": "ranking-model",
                "cause_name": "Ranking model",
                "summary": "Assign Noah Williams to roll back the ranking model.",
                "on_call": False,
            },
            owner=owner,
            blocked=[{"procedure_id": "clear-cache", "procedure_name": "Clear search cache", "result": "failed", "episode": "inc-b12"}],
            path=[
                {"title": "Cause hop", "detail": "INC-B12 AFFECTED Search API and CAUSED_BY Ranking model."},
                {"title": "Action written to the graph", "detail": "Noah Williams assigned to Roll back ranking model."},
                {"title": "Why not the on-call owner", "detail": "Maya Chen would clear the cache. That attempt failed."},
            ],
            agents=[
                {"name": "Archivist", "track": "Agent memory and coordination", "summary": "Brightpath memory is a different graph."},
                {"name": "Cartographer", "track": "Agents that act on connected data", "summary": "Rolled the ranker, not the cache."},
                {"name": "Liaison", "track": "Company brain", "summary": "Handoff stays inside Brightpath."},
            ],
            coordination=[
                {"agent": "Archivist", "rel": "WROTE", "label": "Recall"},
                {"agent": "Cartographer", "rel": "READ", "label": "Recall"},
                {"agent": "Liaison", "rel": "WROTE", "label": "Handoff"},
            ],
            handoff_id=handoff_id,
            continued_from=continued,
        )

    def _pack(self, **kwargs) -> dict:
        service = kwargs["service"]["id"]
        kwargs["algorithms"] = {
            "pagerank": [
                {"name": "Postgres primary", "score": 0.31},
                {"name": "Checkout API", "score": 0.22},
                {"name": "Payments gateway", "score": 0.14},
            ],
            "shortest_path": ["Checkout API", "Postgres primary", "Postgres replica"] if "checkout" in service else ["Search API", "Ranking model"],
            "components": [
                {"name": "Checkout API", "component": 1},
                {"name": "Experiments lab", "component": 2},
            ],
            "notes": ["algo.pageRank", "algo.betweenness", "algo.WCC", "shortestPath"],
        }
        kwargs["blast"] = [
            {"id": "storefront", "name": "Web storefront", "tier": "edge"},
            {"id": "billing-api", "name": "Billing API", "tier": "standard"},
            {"id": "ledger", "name": "Ledger", "tier": "critical"},
        ]
        kwargs["upstream"] = [{"id": "postgres-primary", "name": "Postgres primary"}]
        kwargs["recall_summary"] = kwargs["path"][0]["detail"] if kwargs["path"] else ""
        kwargs["sources"] = []
        return kwargs


def ask(tenant: str, question: str, service: str | None) -> dict:
    if tenant == "brightpath":
        rows = {
            "who_knows": [{"person": "Noah Williams", "role": "ML engineer", "available": True}, {"person": "Ava Singh", "role": "ML engineer", "available": True}],
            "who_worked": [{"person": "Noah Williams", "role": "ML engineer", "project": "Ranking Rollback"}],
            "blast": [{"id": "shop-web", "service": "Shop web", "tier": "edge"}],
            "last_time": [{"episode": "inc-b12", "name": "INC-B12", "symptom": "relevance_drop", "summary": "Cache flush failed.", "impact_minutes": 35, "cause": "Ranking model", "result": "failed", "procedure": "Clear search cache", "person": "Chris Patel"}],
            "decision": [{"title": "Do not flush the cache for relevance drops", "rationale": "Rollback is the procedure that worked.", "document": "INC-B12 postmortem", "kind": "postmortem", "decided_by": "Maya Chen", "episode": "INC-B12"}],
            "ownership": [{"service": "Search API", "owners": ["Maya Chen"], "experts": ["Maya Chen"]}],
        }.get(question, [])
    else:
        rows = {
            "who_knows": [{"person": "Jordan Lee", "role": "SRE", "available": True}, {"person": "Riley Chen", "role": "Data engineer", "available": True}],
            "who_worked": [{"person": "Jordan Lee", "role": "SRE", "project": "Failover Drill"}, {"person": "Riley Chen", "role": "Data engineer", "project": "Ledger v2"}],
            "blast": [
                {"id": "checkout-api", "service": "Checkout API", "tier": "critical"},
                {"id": "ledger", "service": "Ledger", "tier": "critical"},
                {"id": "payments-gateway", "service": "Payments gateway", "tier": "critical"},
            ],
            "last_time": [{"episode": "inc-1042", "name": "INC-1042", "symptom": "latency_spike", "summary": "Restarting payments did not recover.", "impact_minutes": 42, "cause": "Postgres primary", "result": "failed", "procedure": "Restart payments gateway", "person": "Alex Kim"}],
            "decision": [{"title": "Do not restart payments for checkout latency", "rationale": "The gateway was a symptom. The primary was saturated.", "document": "INC-1042 postmortem", "kind": "postmortem", "decided_by": "Priya Shah", "episode": "INC-1042"}],
            "ownership": [{"service": "Checkout API", "owners": ["Priya Shah"], "experts": ["Priya Shah"]}],
        }.get(question, [])
    titles = {
        "who_knows": "Who knows this system?",
        "who_worked": "Who has worked on this system?",
        "blast": "What breaks if this service goes down?",
        "last_time": "What happened last time?",
        "decision": "Where did this decision come from?",
        "ownership": "Who owns what, and who knows it?",
    }
    return {"question": question, "title": titles.get(question, question), "service": service, "rows": rows}
