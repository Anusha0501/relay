# The on-call owner was the wrong page

Relay is a small on-call crew built during Graph Hacks. Three agents share a FalkorDB graph. The thing worth writing down is not the UI. It is that the second session makes a different decision only because the first session wrote nodes.

## The trap

Checkout is slow. Priya owns Checkout API and she is on call. The runbook with the lowest rank says restart the payments gateway. A policy that looks at one node and one edge will page Priya every time, and it will be wrong for a reason that is sitting in the graph.

Fourteen days ago the same symptom lasted 42 minutes. Restarting payments failed. Scaling checkout did nothing. The postmortem said the Postgres primary was saturated. Forty-five days before that, a different symptom on a different service recovered in eight minutes when Jordan failed the primary over to its replica.

Priya wrote that decision. She is not the person who has done the fix. Riley knows the primary too. Taylor is on the payments team and available, and has never touched it. The answer is a path, not a record.

## What each agent is allowed to know

Archivist is the only agent that reads episodes. It writes a `Recall` node: suspected cause, blocked procedures, and any open handoff. It also writes three kinds of memory as nodes.

- Episodic: what INC-1042 was.
- Semantic: checkout latency has previously been caused by the primary.
- Procedural: do not repeat the restart.

Cartographer does not receive that as a Python object. It matches `(:Recall {session_id})`. If the node is missing, it stops. From the cause id on that node it queries successful attempts, including attempts that happened under a different symptom, and it runs PageRank, betweenness, weakly connected components, and a shortest path from the alert to the replica. Then it writes an `Action`.

Liaison does not re-decide. It matches the `Action` and writes a `Handoff` that points at the assignee, the procedure, and the service. It attaches the postmortem Priya authored, so the company-brain answer and the paging answer are allowed to name different people.

The tests tamper with those nodes. Add the successful procedure to the blocked list on the Recall, and Cartographer picks the next procedure. Change the assignee on the Action, and Liaison hands off to that person. The edges `WROTE` and `READ` are the transcript.

## The next shift

Leave the handoff open and raise the same alert. Archivist finds it. Cartographer continues it instead of starting from the owner. Mark the failover failed and the handoff closes as blocked. The next Recall includes that attempt, the success from INC-998 is no longer enough, and the crew promotes the read replica instead. Jordan still gets it, because he knows the primary. Priya still does not.

A second company, Brightpath, lives in another graph on the same FalkorDB instance. Same crew, same code. Maya is on call. The crew pages Noah to roll back a ranking model. Jordan does not exist in that graph, and Northwind's handoff id does not resolve there.

## What I would not claim

The algorithms are tools. The decision still holds if a build cannot run `algo.pageRank`, because the cause hop and the blocked attempts are ordinary Cypher. PageRank is there to show which dependency is structurally important, not to cast the vote by itself.

The seed is fictional. The point of the seed is that the naive path and the memory path are both computable, and they disagree. A chatbot wrapped around the same nodes would still page Priya if the prompt forgot the failed attempt. The graph did not forget, because the next process had to read it.

## FalkorDB, specifically

Traversals are the agent loop, so the database had to answer `DEPENDS_ON*1..4` and `shortestPath` on every decision, not as a nightly job. Multi-graph kept the two companies apart without a second deployment. The procedures `algo.pageRank`, `algo.betweenness`, and `algo.WCC` were callable as Cypher, which meant the action agent could use them without a separate analytics service.

The rough edge was local setup. FalkorDBLite is the right embedded story, and on Apple Silicon it is the whole demo. The published macOS wheel's `redis-server` is arm64, so an Intel Mac has to use Docker. That is a documentation problem more than a model problem. I would like the Intel wheel, and I would like algorithm errors to name the missing procedure instead of failing the whole query string.

The part I will keep is the handoff. Memory that does not change the next action is a log. Memory that the next agent is required to read is the product.
