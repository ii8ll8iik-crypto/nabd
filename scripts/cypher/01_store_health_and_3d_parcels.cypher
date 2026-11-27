// 01. Verify city metadata and 3D volumetric parcel breakdown (day vs. night pulse)
MATCH (m:Meta)
WITH m
MATCH (p:Parcel)
RETURN m.slug AS city,
       m.schema_version AS schema_version,
       count(p) AS total_parcels,
       round(sum(p.gfa_m2)) AS total_gfa_m2,
       sum(p.day_pop) AS total_day_pop,
       sum(p.night_pop) AS total_night_pop
