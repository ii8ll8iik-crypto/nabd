"""
Live World Ingestion Pipeline: OpenStreetMap (Overpass) -> Relate (.rl)
Pulls real streets, buildings, and services for ANY bounding box on Earth,
transforms them into a multi-layer urban graph, and materializes a .rl database.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import numpy as np
from scipy.spatial import cKDTree

from backend.engine.catalog import SERVICE_CATALOG, classify_osm_tags

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]

PRESETS: Dict[str, Dict[str, Any]] = {
    "irbid-yarmouk": {
        "label": "Irbid — Yarmouk & University St",
        "lat": 32.5365,
        "lon": 35.8555,
        "radius_m": 850,
    },
    "irbid-center": {
        "label": "Irbid — City Center",
        "lat": 32.5556,
        "lon": 35.8500,
        "radius_m": 850,
    },
    "manhattan-midtown": {
        "label": "Manhattan — Midtown & Bryant Park (NYC)",
        "lat": 40.7536,
        "lon": -73.9832,
        "radius_m": 650,
    },
    "barcelona-eixample": {
        "label": "Barcelona — Eixample",
        "lat": 41.3917,
        "lon": 2.1649,
        "radius_m": 750,
    },
}

# (walk_m_per_s, drive_m_per_s, hourly_capacity)
HIGHWAY_PHYSICS: Dict[str, Tuple[float, float, int]] = {
    "footway": (1.35, 0.0, 250),
    "pedestrian": (1.35, 0.0, 400),
    "living_street": (1.32, 4.5, 450),
    "service": (1.28, 6.0, 500),
    "residential": (1.30, 8.3, 700),
    "unclassified": (1.28, 9.5, 850),
    "tertiary": (1.22, 12.5, 1100),
    "tertiary_link": (1.20, 11.0, 900),
    "secondary": (1.12, 15.0, 1600),
    "secondary_link": (1.10, 13.0, 1200),
    "primary": (0.98, 18.0, 2400),      # Crossing friction creates realistic topological barriers
    "primary_link": (0.98, 15.0, 1800),
}

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def bbox_from_center(lat: float, lon: float, radius_m: float) -> Tuple[float, float, float, float]:
    dlat = radius_m / 111320.0
    dlon = radius_m / (111320.0 * math.cos(math.radians(lat)))
    return (lat - dlat, lon - dlon, lat + dlat, lon + dlon)


def polygon_area_m2(coords: List[Tuple[float, float]]) -> float:
    if len(coords) < 3:
        return 0.0
    lat0 = sum(c[0] for c in coords) / len(coords)
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 111320.0
    pts = [(lon * kx, lat * ky) for lat, lon in coords]
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def fetch_overpass(bbox: Tuple[float, float, float, float], raw_cache: Path, force: bool = False) -> Dict[str, Any]:
    if raw_cache.exists() and not force:
        return json.loads(raw_cache.read_text(encoding="utf-8"))

    s, w, n, e = bbox
    query = f"""
    [out:json][timeout:60];
    (
      way["highway"]({s},{w},{n},{e});
      way["building"]({s},{w},{n},{e});
      node["shop"]({s},{w},{n},{e});
      way["shop"]({s},{w},{n},{e});
      node["amenity"]({s},{w},{n},{e});
      way["amenity"]({s},{w},{n},{e});
    );
    out body;
    >;
    out skel qt;
    """

    headers = {
        "User-Agent": "NabdUrbanPhysics/1.0 (Urban Graph Research)",
        "Accept": "application/json, */*",
    }

    last_err: Exception | None = None
    for url in OVERPASS_MIRRORS:
        try:
            print(f"[ingest] Fetching live OpenStreetMap data from {url} ...")
            with httpx.Client(timeout=90.0, headers=headers, follow_redirects=True) as client:
                resp = client.post(url, data={"data": query})
                resp.raise_for_status()
                payload = resp.json()
                raw_cache.parent.mkdir(parents=True, exist_ok=True)
                raw_cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                return payload
        except Exception as exc:
            last_err = exc
            print(f"[ingest] Mirror failed ({exc}), trying next...")

    raise RuntimeError(f"All Overpass mirrors failed: {last_err}")


def parse_osm_to_payload(
    raw: Dict[str, Any],
    slug: str,
    label: str,
    center_lat: float,
    center_lon: float,
    radius_m: float,
) -> Dict[str, Any]:
    elements = raw.get("elements", [])
    nodes: Dict[int, Tuple[float, float, Dict[str, str]]] = {}
    ways: List[Dict[str, Any]] = []

    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"], el.get("tags", {}))
        elif el["type"] == "way":
            ways.append(el)

    # 1. Extract street topology (compact intersections + sampled vertices every ~45m)
    street_ways = [w for w in ways if w.get("tags", {}).get("highway") in HIGHWAY_PHYSICS]
    node_way_count: Dict[int, int] = {}
    for w in street_ways:
        nds = w.get("nodes", [])
        for idx, nid in enumerate(nds):
            inc = 2 if (idx == 0 or idx == len(nds) - 1) else 1
            node_way_count[nid] = node_way_count.get(nid, 0) + inc

    junctions_map: Dict[str, Dict[str, Any]] = {}
    streets: List[Dict[str, Any]] = []
    residential_jids: List[str] = []

    for w in street_ways:
        nds = [nid for nid in w.get("nodes", []) if nid in nodes]
        if len(nds) < 2:
            continue
        tags = w.get("tags", {})
        hw = tags["highway"]
        walk_mps, drive_mps, cap = HIGHWAY_PHYSICS[hw]
        oneway = tags.get("oneway") in ("yes", "true", "1")

        # Keep endpoints, intersections, and intermediate points every ~45m
        seg_start = nds[0]
        acc_len = 0.0
        for i in range(1, len(nds)):
            prev_nid, cur_nid = nds[i - 1], nds[i]
            p_lat, p_lon, _ = nodes[prev_nid]
            c_lat, c_lon, _ = nodes[cur_nid]
            acc_len += haversine_m(p_lat, p_lon, c_lat, c_lon)

            is_anchor = (i == len(nds) - 1) or (node_way_count.get(cur_nid, 0) > 1) or (acc_len >= 45.0)
            if is_anchor and seg_start != cur_nid and acc_len > 0.5:
                src_id = f"j_{seg_start}"
                dst_id = f"j_{cur_nid}"
                s_lat, s_lon, _ = nodes[seg_start]
                junctions_map.setdefault(src_id, {"id": src_id, "lat": s_lat, "lon": s_lon})
                junctions_map.setdefault(dst_id, {"id": dst_id, "lat": c_lat, "lon": c_lon})

                if hw in ("residential", "living_street", "unclassified"):
                    residential_jids.append(src_id)

                walk_min = round((acc_len / walk_mps) / 60.0, 4)
                drive_min = round((acc_len / drive_mps) / 60.0, 4) if drive_mps > 0 else 999.0

                streets.append({
                    "src": src_id,
                    "dst": dst_id,
                    "length_m": round(acc_len, 2),
                    "walk_min": walk_min,
                    "drive_min": drive_min,
                    "highway": hw,
                    "capacity": cap,
                    "oneway": oneway,
                })
                # Pedestrians can walk both ways on urban streets; cars respect oneway
                streets.append({
                    "src": dst_id,
                    "dst": src_id,
                    "length_m": round(acc_len, 2),
                    "walk_min": walk_min,
                    "drive_min": 999.0 if oneway else drive_min,
                    "highway": hw,
                    "capacity": cap,
                    "oneway": oneway,
                })
                seg_start = cur_nid
                acc_len = 0.0

    if not junctions_map:
        raise RuntimeError("No street junctions found in this area. Try increasing radius_m.")

    junctions = list(junctions_map.values())
    j_coords = np.array([[j["lat"], j["lon"]] for j in junctions])
    kdtree = cKDTree(j_coords)

    def snap_to_junction(lat: float, lon: float) -> Tuple[str, float, float]:
        _, idx = kdtree.query([lat, lon])
        j = junctions[int(idx)]
        dist = haversine_m(lat, lon, j["lat"], j["lon"])
        return j["id"], round(dist, 2), round((dist / 1.25) / 60.0, 4)

    # 2. Extract services (POIs from nodes and building ways)
    services: List[Dict[str, Any]] = []
    seen_srv_coords: set[Tuple[str, int, int]] = set()

    def add_service(oid: str, lat: float, lon: float, tags: Dict[str, str], area_m2: float = 0.0) -> None:
        cat = classify_osm_tags(tags)
        if not cat:
            return
        dedup_key = (cat, int(round(lat * 10000)), int(round(lon * 10000)))
        if dedup_key in seen_srv_coords:
            return
        seen_srv_coords.add(dedup_key)
        spec = SERVICE_CATALOG[cat]
        name = tags.get("name:ar") or tags.get("name") or tags.get("name:en") or spec.label_en
        # Slight attraction scaling for larger real footprints
        size_boost = min(2.2, max(1.0, math.sqrt(max(area_m2, 60.0) / 100.0))) if area_m2 > 0 else 1.0
        jid, snap_m, snap_w = snap_to_junction(lat, lon)
        services.append({
            "id": oid,
            "name": str(name)[:80],
            "category": cat,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "attraction": round(spec.base_attraction * size_boost, 3),
            "capacity": spec.daily_capacity,
            "junction_id": jid,
            "snap_m": snap_m,
            "snap_walk_min": snap_w,
        })

    for nid, (lat, lon, tags) in nodes.items():
        if tags:
            add_service(f"srv_n_{nid}", lat, lon, tags)

    # 3. Extract buildings (both as potential services and residential demand blocks)
    blocks: List[Dict[str, Any]] = []
    for w in ways:
        tags = w.get("tags", {})
        nds = [nodes[nid] for nid in w.get("nodes", []) if nid in nodes]
        if len(nds) < 3:
            continue
        coords = [(p[0], p[1]) for p in nds]
        clat = sum(c[0] for c in coords) / len(coords)
        clon = sum(c[1] for c in coords) / len(coords)
        area = polygon_area_m2(coords)

        if classify_osm_tags(tags):
            add_service(f"srv_w_{w['id']}", clat, clon, tags, area_m2=area)

        if "building" in tags and area >= 25.0:
            btype = tags.get("building", "yes")
            if btype in ("mosque", "church", "garage", "shed", "roof", "warehouse"):
                continue
            try:
                levels = float(tags.get("building:levels", "2" if btype in ("apartments", "yes", "residential") else "1"))
            except ValueError:
                levels = 2.0
            levels = max(1.0, min(12.0, levels))
            est_pop = max(4, min(260, int(round((area * levels) / 38.0))))
            jid, snap_m, snap_w = snap_to_junction(clat, clon)
            blocks.append({
                "id": f"blk_{w['id']}",
                "lat": round(clat, 6),
                "lon": round(clon, 6),
                "area_m2": round(area, 1),
                "levels": levels,
                "est_pop": est_pop,
                "kind": str(btype)[:30],
                "junction_id": jid,
                "snap_m": snap_m,
                "snap_walk_min": snap_w,
            })

    # Fallback: if OSM building polygons are sparse in this neighborhood, synthesize demand blocks on residential junctions
    if len(blocks) < 30:
        pool = list(dict.fromkeys(residential_jids)) or [j["id"] for j in junctions]
        step = max(1, len(pool) // 80)
        for jid in pool[::step]:
            j = junctions_map[jid]
            blocks.append({
                "id": f"syn_{jid}",
                "lat": round(j["lat"], 6),
                "lon": round(j["lon"], 6),
                "area_m2": 320.0,
                "levels": 3.0,
                "est_pop": 35,
                "kind": "inferred_residential",
                "junction_id": jid,
                "snap_m": 0.0,
                "snap_walk_min": 0.0,
            })

    # 4. Serialize Laws Layer (ServiceTypes + Hop-3 Leontief Synergies)
    service_types = []
    synergies = []
    for spec in SERVICE_CATALOG.values():
        service_types.append({
            "key": spec.key,
            "label_en": spec.label_en,
            "label_ar": spec.label_ar,
            "beta_decay": spec.beta_decay,
            "alpha_attraction": spec.alpha_attraction,
            "base_attraction": spec.base_attraction,
            "outside_option": spec.outside_option,
            "ideal_walk_min": spec.ideal_walk_min,
            "daily_capacity": spec.daily_capacity,
            "demand_per_1k_pop": spec.demand_per_1k_pop,
        })
        for dst, mult in spec.synergy_induces.items():
            synergies.append({
                "src": spec.key,
                "dst": dst,
                "multiplier": mult,
                "decay_gamma": 0.22,
            })

    return {
        "meta": {
            "slug": slug,
            "label": label,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "radius_m": radius_m,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "total_est_pop": sum(b["est_pop"] for b in blocks),
        },
        "service_types": service_types,
        "synergies": synergies,
        "junctions": junctions,
        "streets": streets,
        "blocks": blocks,
        "services": services,
    }


def materialize_relate_db(payload: Dict[str, Any], db_path: Path) -> Dict[str, Any]:
    from backend.relate_core.builder import materialize_relate_v2
    return materialize_relate_v2(payload, db_path)


def ingest_area(
    slug: str,
    label: str,
    lat: float,
    lon: float,
    radius_m: float = 850,
    force: bool = False,
) -> Dict[str, Any]:
    from backend.relate_core.builder import enrich_payload_v2, materialize_relate_v2

    raw_path = DATA_DIR / "raw" / f"{slug}.osm.json"
    db_path = DATA_DIR / f"{slug}.rl"

    bbox = bbox_from_center(lat, lon, radius_m)
    raw = fetch_overpass(bbox, raw_path, force=force)
    base_payload = parse_osm_to_payload(raw, slug, label, lat, lon, radius_m)
    payload = enrich_payload_v2(base_payload, slug)

    print(
        f"[ingest:v2] Parsed {len(payload['junctions'])} junctions, "
        f"{len(payload['streets'])} streets, "
        f"{len(payload['parcels'])} 3D parcels "
        f"(day={payload['meta']['total_day_pop']:,}, night={payload['meta']['total_night_pop']:,}), "
        f"{len(payload['services'])} services, {len(payload['env_zones'])} env zones."
    )
    print(f"[ingest:v2] Materializing indexed Relate v2 store -> {db_path} ...")
    receipt = materialize_relate_v2(payload, db_path)
    print(
        f"[ingest:v2] Done! {db_path.name} ({receipt['total_bytes'] / 1024:.1f} KB, "
        f"nodes={receipt['relate_store_info']['node_count']}, "
        f"rels={receipt['relate_store_info']['rel_count']}, "
        f"sha256={receipt['sha256'][:12]}...)"
    )
    return payload["meta"]

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest live OpenStreetMap area into a Relate (.rl) graph.")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), default="irbid-yarmouk")
    parser.add_argument("--slug", type=str, help="Custom area slug")
    parser.add_argument("--label", type=str, help="Custom area display name")
    parser.add_argument("--lat", type=float, help="Center latitude")
    parser.add_argument("--lon", type=float, help="Center longitude")
    parser.add_argument("--radius", type=float, default=850, help="Radius in meters")
    parser.add_argument("--force", action="store_true", help="Re-download live OSM even if cached")
    args = parser.parse_args()

    if args.lat is not None and args.lon is not None:
        slug = args.slug or f"area_{args.lat:.3f}_{args.lon:.3f}".replace(".", "_")
        label = args.label or f"Live Area ({args.lat:.4f}, {args.lon:.4f})"
        ingest_area(slug, label, args.lat, args.lon, args.radius, force=args.force)
    else:
        p = PRESETS[args.preset]
        ingest_area(args.preset, p["label"], p["lat"], p["lon"], p["radius_m"], force=args.force)


if __name__ == "__main__":
    main()
