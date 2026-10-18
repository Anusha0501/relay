"""Company graphs. Each tenant is its own FalkorDB graph."""

from __future__ import annotations

from app.db import fetch, query

SEED_VERSION = 1

LABELS = {
    "Person",
    "Team",
    "Service",
    "Project",
    "Procedure",
    "Episode",
    "Attempt",
    "Document",
    "Decision",
    "Agent",
    "Meta",
}
RELS = {
    "MEMBER_OF",
    "OWNS",
    "KNOWS",
    "WORKED_ON",
    "USES",
    "DEPENDS_ON",
    "ROUTES_TO",
    "APPLIES_TO",
    "AFFECTED",
    "CAUSED_BY",
    "ATTEMPTED",
    "USED",
    "BY",
    "ON",
    "DESCRIBES",
    "ABOUT",
    "DECIDED_BY",
    "SOURCED_FROM",
    "AUTHORED",
}

SCENARIOS = {
    "northwind": [
        {
            "id": "checkout-latency",
            "service": "checkout-api",
            "symptom": "latency_spike",
            "title": "Checkout latency spike",
            "detail": "Checkout p95 crossed 4 seconds. The on-call roster says page Priya Shah.",
        }
    ],
    "brightpath": [
        {
            "id": "search-relevance",
            "service": "search-api",
            "symptom": "relevance_drop",
            "title": "Search relevance drop",
            "detail": "Shop search is returning stale rankings. The on-call roster says page Maya Chen.",
        }
    ],
}


def _northwind() -> dict:
    return {
        "company": "Northwind Cloud",
        "blurb": "Payments company. The alerting service owner is not the person who has fixed this failure.",
        "nodes": [
            ("Team", {"id": "team-payments", "name": "Payments", "x": 18, "y": 8}),
            ("Team", {"id": "team-platform", "name": "Platform", "x": 36, "y": 8}),
            ("Team", {"id": "team-sre", "name": "SRE", "x": 54, "y": 8}),
            ("Team", {"id": "team-data", "name": "Data", "x": 72, "y": 8}),
            ("Team", {"id": "team-security", "name": "Security", "x": 86, "y": 8}),
            ("Team", {"id": "team-product", "name": "Product", "x": 8, "y": 8}),
            ("Person", {"id": "priya", "name": "Priya Shah", "role": "Payments lead", "available": True, "on_call": True, "x": 22, "y": 90}),
            ("Person", {"id": "alex", "name": "Alex Kim", "role": "Platform engineer", "available": False, "on_call": False, "x": 38, "y": 90}),
            ("Person", {"id": "jordan", "name": "Jordan Lee", "role": "SRE", "available": True, "on_call": False, "x": 54, "y": 90}),
            ("Person", {"id": "riley", "name": "Riley Chen", "role": "Data engineer", "available": True, "on_call": False, "x": 70, "y": 90}),
            ("Person", {"id": "morgan", "name": "Morgan Diaz", "role": "Security", "available": True, "on_call": False, "x": 84, "y": 90}),
            ("Person", {"id": "sam", "name": "Sam Okonkwo", "role": "Product", "available": True, "on_call": False, "x": 8, "y": 90}),
            ("Person", {"id": "taylor", "name": "Taylor Brooks", "role": "Payments, new hire", "available": True, "on_call": False, "x": 22, "y": 78}),
            ("Service", {"id": "storefront", "name": "Web storefront", "tier": "edge", "summary": "Customer-facing shop.", "x": 8, "y": 28}),
            ("Service", {"id": "billing-api", "name": "Billing API", "tier": "standard", "summary": "Invoices and receipts.", "x": 8, "y": 46}),
            ("Service", {"id": "notifications", "name": "Notifications", "tier": "standard", "summary": "Email and SMS.", "x": 8, "y": 64}),
            ("Service", {"id": "checkout-api", "name": "Checkout API", "tier": "critical", "summary": "Places orders.", "x": 30, "y": 46}),
            ("Service", {"id": "payments-gateway", "name": "Payments gateway", "tier": "critical", "summary": "Authorizes cards.", "x": 52, "y": 28}),
            ("Service", {"id": "fraud-service", "name": "Fraud service", "tier": "standard", "summary": "Scores orders.", "x": 74, "y": 18}),
            ("Service", {"id": "redis-cache", "name": "Redis cache", "tier": "standard", "summary": "Fraud feature cache.", "x": 92, "y": 18}),
            ("Service", {"id": "ledger", "name": "Ledger", "tier": "critical", "summary": "Settles money.", "x": 52, "y": 64}),
            ("Service", {"id": "postgres-primary", "name": "Postgres primary", "tier": "critical", "summary": "System of record.", "x": 74, "y": 46}),
            ("Service", {"id": "postgres-replica", "name": "Postgres replica", "tier": "standard", "summary": "Failover target.", "x": 92, "y": 46}),
            ("Service", {"id": "experiments-lab", "name": "Experiments lab", "tier": "experiment", "summary": "Isolated sandbox.", "x": 92, "y": 70}),
            ("Project", {"id": "checkout-rewrite", "name": "Checkout Rewrite", "status": "active"}),
            ("Project", {"id": "failover-drill", "name": "Failover Drill", "status": "complete"}),
            ("Project", {"id": "ledger-v2", "name": "Ledger v2", "status": "active"}),
            ("Procedure", {"id": "restart-payments", "name": "Restart payments gateway", "summary": "Roll the payments process.", "naive_rank": 1}),
            ("Procedure", {"id": "scale-checkout", "name": "Scale checkout-api", "summary": "Add checkout replicas.", "naive_rank": 2}),
            ("Procedure", {"id": "failover-replica", "name": "Fail over to replica", "summary": "Promote Postgres replica and repoint writers.", "naive_rank": 4}),
            ("Procedure", {"id": "promote-read-replica", "name": "Promote read replica", "summary": "Promote the replica without the full failover runbook.", "naive_rank": 5}),
            ("Episode", {"id": "inc-1042", "name": "INC-1042", "symptom": "latency_spike", "impact_minutes": 42, "started_at": 200, "live": False, "summary": "Checkout latency. Restarting payments ran 42 minutes and did not recover."}),
            ("Episode", {"id": "inc-998", "name": "INC-998", "symptom": "saturation", "impact_minutes": 8, "started_at": 100, "live": False, "summary": "Ledger saturation. Promoting the replica recovered the primary in 8 minutes."}),
            ("Attempt", {"id": "att-1042-restart", "result": "failed", "impact_minutes": 42}),
            ("Attempt", {"id": "att-1042-scale", "result": "no_effect", "impact_minutes": 42}),
            ("Attempt", {"id": "att-998-failover", "result": "success", "impact_minutes": 8}),
            ("Document", {"id": "pm-1042", "title": "INC-1042 postmortem", "kind": "postmortem", "summary": "The gateway was a symptom. The primary was saturated."}),
            ("Document", {"id": "adr-014", "title": "ADR-014 Prefer replica failover", "kind": "decision", "summary": "When the primary is saturated, fail over. Do not restart payments."}),
            ("Document", {"id": "rb-restart", "title": "Runbook: restart payments", "kind": "runbook", "summary": "First-line latency runbook. It is the naive page."}),
            ("Document", {"id": "rb-failover", "title": "Runbook: replica failover", "kind": "runbook", "summary": "Promote postgres-replica, then repoint checkout and ledger."}),
            ("Decision", {"id": "dec-1042", "title": "Do not restart payments for checkout latency", "rationale": "INC-1042 showed the gateway was a symptom. The primary was saturated. The failover drill is the procedure that worked."}),
            ("Agent", {"id": "archivist", "name": "Archivist", "focus": "Memory"}),
            ("Agent", {"id": "cartographer", "name": "Cartographer", "focus": "Action"}),
            ("Agent", {"id": "liaison", "name": "Liaison", "focus": "Handoff"}),
        ],
        "edges": [
            ("priya", "Person", "MEMBER_OF", "team-payments", "Team"),
            ("taylor", "Person", "MEMBER_OF", "team-payments", "Team"),
            ("alex", "Person", "MEMBER_OF", "team-platform", "Team"),
            ("jordan", "Person", "MEMBER_OF", "team-sre", "Team"),
            ("riley", "Person", "MEMBER_OF", "team-data", "Team"),
            ("morgan", "Person", "MEMBER_OF", "team-security", "Team"),
            ("sam", "Person", "MEMBER_OF", "team-product", "Team"),
            ("priya", "Person", "OWNS", "checkout-api", "Service"),
            ("priya", "Person", "OWNS", "payments-gateway", "Service"),
            ("priya", "Person", "KNOWS", "checkout-api", "Service"),
            ("priya", "Person", "KNOWS", "payments-gateway", "Service"),
            ("alex", "Person", "KNOWS", "payments-gateway", "Service"),
            ("jordan", "Person", "KNOWS", "postgres-primary", "Service"),
            ("jordan", "Person", "KNOWS", "postgres-replica", "Service"),
            ("riley", "Person", "KNOWS", "postgres-primary", "Service"),
            ("riley", "Person", "KNOWS", "ledger", "Service"),
            ("morgan", "Person", "KNOWS", "fraud-service", "Service"),
            ("priya", "Person", "WORKED_ON", "checkout-rewrite", "Project"),
            ("alex", "Person", "WORKED_ON", "checkout-rewrite", "Project"),
            ("jordan", "Person", "WORKED_ON", "failover-drill", "Project"),
            ("riley", "Person", "WORKED_ON", "ledger-v2", "Project"),
            ("checkout-rewrite", "Project", "USES", "checkout-api", "Service"),
            ("checkout-rewrite", "Project", "USES", "payments-gateway", "Service"),
            ("failover-drill", "Project", "USES", "postgres-primary", "Service"),
            ("failover-drill", "Project", "USES", "postgres-replica", "Service"),
            ("ledger-v2", "Project", "USES", "ledger", "Service"),
            ("ledger-v2", "Project", "USES", "postgres-primary", "Service"),
            ("storefront", "Service", "DEPENDS_ON", "checkout-api", "Service", {"dist": 1}),
            ("billing-api", "Service", "DEPENDS_ON", "checkout-api", "Service", {"dist": 1}),
            ("notifications", "Service", "DEPENDS_ON", "checkout-api", "Service", {"dist": 1}),
            ("checkout-api", "Service", "DEPENDS_ON", "payments-gateway", "Service", {"dist": 1}),
            ("checkout-api", "Service", "DEPENDS_ON", "postgres-primary", "Service", {"dist": 1}),
            ("payments-gateway", "Service", "DEPENDS_ON", "postgres-primary", "Service", {"dist": 1}),
            ("payments-gateway", "Service", "DEPENDS_ON", "fraud-service", "Service", {"dist": 2}),
            ("fraud-service", "Service", "DEPENDS_ON", "redis-cache", "Service", {"dist": 1}),
            ("ledger", "Service", "DEPENDS_ON", "postgres-primary", "Service", {"dist": 1}),
            ("postgres-primary", "Service", "ROUTES_TO", "postgres-replica", "Service", {"dist": 1}),
            ("restart-payments", "Procedure", "APPLIES_TO", "payments-gateway", "Service"),
            ("scale-checkout", "Procedure", "APPLIES_TO", "checkout-api", "Service"),
            ("failover-replica", "Procedure", "APPLIES_TO", "postgres-primary", "Service"),
            ("promote-read-replica", "Procedure", "APPLIES_TO", "postgres-primary", "Service"),
            ("inc-1042", "Episode", "AFFECTED", "checkout-api", "Service"),
            ("inc-1042", "Episode", "CAUSED_BY", "postgres-primary", "Service"),
            ("inc-998", "Episode", "AFFECTED", "ledger", "Service"),
            ("inc-998", "Episode", "CAUSED_BY", "postgres-primary", "Service"),
            ("inc-1042", "Episode", "ATTEMPTED", "att-1042-restart", "Attempt"),
            ("inc-1042", "Episode", "ATTEMPTED", "att-1042-scale", "Attempt"),
            ("inc-998", "Episode", "ATTEMPTED", "att-998-failover", "Attempt"),
            ("att-1042-restart", "Attempt", "USED", "restart-payments", "Procedure"),
            ("att-1042-restart", "Attempt", "BY", "alex", "Person"),
            ("att-1042-restart", "Attempt", "ON", "payments-gateway", "Service"),
            ("att-1042-scale", "Attempt", "USED", "scale-checkout", "Procedure"),
            ("att-1042-scale", "Attempt", "BY", "priya", "Person"),
            ("att-1042-scale", "Attempt", "ON", "checkout-api", "Service"),
            ("att-998-failover", "Attempt", "USED", "failover-replica", "Procedure"),
            ("att-998-failover", "Attempt", "BY", "jordan", "Person"),
            ("att-998-failover", "Attempt", "ON", "postgres-primary", "Service"),
            ("pm-1042", "Document", "DESCRIBES", "postgres-primary", "Service"),
            ("rb-restart", "Document", "DESCRIBES", "payments-gateway", "Service"),
            ("rb-failover", "Document", "DESCRIBES", "postgres-replica", "Service"),
            ("dec-1042", "Decision", "ABOUT", "inc-1042", "Episode"),
            ("dec-1042", "Decision", "DECIDED_BY", "priya", "Person"),
            ("dec-1042", "Decision", "SOURCED_FROM", "pm-1042", "Document"),
            ("dec-1042", "Decision", "SOURCED_FROM", "adr-014", "Document"),
            ("pm-1042", "Document", "AUTHORED", "priya", "Person"),
        ],
    }


def _brightpath() -> dict:
    return {
        "company": "Brightpath",
        "blurb": "A second company in its own graph. Northwind people and incidents are not visible here.",
        "nodes": [
            ("Team", {"id": "team-search", "name": "Search", "x": 20, "y": 8}),
            ("Team", {"id": "team-ml", "name": "ML", "x": 50, "y": 8}),
            ("Team", {"id": "team-platform", "name": "Platform", "x": 78, "y": 8}),
            ("Person", {"id": "maya", "name": "Maya Chen", "role": "Search lead", "available": True, "on_call": True, "x": 20, "y": 90}),
            ("Person", {"id": "noah", "name": "Noah Williams", "role": "ML engineer", "available": True, "on_call": False, "x": 46, "y": 90}),
            ("Person", {"id": "ava", "name": "Ava Singh", "role": "ML engineer", "available": True, "on_call": False, "x": 64, "y": 90}),
            ("Person", {"id": "chris", "name": "Chris Patel", "role": "Platform engineer", "available": True, "on_call": False, "x": 82, "y": 90}),
            ("Service", {"id": "shop-web", "name": "Shop web", "tier": "edge", "summary": "Storefront search box.", "x": 12, "y": 42}),
            ("Service", {"id": "search-api", "name": "Search API", "tier": "critical", "summary": "Query serving.", "x": 36, "y": 42}),
            ("Service", {"id": "ranking-model", "name": "Ranking model", "tier": "critical", "summary": "Current ranker.", "x": 62, "y": 28}),
            ("Service", {"id": "elastic", "name": "Elasticsearch", "tier": "critical", "summary": "Search index.", "x": 62, "y": 58}),
            ("Service", {"id": "ingest", "name": "Ingest", "tier": "standard", "summary": "Index pipeline.", "x": 86, "y": 58}),
            ("Service", {"id": "sandbox-lab", "name": "Sandbox lab", "tier": "experiment", "summary": "Isolated from search.", "x": 86, "y": 28}),
            ("Project", {"id": "search-platform", "name": "Search Platform", "status": "active"}),
            ("Project", {"id": "ranking-rollback", "name": "Ranking Rollback", "status": "complete"}),
            ("Procedure", {"id": "clear-cache", "name": "Clear search cache", "summary": "Flush Elasticsearch caches.", "naive_rank": 1}),
            ("Procedure", {"id": "rollback-ranking", "name": "Roll back ranking model", "summary": "Serve the previous ranker.", "naive_rank": 4}),
            ("Procedure", {"id": "freeze-ingest", "name": "Freeze ingest", "summary": "Stop writes to the index.", "naive_rank": 6}),
            ("Episode", {"id": "inc-b12", "name": "INC-B12", "symptom": "relevance_drop", "impact_minutes": 35, "started_at": 200, "live": False, "summary": "Search went stale. Clearing the cache did not restore rankings."}),
            ("Episode", {"id": "inc-b4", "name": "INC-B4", "symptom": "drift", "impact_minutes": 6, "started_at": 100, "live": False, "summary": "Ranking drift. Rolling back the model recovered relevance in 6 minutes."}),
            ("Attempt", {"id": "att-b12-cache", "result": "failed", "impact_minutes": 35}),
            ("Attempt", {"id": "att-b4-rollback", "result": "success", "impact_minutes": 6}),
            ("Document", {"id": "pm-b12", "title": "INC-B12 postmortem", "kind": "postmortem", "summary": "The index was healthy. A bad ranking deploy was the cause."}),
            ("Document", {"id": "adr-b2", "title": "ADR-B2 Roll back ranker first", "kind": "decision", "summary": "Relevance drops get a model rollback, not a cache flush."}),
            ("Decision", {"id": "dec-b12", "title": "Do not flush the cache for relevance drops", "rationale": "INC-B12 showed cache flushes hide a bad ranker. Rollback is the procedure that worked."}),
            ("Agent", {"id": "archivist", "name": "Archivist", "focus": "Memory"}),
            ("Agent", {"id": "cartographer", "name": "Cartographer", "focus": "Action"}),
            ("Agent", {"id": "liaison", "name": "Liaison", "focus": "Handoff"}),
        ],
        "edges": [
            ("maya", "Person", "MEMBER_OF", "team-search", "Team"),
            ("noah", "Person", "MEMBER_OF", "team-ml", "Team"),
            ("ava", "Person", "MEMBER_OF", "team-ml", "Team"),
            ("chris", "Person", "MEMBER_OF", "team-platform", "Team"),
            ("maya", "Person", "OWNS", "search-api", "Service"),
            ("maya", "Person", "KNOWS", "search-api", "Service"),
            ("noah", "Person", "KNOWS", "ranking-model", "Service"),
            ("ava", "Person", "KNOWS", "ranking-model", "Service"),
            ("chris", "Person", "KNOWS", "elastic", "Service"),
            ("maya", "Person", "WORKED_ON", "search-platform", "Project"),
            ("chris", "Person", "WORKED_ON", "search-platform", "Project"),
            ("noah", "Person", "WORKED_ON", "ranking-rollback", "Project"),
            ("ava", "Person", "WORKED_ON", "ranking-rollback", "Project"),
            ("search-platform", "Project", "USES", "search-api", "Service"),
            ("search-platform", "Project", "USES", "elastic", "Service"),
            ("ranking-rollback", "Project", "USES", "ranking-model", "Service"),
            ("shop-web", "Service", "DEPENDS_ON", "search-api", "Service", {"dist": 1}),
            ("search-api", "Service", "DEPENDS_ON", "ranking-model", "Service", {"dist": 1}),
            ("search-api", "Service", "DEPENDS_ON", "elastic", "Service", {"dist": 1}),
            ("elastic", "Service", "DEPENDS_ON", "ingest", "Service", {"dist": 1}),
            ("clear-cache", "Procedure", "APPLIES_TO", "elastic", "Service"),
            ("rollback-ranking", "Procedure", "APPLIES_TO", "ranking-model", "Service"),
            ("freeze-ingest", "Procedure", "APPLIES_TO", "ingest", "Service"),
            ("inc-b12", "Episode", "AFFECTED", "search-api", "Service"),
            ("inc-b12", "Episode", "CAUSED_BY", "ranking-model", "Service"),
            ("inc-b4", "Episode", "AFFECTED", "search-api", "Service"),
            ("inc-b4", "Episode", "CAUSED_BY", "ranking-model", "Service"),
            ("inc-b12", "Episode", "ATTEMPTED", "att-b12-cache", "Attempt"),
            ("inc-b4", "Episode", "ATTEMPTED", "att-b4-rollback", "Attempt"),
            ("att-b12-cache", "Attempt", "USED", "clear-cache", "Procedure"),
            ("att-b12-cache", "Attempt", "BY", "chris", "Person"),
            ("att-b12-cache", "Attempt", "ON", "elastic", "Service"),
            ("att-b4-rollback", "Attempt", "USED", "rollback-ranking", "Procedure"),
            ("att-b4-rollback", "Attempt", "BY", "noah", "Person"),
            ("att-b4-rollback", "Attempt", "ON", "ranking-model", "Service"),
            ("pm-b12", "Document", "DESCRIBES", "ranking-model", "Service"),
            ("dec-b12", "Decision", "ABOUT", "inc-b12", "Episode"),
            ("dec-b12", "Decision", "DECIDED_BY", "maya", "Person"),
            ("dec-b12", "Decision", "SOURCED_FROM", "pm-b12", "Document"),
            ("dec-b12", "Decision", "SOURCED_FROM", "adr-b2", "Document"),
            ("pm-b12", "Document", "AUTHORED", "maya", "Person"),
        ],
    }


TENANTS = {
    "northwind": _northwind(),
    "brightpath": _brightpath(),
}


def _create_node(graph, label: str, props: dict) -> None:
    if label not in LABELS:
        raise ValueError(label)
    keys = ", ".join(f"{key}: ${key}" for key in props)
    query(graph, f"CREATE (:{label} {{{keys}}})", props)


def _relate(graph, src, src_label, rel, dst, dst_label, props=None) -> None:
    if rel not in RELS or src_label not in LABELS or dst_label not in LABELS:
        raise ValueError(rel)
    params = {"src": src, "dst": dst}
    if props:
        params.update(props)
        assignments = ", ".join(f"r.{key} = ${key}" for key in props)
        cypher = f"""
        MATCH (a:{src_label} {{id: $src}}), (b:{dst_label} {{id: $dst}})
        CREATE (a)-[r:{rel}]->(b)
        SET {assignments}
        """
    else:
        cypher = f"""
        MATCH (a:{src_label} {{id: $src}}), (b:{dst_label} {{id: $dst}})
        CREATE (a)-[:{rel}]->(b)
        """
    query(graph, cypher, params)


def seed_graph(graph, spec: dict) -> None:
    query(graph, "MATCH (n) DETACH DELETE n")
    for label, props in spec["nodes"]:
        _create_node(graph, label, props)
    for edge in spec["edges"]:
        src, src_label, rel, dst, dst_label = edge[:5]
        props = edge[5] if len(edge) > 5 else None
        _relate(graph, src, src_label, rel, dst, dst_label, props)
    _create_node(graph, "Meta", {"id": "seed", "version": SEED_VERSION, "company": spec["company"]})


def graph_is_current(graph) -> bool:
    rows = fetch(graph, "MATCH (m:Meta {id:'seed'}) RETURN m.version", None, ["version"])
    return bool(rows) and rows[0]["version"] == SEED_VERSION


def ensure_seeded(db) -> None:
    for tenant, spec in TENANTS.items():
        graph = db.select_graph(f"relay_{tenant}")
        if not graph_is_current(graph):
            seed_graph(graph, spec)


def reset_tenant(graph, tenant: str) -> None:
    seed_graph(graph, TENANTS[tenant])
