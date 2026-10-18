# Submission draft

Paste these into the Graph Hacks form. The video and the public repo URL are still yours to add.

## Project title

Relay

## Description

On-call agents page the service owner and rerun the first runbook. Relay is a three-agent crew that does not. Archivist, Cartographer, and Liaison share a FalkorDB graph: prior incidents, failed procedures, the real cause, and the person who has fixed it. The next session reads the handoff from the graph and either continues it or refuses a procedure that just failed. A second company lives in its own graph so memory does not leak. Built for incident leads who are tired of paging the on-call owner when the postmortem already named someone else.

## Tracks

Select all three. Lead with Agent Memory and Coordination.

- Agent Memory and Coordination
- Agents That Act on Connected Data
- Company Brain

## How did you use FalkorDB?

FalkorDB is the context the agents read and write on every step, not a store beside the prompt.

- One graph per company (`relay_northwind`, `relay_brightpath`) so handoffs and people stay isolated.
- Episodic, semantic, and procedural memory are nodes. An open `Handoff` is the shared state the next session must match before it acts.
- Agents coordinate by `WROTE` and `READ` edges. Cartographer loads `(:Recall {session_id})`. Liaison loads the `Action`. Tests change those nodes and the next agent follows the graph.
- Multi-hop Cypher connects a symptom to a prior episode, to the cause, to a successful attempt under a different symptom, to an available person.
- `algo.pageRank`, `algo.betweenness`, `algo.WCC`, and `shortestPath` run as part of the action, to rank dependencies, find the failover path, and show services that sit outside the blast.
- Decisions point at the person who made them and the postmortem they came from, which is a different path from who should be paged.

## What did you like about FalkorDB?

Cypher and the graph algorithms are one query surface, so an agent can traverse and rank in the same loop. Multi-graph made a second tenant a `select_graph` call instead of a second deployment. The embedded build and the Docker image are the same client, which kept the app small.

## What improvements would you like to see?

An Intel macOS build of FalkorDBLite. The current wheel's server binary is arm64, so Intel Macs have to run Docker. Clearer errors when an `algo.*` procedure is missing, instead of a generic query failure. A short page in the docs that shows a multi-agent handoff pattern, because the client docs are ahead of the "agents share a graph" pattern.

## Blog

Draft: `BLOG.md`. Publish it, then paste the URL. The draft is the post, not a placeholder outline.

## Still required before you file

- Push is the public repo: https://github.com/Anusha0501/relay
- A public or unlisted YouTube demo. Script is in the README under Demo.
- Live URL, or leave the deployment blank and point judges at the Docker instructions in the README.
