// 02. Query real leasable/buildable 3D parcels fronting streets (never street intersections)
MATCH (p:Parcel)-[:FRONTS_ON]->(j:Junction)
WHERE coalesce(p.env_restricted, false) = false
  AND coalesce(p.ownership_status, '') <> 'BLOCKED_OWNERSHIP'
  AND p.site_suitability IN ['storefront_lease', 'mixed_ground_floor', 'vacant_buildable']
RETURN p.id AS parcel_id,
       p.land_use AS land_use,
       p.site_suitability AS suitability,
       p.levels AS floors,
       round(p.gfa_m2) AS gfa_m2,
       p.day_pop AS day_pop,
       j.elev_m AS elev_m
ORDER BY p.gfa_m2 DESC
LIMIT 10
