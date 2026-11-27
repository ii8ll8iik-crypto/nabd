// 04. Inspect persistent AI agent decisions & blocked ownership records stored in .rl
MATCH (d:AgentDecision)-[:EVALUATES]->(p:Parcel)
RETURN d.id AS decision_id,
       d.status AS status,
       d.category AS category,
       d.actor AS actor,
       d.reason AS reason,
       p.id AS parcel_id,
       p.ownership_status AS ownership_status
ORDER BY d.created_at DESC
LIMIT 20
