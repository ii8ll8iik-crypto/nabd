"""Nabd v2 Relate Graph Builder: 3D volumetric parcels, embedded DEM/EnvZones, indexes & provenance."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

from backend.engine.terrain_env import (
    RESTRICTED_ZONES,
    _point_in_ring,
    haversine_m,
    load_or_fetch_elevations,
    load_or_fetch_env_zones,
)
from .client import RelateClient
from .schema import apply_schema


def classify_parcel(
    area_m2: float,
    levels: int,
    kind: str,
    orig_est_pop: int,
    env_restricted: bool,
) -> Dict[str, Any]:
    """Derive 3D GFA, day/night population split, land use, and parcel buildability."""
    k = (kind or "yes").lower().strip()
    lv = max(1, int(levels or 1))
    gfa_m2 = round(float(area_m2) * lv, 1)

    if any(t in k for t in ("office", "tower", "skyscraper", "industrial", "warehouse")):
        land_use = "office"
        day_pop = max(12, int(round(gfa_m2 / 22.0)))
        night_pop = max(2, int(round(day_pop * 0.08)))
        suitability = "storefront_lease"
        ownership = "commercial_lease_candidate"
    elif any(t in k for t in ("commercial", "retail", "shop", "mall", "hotel")):
        land_use = "commercial"
        day_pop = max(10, int(round(gfa_m2 / 28.0)))
        night_pop = max(3, int(round(day_pop * 0.15)))
        suitability = "storefront_lease"
        ownership = "commercial_lease_candidate"
    elif any(t in k for t in ("university", "college", "school", "hospital", "civic", "public", "mosque", "church")):
        land_use = "civic"
        day_pop = max(25, int(round(gfa_m2 / 18.0)))
        night_pop = max(4, int(round(day_pop * 0.10)))
        suitability = "institutional"
        ownership = "public_institutional"
    elif any(t in k for t in ("apartments", "dormitory", "mixed")):
        land_use = "mixed_use" if lv >= 4 else "residential"
        night_pop = max(int(orig_est_pop), int(round(gfa_m2 / 34.0)))
        day_pop = max(6, int(round(night_pop * (0.45 if lv >= 4 else 0.25))))
        suitability = "mixed_ground_floor" if lv >= 4 else "residential_only"
        ownership = "mixed_lease_candidate" if lv >= 4 else "private_residential"
    elif any(t in k for t in ("construction", "vacant", "brownfield", "greenfield", "lot")):
        land_use = "vacant"
        day_pop = 1
        night_pop = 1
        suitability = "vacant_buildable"
        ownership = "vacant_parcel_candidate"
    elif any(t in k for t in ("residential", "house", "detached", "terrace", "semidetached")):
        land_use = "residential"
        night_pop = max(int(orig_est_pop), int(round(gfa_m2 / 38.0)))
        day_pop = max(2, int(round(night_pop * 0.22)))
        suitability = "residential_only"
        ownership = "private_residential"
    else:
        # Generic OSM building=yes: tall/large footprints behave as mixed-use urban blocks
        if lv >= 4 or area_m2 >= 450:
            land_use = "mixed_use"
            night_pop = max(int(orig_est_pop), int(round(gfa_m2 / 36.0)))
            day_pop = max(10, int(round(gfa_m2 / 42.0)))
            suitability = "mixed_ground_floor"
            ownership = "mixed_lease_candidate"
        else:
            land_use = "residential"
            night_pop = max(1, int(orig_est_pop))
            day_pop = max(2, int(round(night_pop * 0.25)))
            suitability = "residential_only"
            ownership = "private_residential"

    if env_restricted:
        suitability = "restricted_env"
        ownership = "protected_zone"

    # Active effective demand population preserves baseline gravity stability while scaling tall towers
    est_pop = max(int(orig_est_pop), int(round(0.60 * night_pop + 0.55 * day_pop)), 1)
    return {
        "gfa_m2": gfa_m2,
        "land_use": land_use,
        "day_pop": day_pop,
        "night_pop": night_pop,
        "est_pop": est_pop,
        "site_suitability": suitability,
        "ownership_status": ownership,
        "env_restricted": bool(env_restricted),
    }


def _dedupe_by_key(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        v = it.get(key)
        if v is None or v in seen:
            continue
        seen.add(v)
        out.append(it)
    return out


def enrich_payload_v2(payload: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """Embed DEM elevations, environmental zones, and 3D parcel attributes into a single Relate payload."""
    meta = dict(payload["meta"])
    junctions = _dedupe_by_key(payload.get("junctions", []), "id")
    services = _dedupe_by_key(payload.get("services", []), "id")
    service_types = _dedupe_by_key(payload.get("service_types", []), "key")
    raw_blocks = _dedupe_by_key(payload.get("blocks", []), "id")

    # 1. Embed real DEM elevations directly onto Junction nodes
    elev_map = load_or_fetch_elevations(slug, junctions)
    elev_vals = list(elev_map.values())
    med_elev = sorted(elev_vals)[len(elev_vals) // 2] if elev_vals else 0.0
    for j in junctions:
        j["elev_m"] = round(float(elev_map.get(j["id"], med_elev)), 2)

    # 2. Embed real Environmental Zones directly as (:EnvZone) + [:NEAR_ZONE] edges
    raw_zones = load_or_fetch_env_zones(
        slug,
        float(meta["center_lat"]),
        float(meta["center_lon"]),
        float(meta["radius_m"]),
    )
    env_zones: List[Dict[str, Any]] = []
    zone_rings: List[Tuple[str, bool, float, float, List[List[float]]]] = []
    seen_zids = set()
    for idx, z in enumerate(raw_zones):
        zid = str(z.get("id") or f"{slug}:env:{idx}")
        if zid in seen_zids:
            zid = f"{zid}_{idx}"
        seen_zids.add(zid)
        ztype = str(z.get("zone_type") or z.get("type") or "park")
        restricted = bool(z.get("is_restricted", ztype in RESTRICTED_ZONES))
        geom_type = str(z.get("geom_type") or "Point")
        coords = z.get("coordinates")
        if coords is None:
            coords = [float(z.get("lon", meta["center_lon"])), float(z.get("lat", meta["center_lat"]))]
        ring: List[List[float]] = []
        if geom_type == "Polygon" and isinstance(coords, list) and coords and isinstance(coords[0], list):
            ring = coords[0]
        elif isinstance(z.get("ring"), list):
            ring = z["ring"]
        zlat = float(z.get("lat", meta["center_lat"]))
        zlon = float(z.get("lon", meta["center_lon"]))
        env_zones.append(
            {
                "id": zid,
                "name": str(z.get("name") or ztype.title()),
                "zone_type": ztype,
                "label_ar": str(z.get("label_ar") or ztype),
                "geom_type": geom_type,
                "lat": zlat,
                "lon": zlon,
                "is_restricted": restricted,
                "coordinates_json": json.dumps(coords, separators=(",", ":")),
            }
        )
        zone_rings.append((zid, restricted, zlat, zlon, ring))

    # Connect junctions within 300m to nearest up to 3 env zones
    near_zones: List[Dict[str, Any]] = []
    for j in junctions:
        jlat, jlon = float(j["lat"]), float(j["lon"])
        hits: List[Tuple[float, str]] = []
        for zid, _, zlat, zlon, _ in zone_rings:
            d = haversine_m(jlat, jlon, zlat, zlon)
            if d <= 300.0:
                hits.append((d, zid))
        hits.sort(key=lambda t: t[0])
        for d, zid in hits[:3]:
            near_zones.append({"junction_id": j["id"], "zone_id": zid, "dist_m": round(d, 1)})

    # 3. Upgrade blocks into 3D volumetric Parcels with land_use, day/night split & suitability
    parcels: List[Dict[str, Any]] = []
    for b in raw_blocks:
        blat, blon = float(b["lat"]), float(b["lon"])
        restricted_hit = False
        for _, is_res, zlat, zlon, ring in zone_rings:
            if not is_res:
                continue
            if ring and len(ring) >= 3 and _point_in_ring(blon, blat, ring):
                restricted_hit = True
                break
        props = classify_parcel(
            area_m2=float(b.get("area_m2", 120.0)),
            levels=int(b.get("levels", 2)),
            kind=str(b.get("kind", "yes")),
            orig_est_pop=int(b.get("est_pop", 10)),
            env_restricted=restricted_hit,
        )
        parcel = dict(b)
        parcel.update(props)
        parcels.append(parcel)

    meta["schema_version"] = "2.0"
    meta["total_est_pop"] = sum(p["est_pop"] for p in parcels)
    meta["total_day_pop"] = sum(p["day_pop"] for p in parcels)
    meta["total_night_pop"] = sum(p["night_pop"] for p in parcels)
    meta["total_gfa_m2"] = round(sum(p["gfa_m2"] for p in parcels), 1)
    meta["min_elev_m"] = round(min(elev_vals), 1) if elev_vals else 0.0
    meta["max_elev_m"] = round(max(elev_vals), 1) if elev_vals else 0.0
    meta["env_zone_count"] = len(env_zones)
    meta["synced_at"] = datetime.now(timezone.utc).isoformat()

    return {
        "meta": meta,
        "service_types": service_types,
        "synergies": payload.get("synergies", []),
        "junctions": junctions,
        "streets": payload.get("streets", []),
        "parcels": parcels,
        "services": services,
        "env_zones": env_zones,
        "near_zones": near_zones,
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def materialize_relate_v2(payload: Dict[str, Any], db_path: Path) -> Dict[str, Any]:
    """Build single-file .rl store with v2 schema, constraints, indexes, SHA-256 & build receipt."""
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    cypher = """
    CREATE (:Meta {
      slug: $data.meta.slug,
      label: $data.meta.label,
      schema_version: $data.meta.schema_version,
      center_lat: $data.meta.center_lat,
      center_lon: $data.meta.center_lon,
      radius_m: $data.meta.radius_m,
      synced_at: $data.meta.synced_at,
      total_est_pop: $data.meta.total_est_pop,
      total_day_pop: $data.meta.total_day_pop,
      total_night_pop: $data.meta.total_night_pop,
      total_gfa_m2: $data.meta.total_gfa_m2,
      min_elev_m: $data.meta.min_elev_m,
      max_elev_m: $data.meta.max_elev_m,
      env_zone_count: $data.meta.env_zone_count
    });

    UNWIND $data.service_types AS st
    CREATE (:ServiceType {
      key: st.key,
      label_en: st.label_en,
      label_ar: st.label_ar,
      beta_decay: st.beta_decay,
      alpha_attraction: st.alpha_attraction,
      base_attraction: st.base_attraction,
      outside_option: st.outside_option,
      ideal_walk_min: st.ideal_walk_min,
      daily_capacity: st.daily_capacity,
      demand_per_1k_pop: st.demand_per_1k_pop
    });

    UNWIND $data.synergies AS syn
    MATCH (a:ServiceType {key: syn.src}), (b:ServiceType {key: syn.dst})
    CREATE (a)-[:SYNERGIZES_WITH {multiplier: syn.multiplier, decay_gamma: syn.decay_gamma}]->(b);

    UNWIND $data.junctions AS j
    CREATE (:Junction {id: j.id, lat: j.lat, lon: j.lon, elev_m: j.elev_m});

    UNWIND $data.streets AS s
    MATCH (a:Junction {id: s.src}), (b:Junction {id: s.dst})
    CREATE (a)-[:STREET {
      length_m: s.length_m,
      walk_min: s.walk_min,
      drive_min: s.drive_min,
      highway: s.highway,
      capacity: s.capacity,
      oneway: s.oneway
    }]->(b);

    UNWIND $data.parcels AS p
    MATCH (j:Junction {id: p.junction_id})
    CREATE (blk:Parcel {
      id: p.id,
      lat: p.lat,
      lon: p.lon,
      area_m2: p.area_m2,
      levels: p.levels,
      gfa_m2: p.gfa_m2,
      est_pop: p.est_pop,
      day_pop: p.day_pop,
      night_pop: p.night_pop,
      kind: p.kind,
      land_use: p.land_use,
      site_suitability: p.site_suitability,
      ownership_status: p.ownership_status,
      env_restricted: p.env_restricted
    })-[:FRONTS_ON {euclid_m: p.snap_m, walk_min: p.snap_walk_min}]->(j);

    UNWIND $data.services AS sv
    MATCH (j:Junction {id: sv.junction_id}), (st:ServiceType {key: sv.category})
    CREATE (s:Service {
      id: sv.id,
      name: sv.name,
      category: sv.category,
      lat: sv.lat,
      lon: sv.lon,
      attraction: sv.attraction,
      capacity: sv.capacity
    })-[:LOCATED_ON {euclid_m: sv.snap_m, walk_min: sv.snap_walk_min}]->(j),
    (s)-[:OF_TYPE]->(st);

    UNWIND $data.env_zones AS z
    CREATE (:EnvZone {
      id: z.id,
      name: z.name,
      zone_type: z.zone_type,
      label_ar: z.label_ar,
      geom_type: z.geom_type,
      lat: z.lat,
      lon: z.lon,
      is_restricted: z.is_restricted,
      coordinates_json: z.coordinates_json
    });

    UNWIND $data.near_zones AS nz
    MATCH (j:Junction {id: nz.junction_id}), (z:EnvZone {id: nz.zone_id})
    CREATE (j)-[:NEAR_ZONE {dist_m: nz.dist_m}]->(z);
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_payload = Path(tmpdir) / "payload.json"
        tmp_payload.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        cmd = [
            "relate",
            "-d",
            str(db_path),
            "--expression-memory-limit",
            "none",
            "--fetch-params",
            f"data={tmp_payload}",
            "query",
        ]
        res = subprocess.run(cmd, input=cypher, text=True, capture_output=True)
        if res.returncode != 0:
            raise RuntimeError(f"Relate v2 build failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")

    # Apply canonical v2 unique constraints & secondary indexes
    with RelateClient(db_path) as client:
        schema_report = apply_schema(client)
        store_info = client.store_info()

    sha256 = _sha256_file(db_path)
    sha_path = db_path.parent / f"{db_path.name}.sha256"
    sha_path.write_text(f"{sha256}  {db_path.name}\n", encoding="utf-8")

    suitability_counts: Dict[str, int] = {}
    for p in payload["parcels"]:
        s = p["site_suitability"]
        suitability_counts[s] = suitability_counts.get(s, 0) + 1

    receipt = {
        "schema_version": "2.0",
        "slug": payload["meta"]["slug"],
        "label": payload["meta"]["label"],
        "built_at": datetime.now(timezone.utc).isoformat(),
        "store_file": db_path.name,
        "sha256": sha256,
        "total_bytes": db_path.stat().st_size,
        "sources": {
            "topology_and_buildings": "OpenStreetMap via Overpass API",
            "elevation_dem": "Open-Meteo Copernicus DEM",
            "environmental_zones": "OpenStreetMap Parks/Water/Tourism/Campus",
        },
        "counts": {
            "junctions": len(payload["junctions"]),
            "streets": len(payload["streets"]),
            "parcels": len(payload["parcels"]),
            "services": len(payload["services"]),
            "env_zones": len(payload["env_zones"]),
            "near_zone_edges": len(payload["near_zones"]),
        },
        "volumetric": {
            "total_gfa_m2": payload["meta"]["total_gfa_m2"],
            "total_day_pop": payload["meta"]["total_day_pop"],
            "total_night_pop": payload["meta"]["total_night_pop"],
            "total_est_pop": payload["meta"]["total_est_pop"],
            "min_elev_m": payload["meta"]["min_elev_m"],
            "max_elev_m": payload["meta"]["max_elev_m"],
            "parcel_suitability": suitability_counts,
        },
        "relate_store_info": {
            "node_count": store_info.get("node_count"),
            "rel_count": store_info.get("rel_count"),
            "constraints": store_info.get("constraints"),
            "indexes": store_info.get("indexes"),
            "codec": store_info.get("codec"),
            "format_version": store_info.get("format_version"),
        },
        "schema_report": schema_report,
    }
    receipt_path = db_path.parent / f"{payload['meta']['slug']}.build-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
