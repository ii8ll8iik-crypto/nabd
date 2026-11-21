"""
Nabd Urban Physics API (FastAPI 3.0)
— 7 Laws + Terrain Slope + Environmental/Tourism Zoning + Universal Hybrid AI Strategist.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dataclasses import replace
from backend.api.ai_strategist import PROVIDER_DEFAULTS, run_hybrid_strategist
from backend.engine.dna_synthesizer import synthesize_facility_dna
from backend.engine.catalog import (
    DEMO_AXES,
    DEMO_ZONE_PRESETS,
    SERVICE_CATALOG,
    build_custom_spec,
)
from backend.engine.ingest import DATA_DIR, PRESETS, ingest_area
from backend.engine.physics import (
    DemographicZoneOverride,
    RealityOverrides,
    UrbanGraphEngine,
)
from backend.engine.terrain_env import env_zones_to_geojson

app = FastAPI(title="Nabd Urban Physics Engine", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_ENGINE_CACHE: Dict[str, UrbanGraphEngine] = {}


def get_engine(slug: str) -> UrbanGraphEngine:
    db_path = DATA_DIR / f"{slug}.rl"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Area '{slug}' not found.")
    if slug not in _ENGINE_CACHE:
        _ENGINE_CACHE[slug] = UrbanGraphEngine(db_path)
    return _ENGINE_CACHE[slug]


class DemoZoneInput(BaseModel):
    lat: float
    lon: float
    radius_m: float = 260.0
    preset: Optional[str] = None
    profile: Optional[Dict[str, float]] = None
    strength: float = 0.88


class OverridesInput(BaseModel):
    closed_junctions: List[str] = Field(default_factory=list)
    closed_points: List[Dict[str, float]] = Field(default_factory=list)
    demolished_blocks: List[str] = Field(default_factory=list)
    extra_population: List[Dict[str, Any]] = Field(default_factory=list)
    extra_services: List[Dict[str, Any]] = Field(default_factory=list)
    demographic_zones: List[DemoZoneInput] = Field(default_factory=list)


class CustomDNAInput(BaseModel):
    name: str
    beta_decay: float = 2.0
    alpha_attraction: float = 1.0
    daily_capacity: int = 80
    demand_per_1k_pop: float = 25.0
    ideal_walk_min: float = 10.0
    audience_weights: Dict[str, float] = Field(default_factory=dict)
    competes_with_category: str = "custom"
    time_profile: Optional[Dict[str, float]] = None
    synergy_induces: Optional[Dict[str, float]] = None


class SimulateRequest(BaseModel):
    lat: float
    lon: float
    category: Optional[str] = "barber"
    custom_dna: Optional[CustomDNAInput] = None
    time_of_day: str = "midday"
    attraction_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    overrides: Optional[OverridesInput] = None
    monte_carlo_runs: int = 200


class OptimizeRequest(BaseModel):
    category: Optional[str] = "barber"
    custom_dna: Optional[CustomDNAInput] = None
    time_of_day: str = "midday"
    top_k: int = 5
    overrides: Optional[OverridesInput] = None


class SynthesizeDnaRequest(BaseModel):
    name: str
    provider: str = "local"
    api_key: str = ""
    model: Optional[str] = None
    custom_base_url: Optional[str] = None


class IllusionRequest(BaseModel):
    category: str = "pharmacy"
    circuity_threshold: float = 1.6
    overrides: Optional[OverridesInput] = None


class SyncAreaRequest(BaseModel):
    lat: float
    lon: float
    radius_m: float = 750.0
    label: Optional[str] = None
    slug: Optional[str] = None
    force: bool = False


class ChatRequest(BaseModel):
    message: str
    lat: float
    lon: float
    category: str = "barber"
    time_of_day: str = "midday"
    overrides: Optional[OverridesInput] = None
    provider: str = "local"
    api_key: str = ""
    model: Optional[str] = None
    custom_base_url: Optional[str] = None
    history: List[Dict[str, str]] = Field(default_factory=list)
    lang: str = "en"


def _to_overrides(ov: Optional[OverridesInput]) -> Optional[RealityOverrides]:
    if ov is None:
        return None
    return RealityOverrides(
        closed_junctions=ov.closed_junctions,
        closed_points=ov.closed_points,
        demolished_blocks=ov.demolished_blocks,
        extra_population=ov.extra_population,
        extra_services=ov.extra_services,
        demographic_zones=[
            DemographicZoneOverride(
                lat=z.lat, lon=z.lon, radius_m=z.radius_m,
                preset=z.preset, profile=z.profile, strength=z.strength,
            )
            for z in ov.demographic_zones
        ],
    )


def _extract_raw_building_polygons(slug: str) -> Dict[str, List[List[float]]]:
    raw_path = DATA_DIR / "raw" / f"{slug}.osm.json"
    if not raw_path.exists():
        return {}
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    nodes: Dict[int, List[float]] = {}
    polys: Dict[str, List[List[float]]] = {}
    for el in raw.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = [el["lon"], el["lat"]]
    for el in raw.get("elements", []):
        if el["type"] == "way" and "building" in el.get("tags", {}):
            coords = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
            if len(coords) >= 3:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                polys[f"blk_{el['id']}"] = coords
    return polys




def _build_custom_from_input(d: Optional[CustomDNAInput]):
    if d is None:
        return None
    spec = build_custom_spec(
        name=d.name,
        beta_decay=d.beta_decay,
        alpha_attraction=d.alpha_attraction,
        daily_capacity=d.daily_capacity,
        demand_per_1k_pop=d.demand_per_1k_pop,
        ideal_walk_min=d.ideal_walk_min,
        audience_weights=d.audience_weights,
        competes_with_category=d.competes_with_category,
    )
    updates: Dict[str, Any] = {}
    if d.competes_with_category in SERVICE_CATALOG:
        updates["key"] = d.competes_with_category
    if d.time_profile:
        updates["time_profile"] = d.time_profile
    if d.synergy_induces:
        updates["synergy_induces"] = d.synergy_induces
    return replace(spec, **updates) if updates else spec


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "engine": "Nabd Urban Physics 3.0"}


@app.get("/api/catalog")
def get_catalog() -> Dict[str, Any]:
    available_dbs = sorted([p.stem for p in DATA_DIR.glob("*.rl")])
    services = {
        k: {
            "key": v.key, "label_en": v.label_en, "label_ar": v.label_ar,
            "beta_decay": v.beta_decay, "alpha_attraction": v.alpha_attraction,
            "ideal_walk_min": v.ideal_walk_min, "daily_capacity": v.daily_capacity,
            "audience_weights": v.audience_weights, "synergy_induces": v.synergy_induces,
        }
        for k, v in SERVICE_CATALOG.items()
    }
    return {
        "available_areas": available_dbs,
        "presets": PRESETS,
        "services": services,
        "demo_axes": list(DEMO_AXES),
        "demo_zone_presets": DEMO_ZONE_PRESETS,
        "ai_providers": list(PROVIDER_DEFAULTS.keys()),
    }


@app.get("/api/area/{slug}/layers")
def get_area_layers(slug: str) -> Dict[str, Any]:
    eng = get_engine(slug)
    raw_polys = _extract_raw_building_polygons(slug)

    b_features = []
    for i, b in enumerate(eng.blocks):
        demo_vec = eng._base_block_demo[i]
        dom_axis = DEMO_AXES[int(demo_vec.argmax())]
        ring = raw_polys.get(b["id"])
        if not ring:
            d = 0.00011
            lat, lon = b["lat"], b["lon"]
            ring = [
                [lon - d, lat - d], [lon + d, lat - d],
                [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d],
            ]
        b_features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "id": b["id"], "est_pop": b["est_pop"], "levels": b["levels"],
                "height": round(float(b["levels"]) * 3.8, 1),
                "dominant_demo": dom_axis,
                "students_pct": round(float(demo_vec[0]) * 100.0, 1),
                "families_pct": round(float(demo_vec[3]) * 100.0, 1),
            },
        })

    seen_edges: set[tuple[str, str]] = set()
    s_features = []
    for e in eng.streets:
        pair = (e["src"], e["dst"]) if e["src"] < e["dst"] else (e["dst"], e["src"])
        if pair in seen_edges:
            continue
        seen_edges.add(pair)
        u_idx = eng.j_index[e["src"]]
        v_idx = eng.j_index[e["dst"]]
        u, v = eng.junctions[u_idx], eng.junctions[v_idx]
        slope_pct = round(abs(float(eng.j_elev[v_idx] - eng.j_elev[u_idx])) / max(float(e["length_m"]), 1.0) * 100.0, 1) if eng.has_elevation else 0.0
        s_features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[u["lon"], u["lat"]], [v["lon"], v["lat"]]]},
            "properties": {
                "src": e["src"], "dst": e["dst"], "highway": e["highway"],
                "length_m": e["length_m"], "walk_min": e["walk_min"],
                "capacity": e["capacity"], "slope_pct": slope_pct,
            },
        })

    srv_features = []
    for s in eng.services:
        spec = SERVICE_CATALOG.get(s["category"])
        srv_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": {
                "id": s["id"], "name": s["name"], "category": s["category"],
                "label_ar": spec.label_ar if spec else s["category"],
                "attraction": s["attraction"], "capacity": s["capacity"],
            },
        })

    elev_min = round(float(eng.j_elev.min()), 1) if eng.has_elevation else None
    elev_max = round(float(eng.j_elev.max()), 1) if eng.has_elevation else None

    return {
        "meta": eng.meta,
        "stats": {
            "junctions": len(eng.junctions),
            "streets": len(s_features),
            "blocks": len(eng.blocks),
            "services": len(eng.services),
            "env_zones": len(eng.env_zones),
            "elev_min_m": elev_min,
            "elev_max_m": elev_max,
            "total_est_pop": sum(int(b["est_pop"]) for b in eng.blocks),
        },
        "buildings": {"type": "FeatureCollection", "features": b_features},
        "streets": {"type": "FeatureCollection", "features": s_features},
        "services": {"type": "FeatureCollection", "features": srv_features},
        "env_zones": env_zones_to_geojson(eng.env_zones),
    }


@app.post("/api/area/sync")
def sync_live_area(req: SyncAreaRequest) -> Dict[str, Any]:
    slug = req.slug or f"live_{req.lat:.3f}_{req.lon:.3f}".replace(".", "_").replace("-", "m")
    label = req.label or f"Live ({req.lat:.4f}, {req.lon:.4f})"
    try:
        meta = ingest_area(slug, label, req.lat, req.lon, req.radius_m, force=req.force)
        _ENGINE_CACHE.pop(slug, None)
        get_engine(slug)
        return {"status": "synced", "slug": slug, "meta": meta}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/area/{slug}/simulate")
def simulate(slug: str, req: SimulateRequest) -> Dict[str, Any]:
    eng = get_engine(slug)
    ov = _to_overrides(req.overrides)
    custom_spec = _build_custom_from_input(req.custom_dna)
    try:
        return eng.simulate_injection(
            lat=req.lat, lon=req.lon, category=req.category, custom_spec=custom_spec,
            time_of_day=req.time_of_day, attraction_multiplier=req.attraction_multiplier,
            capacity_multiplier=req.capacity_multiplier, overrides=ov,
            monte_carlo_runs=req.monte_carlo_runs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/area/{slug}/illusions")
def illusions(slug: str, req: IllusionRequest) -> Dict[str, Any]:
    eng = get_engine(slug)
    return eng.detect_topological_illusions(
        category=req.category, overrides=_to_overrides(req.overrides),
        circuity_threshold=req.circuity_threshold,
    )


@app.post("/api/area/{slug}/optimize")
def optimize(slug: str, req: OptimizeRequest) -> Dict[str, Any]:
    eng = get_engine(slug)
    custom_spec = _build_custom_from_input(req.custom_dna)
    top = eng.optimize_locations(
        category=req.category, custom_spec=custom_spec, time_of_day=req.time_of_day,
        top_k=req.top_k, overrides=_to_overrides(req.overrides),
    )
    return {"category": req.custom_dna.name if req.custom_dna else req.category, "time_of_day": req.time_of_day, "top_locations": top}


@app.post("/api/dna/synthesize")
def synthesize_dna_endpoint(req: SynthesizeDnaRequest) -> Dict[str, Any]:
    return synthesize_facility_dna(
        name=req.name,
        provider=req.provider,
        api_key=req.api_key,
        model=req.model,
        custom_base_url=req.custom_base_url,
    )


@app.post("/api/area/{slug}/chat")
def strategist_chat(slug: str, req: ChatRequest) -> Dict[str, Any]:
    eng = get_engine(slug)
    return run_hybrid_strategist(
        eng=eng,
        message=req.message,
        lat=req.lat,
        lon=req.lon,
        active_category=req.category,
        time_of_day=req.time_of_day,
        overrides=_to_overrides(req.overrides),
        provider=req.provider,
        api_key=req.api_key,
        model=req.model,
        custom_base_url=req.custom_base_url,
        history=req.history,
        lang=req.lang,
    )


@app.get("/api/geocode")
def geocode_place(q: str, lang: str = "en") -> Dict[str, Any]:
    """Global city/neighborhood search via OpenStreetMap Nominatim."""
    query = q.strip()
    if len(query) < 2:
        return {"results": []}
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 5})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NabdUrbanPhysics/3.0 (global-search)",
            "Accept-Language": "ar,en" if lang == "ar" else "en,ar",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        results = [
            {
                "display_name": item.get("display_name", ""),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "type": item.get("type", ""),
            }
            for item in raw
        ]
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Geocode lookup failed: {exc}")
