# Relay

On-call agents page the person who owns the alerting service and rerun the first runbook. That is often the wrong action. The right page depends on a prior incident, the procedure that failed, the service that actually caused it, and the person who has fixed that cause before.

Relay is a three-agent crew whose shared context is a FalkorDB graph. Archivist writes memory. Cartographer reads that memory and chooses an action. Liaison reads the action and writes the handoff the next session will find. None of them pass the decision around in process memory.

The lead track is **Agent Memory and Coordination**. The same run also enters **Agents That Act on Connected Data** and **Company Brain**.

## The decision you can demo

Northwind Cloud. Checkout latency. Priya Shah is on call and owns Checkout API. The obvious action is to restart the payments gateway.

The graph says otherwise:

1. INC-1042 had the same symptom, and restarting payments failed.
2. The postmortem cause was the Postgres primary, not the gateway.
3. INC-998 recovered that primary by failing over to the replica. Jordan Lee did it.
4. Riley Chen also knows the primary, but has not done the failover.

The crew assigns Jordan to fail over. The next shift reads that handoff from FalkorDB and continues it. If the failover is recorded as a failure, the next crew refuses to repeat it and picks the next unblocked procedure.

Brightpath is a second company in its own graph. Maya is on call there. The crew pages Noah instead, and it cannot see Northwind's people or handoffs.

## Agents

| Agent | Writes | Reads | Track |
| --- | --- | --- | --- |
| Archivist | Recall, episodic, semantic, and procedural Memory | Episodes, attempts, open handoffs | Memory and coordination |
| Cartographer | Action | The Recall node, then procedures, blast radius, PageRank, betweenness, components, shortest path | Act on connected data |
| Liaison | Handoff | The Action node, owners, and the source document | Company brain |

Cartographer will not run if the Recall node is missing. Liaison assigns whoever the Action node names, even if that name was written by a different process. That is the coordination test.

## Graph model

Two FalkorDB graphs, `relay_northwind` and `relay_brightpath`. One instance, isolated tenants.

Nodes: `Person`, `Team`, `Service`, `Project`, `Procedure`, `Episode`, `Attempt`, `Document`, `Decision`, `Agent`, `Memory`, `Recall`, `Action`, `Handoff`.

Relationships the decisions use:

- `(Person)-[:OWNS|KNOWS|WORKED_ON]->`
- `(Person)-[:WORKED_ON]->(Project)-[:USES]->(Service)`
- `(Service)-[:DEPENDS_ON {dist}]->(Service)`
- `(Service)-[:ROUTES_TO {dist}]->(Service)`
- `(Episode)-[:AFFECTED]->(Service)` and `(Episode)-[:CAUSED_BY]->(Service)`
- `(Episode)-[:ATTEMPTED]->(Attempt)-[:USED]->(Procedure)`
- `(Attempt)-[:BY]->(Person)` and `(Attempt)-[:ON]->(Service)`
- `(Decision)-[:ABOUT]->(Episode)`, `[:DECIDED_BY]->(Person)`, `[:SOURCED_FROM]->(Document)`
- `(Handoff)-[:ABOUT]->(Service)`, `[:ASSIGNS]->(Person)`, `[:RECOMMENDS]->(Procedure)`
- `(Agent)-[:WROTE|READ {session_id}]->` the shared nodes

Annotated queries: [cypher/queries.cypher](cypher/queries.cypher). The strings the app executes: [app/cypher_book.py](app/cypher_book.py).

Algorithms, called as tools and ignored if a build does not ship them:

- `algo.pageRank` on `Service` / `DEPENDS_ON`
- `algo.betweenness` on the same topology
- `algo.WCC` to show isolated services are outside the blast
- `shortestPath` over `DEPENDS_ON` and `ROUTES_TO`

## Run it

FalkorDB is the database. Docker is the runtime that works everywhere, including Intel Macs. The FalkorDBLite wheel currently ships an arm64 `redis-server`, so an Intel Mac cannot use the embedded fallback.

```bash
docker compose up -d
uv sync --all-groups --python 3.12
FALKORDB_HOST=localhost uv run uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Open http://127.0.0.1:8080. FalkorDB Browser is on http://localhost:3000.

On Apple Silicon, without Docker:

```bash
uv sync --all-groups --python 3.12
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080
```

That path starts FalkorDBLite and stores the graphs in `data/relay.db`.

### Demo

1. Stay on Northwind. Read the incident: the roster would page Priya.
2. **Run the crew.** The decision is Jordan Lee, fail over to the replica. The contrast card is the owner policy.
3. **Next shift.** The same alert continues the open handoff. The kicker says the shift read it from the graph.
4. **It failed**, then **Next shift**. Failover is blocked. The crew picks "Promote read replica" and still does not page Priya.
5. Switch the company to Brightpath and run the crew. Noah, not Maya. No Northwind names.
6. Ask "Who has worked on this system?" and "Where did this decision come from?"

Reset graph restores the seed.

### Tests

```bash
docker compose up -d
FALKORDB_HOST=localhost uv run pytest -q
```

GitHub Actions runs the same tests against `falkordb/falkordb:latest`.

## API

- `GET /api/health`
- `GET /api/tenants/{tenant}`
- `POST /api/tenants/{tenant}/incidents` with `{service, symptom, policy}` where policy is `memory` or `owner`
- `POST /api/tenants/{tenant}/sessions/{session_id}/outcome` with `{result: success|failed, note}`
- `POST /api/tenants/{tenant}/ask` with `{question, service}`
- `GET /api/tenants/{tenant}/graph`
- `GET /api/tenants/{tenant}/memory`
- `POST /api/tenants/{tenant}/reset`
- `GET /api/cypher`

Tenant ids are limited to the seeded companies. Queries are parameterized.
