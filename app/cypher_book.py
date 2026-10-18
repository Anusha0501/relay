"""Cypher the crew actually runs. Annotated copies live in cypher/queries.cypher."""

PRIOR_CAUSE = """
MATCH (e:Episode)-[:AFFECTED]->(:Service {id:$service})
WHERE e.symptom = $symptom AND coalesce(e.live, false) = false
MATCH (e)-[:CAUSED_BY]->(cause:Service)
RETURN e.id, e.summary, e.impact_minutes, cause.id, cause.name, e.started_at
ORDER BY e.started_at DESC
LIMIT 1
"""

FAILED_ATTEMPTS = """
MATCH (e:Episode)-[:AFFECTED]->(:Service {id:$service})
WHERE e.symptom = $symptom
MATCH (e)-[:ATTEMPTED]->(a:Attempt)-[:USED]->(proc:Procedure)
WHERE a.result IN ['failed', 'no_effect']
OPTIONAL MATCH (a)-[:BY]->(p:Person)
RETURN proc.id, proc.name, a.result, e.id, p.name, a.impact_minutes
"""

OPEN_HANDOFF = """
MATCH (h:Handoff {status:'open'})-[:ABOUT]->(:Service {id:$service})
OPTIONAL MATCH (h)-[:ASSIGNS]->(p:Person)
OPTIONAL MATCH (h)-[:RECOMMENDS]->(proc:Procedure)
RETURN h.id, h.summary, h.session_id, p.id, p.name, p.available, proc.id, proc.name
ORDER BY h.created_at DESC
LIMIT 1
"""

SUCCESSFUL_ATTEMPTS = """
MATCH (a:Attempt {result:'success'})-[:ON]->(:Service {id:$cause})
MATCH (a)-[:USED]->(proc:Procedure)
MATCH (a)-[:BY]->(p:Person)
RETURN proc.id, proc.name, p.id, p.name, p.available, p.role, a.id
"""

PROCEDURES_FOR = """
MATCH (proc:Procedure)-[:APPLIES_TO]->(:Service {id:$service})
RETURN proc.id, proc.name, proc.summary, proc.naive_rank
ORDER BY proc.naive_rank ASC
"""

KNOWERS = """
MATCH (p:Person)-[:KNOWS]->(:Service {id:$service})
RETURN p.id, p.name, p.role, p.available
ORDER BY p.name ASC
"""

OWNER_POLICY = """
MATCH (owner:Person)-[:OWNS]->(s:Service {id:$service})
WHERE owner.available = true
MATCH (s)-[:DEPENDS_ON*0..1]->(dep:Service)<-[:APPLIES_TO]-(proc:Procedure)
RETURN owner.id, owner.name, owner.role, proc.id, proc.name, proc.naive_rank, dep.id, dep.name
ORDER BY proc.naive_rank ASC, dep.id ASC
LIMIT 1
"""

BLAST = """
MATCH (affected:Service)-[:DEPENDS_ON*1..4]->(:Service {id:$service})
RETURN DISTINCT affected.id, affected.name, affected.tier
ORDER BY affected.name ASC
"""

UPSTREAM = """
MATCH (:Service {id:$service})-[:DEPENDS_ON*1..3]->(dep:Service)
RETURN DISTINCT dep.id, dep.name
ORDER BY dep.name ASC
"""

REPLICA = """
MATCH (:Service {id:$cause})-[:ROUTES_TO]->(replica:Service)
RETURN replica.id, replica.name
LIMIT 1
"""

SHORTEST_ACTION_PATH = """
MATCH (a:Service {id:$source}), (b:Service {id:$target})
MATCH p = shortestPath((a)-[:DEPENDS_ON|ROUTES_TO*..8]->(b))
RETURN [n IN nodes(p) | n.name]
"""

DECISION_SOURCE = """
MATCH (d:Decision)-[:ABOUT]->(:Episode {id:$episode})
MATCH (d)-[:SOURCED_FROM]->(doc:Document)
MATCH (d)-[:DECIDED_BY]->(p:Person)
RETURN d.title, d.rationale, doc.title, doc.kind, p.name
"""

PAGE_RANK = """
CALL algo.pageRank('Service', 'DEPENDS_ON')
YIELD node, score
RETURN node.name, score
ORDER BY score DESC
LIMIT 8
"""

BETWEENNESS = """
CALL algo.betweenness({
  nodeLabels: ['Service'],
  relationshipTypes: ['DEPENDS_ON'],
  samplingSeed: 7
})
YIELD node, score
RETURN node.name, score
ORDER BY score DESC
LIMIT 8
"""

COMPONENTS = """
CALL algo.WCC({nodeLabels: ['Service'], relationshipTypes: ['DEPENDS_ON', 'ROUTES_TO']})
YIELD node, componentId
RETURN node.name, componentId
"""

SERVICE_ROW = """
MATCH (s:Service {id:$service})
RETURN s.id, s.name, s.tier, s.summary
"""

RECALL_ROW = """
MATCH (r:Recall {session_id:$session_id})
RETURN r.id, r.service, r.symptom, r.suspected_cause, r.prior_episode,
       r.blocked_procedures, r.handoff_id, r.handoff_procedure_id, r.handoff_person_id, r.summary
"""

ACTION_ROW = """
MATCH (a:Action {session_id:$session_id, policy:'memory'})
RETURN a.id, a.procedure_id, a.procedure_name, a.assignee_id, a.assignee_name,
       a.cause, a.service, a.summary, a.episode_id
ORDER BY a.created_at DESC
LIMIT 1
"""

PERSON_ROW = """
MATCH (p:Person {id:$id})
RETURN p.id, p.name, p.role, p.available, p.on_call
"""

OWNERS_OF = """
MATCH (p:Person)-[:OWNS]->(:Service {id:$service})
RETURN p.id, p.name, p.on_call, p.available
ORDER BY p.name ASC
"""

WHO_WORKED = """
MATCH (p:Person)-[:WORKED_ON]->(project:Project)-[:USES]->(:Service {id:$service})
RETURN DISTINCT p.name, p.role, project.name
ORDER BY p.name ASC
"""

WHO_KNOWS = """
MATCH (p:Person)-[:KNOWS]->(:Service {id:$service})
RETURN p.name, p.role, p.available
ORDER BY p.name ASC
"""

LAST_TIME = """
MATCH (e:Episode)-[:AFFECTED]->(:Service {id:$service})
WHERE coalesce(e.live, false) = false
OPTIONAL MATCH (e)-[:CAUSED_BY]->(cause:Service)
OPTIONAL MATCH (e)-[:ATTEMPTED]->(a:Attempt)-[:USED]->(proc:Procedure)
OPTIONAL MATCH (a)-[:BY]->(p:Person)
RETURN e.id, e.name, e.symptom, e.summary, e.impact_minutes, cause.name, a.result, proc.name, p.name
ORDER BY e.started_at DESC
"""

OWNERSHIP = """
MATCH (s:Service)
OPTIONAL MATCH (owner:Person)-[:OWNS]->(s)
OPTIONAL MATCH (expert:Person)-[:KNOWS]->(s)
RETURN s.name, collect(DISTINCT owner.name), collect(DISTINCT expert.name)
ORDER BY s.name ASC
"""

DECISIONS_ABOUT = """
MATCH (d:Decision)-[:ABOUT]->(e:Episode)-[:AFFECTED|CAUSED_BY]->(:Service {id:$service})
MATCH (d)-[:SOURCED_FROM]->(doc:Document)
MATCH (d)-[:DECIDED_BY]->(p:Person)
RETURN DISTINCT d.title, d.rationale, doc.title, doc.kind, p.name, e.name
"""

GRAPH_NODES = """
MATCH (n)
WHERE n:Service OR n:Person OR n:Team
RETURN n.id, labels(n)[0], n.name, n.x, n.y, n.tier, n.role, n.available, n.on_call
"""

GRAPH_EDGES = """
MATCH (a)-[r]->(b)
WHERE (a:Service OR a:Person) AND (b:Service OR b:Person OR b:Team)
  AND type(r) IN ['DEPENDS_ON', 'ROUTES_TO', 'OWNS', 'KNOWS', 'MEMBER_OF']
RETURN a.id, b.id, type(r)
"""
