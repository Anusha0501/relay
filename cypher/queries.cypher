// Relay query book
// These are the traversals the crew depends on.
// Executable copies: app/cypher_book.py

// 1. Memory. Same symptom, prior episode, real cause.
//    The live episode is excluded so a new alert cannot erase the postmortem.
MATCH (e:Episode)-[:AFFECTED]->(:Service {id:$service})
WHERE e.symptom = $symptom AND coalesce(e.live, false) = false
MATCH (e)-[:CAUSED_BY]->(cause:Service)
RETURN e.id, e.summary, e.impact_minutes, cause.id, cause.name, e.started_at
ORDER BY e.started_at DESC
LIMIT 1;

// 2. Procedural memory. Failed and no-effect attempts on this symptom are blocked.
MATCH (e:Episode)-[:AFFECTED]->(:Service {id:$service})
WHERE e.symptom = $symptom
MATCH (e)-[:ATTEMPTED]->(a:Attempt)-[:USED]->(proc:Procedure)
WHERE a.result IN ['failed', 'no_effect']
OPTIONAL MATCH (a)-[:BY]->(p:Person)
RETURN proc.id, proc.name, a.result, e.id, p.name, a.impact_minutes;

// 3. Shared state. The next session reads the open handoff instead of starting over.
MATCH (h:Handoff {status:'open'})-[:ABOUT]->(:Service {id:$service})
OPTIONAL MATCH (h)-[:ASSIGNS]->(p:Person)
OPTIONAL MATCH (h)-[:RECOMMENDS]->(proc:Procedure)
RETURN h.id, h.summary, h.session_id, p.id, p.name, p.available, proc.id, proc.name
ORDER BY h.created_at DESC
LIMIT 1;

// 4. Action. Successful attempts on the suspected cause, including a different symptom.
MATCH (a:Attempt {result:'success'})-[:ON]->(:Service {id:$cause})
MATCH (a)-[:USED]->(proc:Procedure)
MATCH (a)-[:BY]->(p:Person)
RETURN proc.id, proc.name, p.id, p.name, p.available, p.role, a.id;

// 5. The naive policy. Page the owner and the lowest-ranked runbook within one hop.
MATCH (owner:Person)-[:OWNS]->(s:Service {id:$service})
WHERE owner.available = true
MATCH (s)-[:DEPENDS_ON*0..1]->(dep:Service)<-[:APPLIES_TO]-(proc:Procedure)
RETURN owner.id, owner.name, owner.role, proc.id, proc.name, proc.naive_rank, dep.id, dep.name
ORDER BY proc.naive_rank ASC, dep.id ASC
LIMIT 1;

// 6. Blast radius. What depends, directly or indirectly, on this service.
MATCH (affected:Service)-[:DEPENDS_ON*1..4]->(:Service {id:$service})
RETURN DISTINCT affected.id, affected.name, affected.tier
ORDER BY affected.name ASC;

// 7. Shortest action path from the alert to the failover target.
MATCH (a:Service {id:$source}), (b:Service {id:$target})
MATCH p = shortestPath((a)-[:DEPENDS_ON|ROUTES_TO*..8]->(b))
RETURN [n IN nodes(p) | n.name];

// 8. Graph algorithms used as agent tools.
CALL algo.pageRank('Service', 'DEPENDS_ON')
YIELD node, score
RETURN node.name, score
ORDER BY score DESC
LIMIT 8;

CALL algo.betweenness({
  nodeLabels: ['Service'],
  relationshipTypes: ['DEPENDS_ON'],
  samplingSeed: 7
})
YIELD node, score
RETURN node.name, score
ORDER BY score DESC
LIMIT 8;

CALL algo.WCC({nodeLabels: ['Service'], relationshipTypes: ['DEPENDS_ON', 'ROUTES_TO']})
YIELD node, componentId
RETURN node.name, componentId;

// 9. Company brain. Who has actually worked on the system.
MATCH (p:Person)-[:WORKED_ON]->(project:Project)-[:USES]->(:Service {id:$service})
RETURN DISTINCT p.name, p.role, project.name
ORDER BY p.name ASC;

// 10. Trace a decision back to the person and the document.
MATCH (d:Decision)-[:ABOUT]->(:Episode {id:$episode})
MATCH (d)-[:SOURCED_FROM]->(doc:Document)
MATCH (d)-[:DECIDED_BY]->(p:Person)
RETURN d.title, d.rationale, doc.title, doc.kind, p.name;
