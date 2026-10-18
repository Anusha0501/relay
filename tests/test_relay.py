"""The graph has to change the decision, and the next session has to see it."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agents import cartographer, liaison, record_outcome, run_incident
from app.company import ask
from app.db import fetch, query, reset_connection
from app.seed import ensure_seeded, reset_tenant


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    if not os.environ.get("FALKORDB_HOST", "").strip():
        path = tmp_path_factory.mktemp("falkor") / "relay.db"
        os.environ["FALKORDB_PATH"] = str(path)
    reset_connection()
    from app.db import open_db

    db, _backend = open_db()
    ensure_seeded(db)
    return db


@pytest.fixture()
def graphs(database):
    north = database.select_graph("relay_northwind")
    bright = database.select_graph("relay_brightpath")
    reset_tenant(north, "northwind")
    reset_tenant(bright, "brightpath")
    return north, bright


def test_memory_pages_the_person_who_fixed_the_cause_not_the_owner(graphs):
    north, _bright = graphs
    result = run_incident(north, "checkout-api", "latency_spike", "memory")

    assert result["decision"]["assignee_id"] == "jordan"
    assert result["decision"]["procedure_id"] == "failover-replica"
    assert result["decision"]["cause_id"] == "postgres-primary"
    assert result["owner_would_have"]["assignee_id"] == "priya"
    assert result["owner_would_have"]["procedure_id"] == "restart-payments"
    assert "restart-payments" in {row["procedure_id"] for row in result["blocked"]}
    assert any(step["title"] == "Source of the decision" for step in result["path"])
    assert any(edge["rel"] == "READ" and edge["agent"] == "Cartographer" for edge in result["coordination"])
    assert any(edge["rel"] == "WROTE" and edge["agent"] == "Liaison" for edge in result["coordination"])


def test_owner_policy_does_not_write_a_handoff(graphs):
    north, _bright = graphs
    result = run_incident(north, "checkout-api", "latency_spike", "owner")
    assert result["decision"]["assignee_id"] == "priya"
    assert result["handoff_id"] == ""
    later = run_incident(north, "checkout-api", "latency_spike", "memory")
    assert later["continued_from"] == ""
    assert later["decision"]["assignee_id"] == "jordan"


def test_next_session_reads_the_handoff_from_the_graph(graphs):
    north, _bright = graphs
    first = run_incident(north, "checkout-api", "latency_spike", "memory")
    second = run_incident(north, "checkout-api", "latency_spike", "memory")

    assert second["continued_from"] == first["handoff_id"]
    assert second["decision"]["assignee_id"] == "jordan"
    assert second["decision"]["procedure_id"] == "failover-replica"
    stored = fetch(
        north,
        "MATCH (h:Handoff {id: $id}) RETURN h.status",
        {"id": first["handoff_id"]},
        ["status"],
    )
    assert stored[0]["status"] == "continued"


def test_a_failed_outcome_blocks_the_procedure_for_the_next_crew(graphs):
    north, _bright = graphs
    first = run_incident(north, "checkout-api", "latency_spike", "memory")
    record_outcome(north, first["session_id"], "failed", "Replica was too far behind.")
    second = run_incident(north, "checkout-api", "latency_spike", "memory")

    assert second["decision"]["procedure_id"] == "promote-read-replica"
    assert "failover-replica" in {row["procedure_id"] for row in second["blocked"]}
    assert second["decision"]["assignee_id"] == "jordan"


def test_cartographer_uses_recall_instead_of_a_local_variable(graphs):
    north, _bright = graphs
    from app.agents import archivist

    session_id = "ses-tamper"
    archivist(north, session_id, "checkout-api", "latency_spike")
    query(
        north,
        """
        MATCH (r:Recall {session_id: $session_id})
        SET r.blocked_procedures = 'failover-replica|restart-payments|scale-checkout'
        """,
        {"session_id": session_id},
    )
    cartographer(north, session_id)
    action = fetch(
        north,
        "MATCH (a:Action {session_id: $session_id}) RETURN a.procedure_id, a.assignee_id",
        {"session_id": session_id},
        ["procedure_id", "assignee_id"],
    )
    assert action[0]["procedure_id"] == "promote-read-replica"
    assert action[0]["assignee_id"] == "jordan"


def test_liaison_follows_the_action_node_written_by_cartographer(graphs):
    north, _bright = graphs
    from app.agents import archivist

    session_id = "ses-handoff"
    archivist(north, session_id, "checkout-api", "latency_spike")
    cartographer(north, session_id)
    query(
        north,
        """
        MATCH (a:Action {session_id: $session_id})
        SET a.assignee_id = 'riley', a.assignee_name = 'Riley Chen'
        """,
        {"session_id": session_id},
    )
    liaison(north, session_id)
    assigned = fetch(
        north,
        """
        MATCH (:Handoff {session_id: $session_id})-[:ASSIGNS]->(p:Person)
        RETURN p.id
        """,
        {"session_id": session_id},
        ["id"],
    )
    assert assigned[0]["id"] == "riley"


def test_tenants_are_separate_graphs(graphs):
    north, bright = graphs
    north_run = run_incident(north, "checkout-api", "latency_spike", "memory")
    bright_run = run_incident(bright, "search-api", "relevance_drop", "memory")

    assert north_run["decision"]["assignee_id"] == "jordan"
    assert bright_run["decision"]["assignee_id"] == "noah"
    assert bright_run["decision"]["procedure_id"] == "rollback-ranking"
    assert bright_run["owner_would_have"]["assignee_id"] == "maya"
    assert bright_run["owner_would_have"]["procedure_id"] == "clear-cache"
    leaked = fetch(bright, "MATCH (p:Person {id: 'jordan'}) RETURN p.name", None, ["name"])
    assert leaked == []
    other = fetch(
        bright,
        "MATCH (h:Handoff {id: $id}) RETURN h.id",
        {"id": north_run["handoff_id"]},
        ["id"],
    )
    assert other == []


def test_company_brain_traces_work_and_decisions(graphs):
    north, _bright = graphs
    worked = ask(north, "who_worked", "postgres-primary")
    names = {row["person"] for row in worked["rows"]}
    assert "Jordan Lee" in names
    assert "Riley Chen" in names
    assert "Taylor Brooks" not in names

    decisions = ask(north, "decision", "checkout-api")
    assert {row["decided_by"] for row in decisions["rows"]} == {"Priya Shah"}
    assert "postmortem" in {row["kind"] for row in decisions["rows"]}

    blast = ask(north, "blast", "postgres-primary")
    blast_ids = {row["id"] for row in blast["rows"]}
    assert "checkout-api" in blast_ids
    assert "ledger" in blast_ids
    assert "experiments-lab" not in blast_ids


def test_concurrent_reads_and_writes_share_one_graph(graphs):
    host = os.environ.get("FALKORDB_HOST", "").strip()
    if not host:
        pytest.skip("embedded FalkorDB is single-process; concurrency is the server path")
    north, _bright = graphs
    run_incident(north, "checkout-api", "latency_spike", "memory")
    port = int(os.environ.get("FALKORDB_PORT", "6379"))

    def client():
        from falkordb import FalkorDB

        return FalkorDB(host=host, port=port).select_graph("relay_northwind")

    def read_handoff(_index):
        rows = client().query(
            "MATCH (h:Handoff {status:'open'})-[:ASSIGNS]->(p:Person) RETURN p.id"
        ).result_set
        assert rows and rows[0][0] == "jordan"

    def write_note(index):
        client().query(
            """
            CREATE (:Memory {
                id: $id, kind: 'episodic', text: $text,
                session_id: 'concurrent', created_at: $created_at
            })
            """,
            {"id": f"mem-c-{index}", "text": f"note {index}", "created_at": index},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(read_handoff, range(8)))
        list(pool.map(write_note, range(8)))

    stored = fetch(
        north,
        "MATCH (m:Memory {session_id:'concurrent'}) RETURN count(m)",
        None,
        ["count"],
    )
    assert stored[0]["count"] == 8
