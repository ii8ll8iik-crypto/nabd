// 03. Multi-hop connected context: Parcel -> Junction -> 1..2-hop Street Services + Nearby EnvZones
MATCH (p:Parcel)-[:FRONTS_ON]->(j:Junction)
WITH p, j ORDER BY p.gfa_m2 DESC LIMIT 5
OPTIONAL MATCH (j)-[:STREET*1..2]-(nj:Junction)<-[:LOCATED_ON]-(s:Service)
WITH p, j, count(DISTINCT s) AS nearby_services
OPTIONAL MATCH (j)-[:NEAR_ZONE]->(z:EnvZone)
RETURN p.id AS parcel_id,
       p.land_use AS land_use,
       j.elev_m AS elev_m,
       nearby_services,
       collect(DISTINCT z.name)[0..4] AS nearby_env_zones
