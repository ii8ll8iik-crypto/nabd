"""
Nabd Urban Physics MCP Server (Model Context Protocol).
Exposes the 7 Laws of Urban Physics, Relate (.rl) multi-hop queries,
Participatory Demographics, and Live Crisis Sandbox to any AI Agent
with zero hallucination.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

from backend.engine.catalog import DEMO_ZONE_PRESETS, SERVICE_CATALOG, build_custom_spec
from backend.engine.ingest import DATA_DIR, ingest_area
from backend.engine.physics import (
    DemographicZoneOverride,
    RealityOverrides,
    UrbanGraphEngine,
)

mcp = MCPServer("nabd-urban-physics")

_ENGINES: Dict[str, UrbanGraphEngine] = {}
_FORBIDDEN_CYPHER = re.compile(
    r"\b(CREATE|DELETE|DETACH|SET|MERGE|REMOVE|DROP)\b", re.IGNORECASE
)


def _get_engine(slug: str) -> UrbanGraphEngine:
    db_path = DATA_DIR / f"{slug}.rl"
    if not db_path.exists():
        available = [p.stem for p in sorted(DATA_DIR.glob("*.rl"))]
        raise ValueError(f"Area '{slug}' not found. Available areas: {available}")
    if slug not in _ENGINES:
        _ENGINES[slug] = UrbanGraphEngine(db_path)
    return _ENGINES[slug]


def _build_overrides(
    demographic_zones: Optional[List[Dict[str, Any]]] = None,
    closed_points: Optional[List[Dict[str, float]]] = None,
    demolished_blocks: Optional[List[str]] = None,
    extra_population: Optional[List[Dict[str, Any]]] = None,
) -> Optional[RealityOverrides]:
    if not any([demographic_zones, closed_points, demolished_blocks, extra_population]):
        return None
    zones = [
        DemographicZoneOverride(
            lat=float(z["lat"]),
            lon=float(z["lon"]),
            radius_m=float(z.get("radius_m", 250.0)),
            preset=z.get("preset"),
            profile=z.get("profile"),
            strength=float(z.get("strength", 0.88)),
        )
        for z in (demographic_zones or [])
    ]
    return RealityOverrides(
        closed_points=closed_points or [],
        demolished_blocks=demolished_blocks or [],
        extra_population=extra_population or [],
        demographic_zones=zones,
    )


@mcp.tool()
def list_areas_and_services() -> str:
    """List all synced Relate (.rl) urban graphs, supported service categories, and demographic brush presets."""
    areas = []
    for p in sorted(DATA_DIR.glob("*.rl")):
        eng = _get_engine(p.stem)
        areas.append({
            "slug": p.stem,
            "label": eng.meta.get("label", p.stem),
            "center_lat": eng.meta.get("center_lat"),
            "center_lon": eng.meta.get("center_lon"),
            "junctions": len(eng.junctions),
            "blocks": len(eng.blocks),
            "services": len(eng.services),
        })
    services = {
        k: {"label_en": v.label_en, "label_ar": v.label_ar, "beta_decay": v.beta_decay}
        for k, v in SERVICE_CATALOG.items()
    }
    return json.dumps(
        {
            "areas": areas,
            "services": services,
            "demographic_zone_presets": list(DEMO_ZONE_PRESETS.keys()),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def sync_live_area(
    lat: float,
    lon: float,
    radius_m: float = 750.0,
    label: Optional[str] = None,
    slug: Optional[str] = None,
) -> str:
    """Pull live OpenStreetMap streets, buildings, and services for ANY coordinates on Earth and build a Relate (.rl) graph."""
    final_slug = slug or f"live_{lat:.3f}_{lon:.3f}".replace(".", "_").replace("-", "m")
    final_label = label or f"Live ({lat:.4f}, {lon:.4f})"
    meta = ingest_area(final_slug, final_label, lat, lon, radius_m)
    _ENGINES.pop(final_slug, None)
    _get_engine(final_slug)
    return json.dumps({"status": "synced", "slug": final_slug, "meta": meta}, ensure_ascii=False, indent=2)


@mcp.tool()
def simulate_urban_injection(
    area_slug: str,
    lat: float,
    lon: float,
    category: str = "barber",
    time_of_day: str = "midday",
    attraction_multiplier: float = 1.0,
    capacity_multiplier: float = 1.0,
    custom_name: Optional[str] = None,
    custom_beta_decay: Optional[float] = None,
    custom_audience_weights: Optional[Dict[str, float]] = None,
    demographic_zones: Optional[List[Dict[str, Any]]] = None,
    closed_points: Optional[List[Dict[str, float]]] = None,
    demolished_blocks: Optional[List[str]] = None,
    extra_population: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Run the complete 7 Laws of Urban Physics + 200 Monte Carlo scenarios for injecting a facility at (lat, lon).
    Supports preset categories or custom Service DNA, time-of-day rhythm, facility scale, and live sandbox overrides.
    """
    eng = _get_engine(area_slug)
    ov = _build_overrides(demographic_zones, closed_points, demolished_blocks, extra_population)
    custom_spec = None
    if custom_name:
        custom_spec = build_custom_spec(
            name=custom_name,
            beta_decay=custom_beta_decay if custom_beta_decay is not None else 1.8,
            audience_weights=custom_audience_weights,
        )
    res = eng.simulate_injection(
        lat=lat,
        lon=lon,
        category=category,
        custom_spec=custom_spec,
        time_of_day=time_of_day,
        attraction_multiplier=attraction_multiplier,
        capacity_multiplier=capacity_multiplier,
        overrides=ov,
        monte_carlo_runs=200,
    )
    # Trim raw block ID lists to keep LLM context crisp while preserving counts
    res["spatial_effects"] = {
        "unlocked_blocks_count": len(res["spatial_effects"]["unlocked_block_ids"]),
        "directly_served_blocks_count": len(res["spatial_effects"]["served_block_ids"]),
    }
    return json.dumps(res, ensure_ascii=False, indent=2)


@mcp.tool()
def detect_topological_illusions(
    area_slug: str,
    category: str = "pharmacy",
    circuity_threshold: float = 1.6,
) -> str:
    """Law 1: Scan the Relate mobility graph to expose blocks that look close by straight line but are isolated by street network circuity."""
    eng = _get_engine(area_slug)
    res = eng.detect_topological_illusions(category=category, circuity_threshold=circuity_threshold)
    res["illusions"] = res["illusions"][:10]
    return json.dumps(res, ensure_ascii=False, indent=2)


@mcp.tool()
def find_optimal_sites(
    area_slug: str,
    category: str = "barber",
    time_of_day: str = "midday",
    top_k: int = 5,
    demographic_zones: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Law 6: Scan the Relate graph to discover the top K mathematically optimal locations maximizing network gain J."""
    eng = _get_engine(area_slug)
    ov = _build_overrides(demographic_zones=demographic_zones)
    sites = eng.optimize_locations(category=category, time_of_day=time_of_day, top_k=top_k, overrides=ov)
    return json.dumps(
        {"area": area_slug, "category": category, "time_of_day": time_of_day, "top_locations": sites},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def compare_two_locations(
    area_slug: str,
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
    category: str = "barber",
    time_of_day: str = "midday",
) -> str:
    """Run a grounded head-to-head A/B comparison of two candidate locations under identical 7-Law physics."""
    eng = _get_engine(area_slug)
    sim_a = eng.simulate_injection(lat_a, lon_a, category=category, time_of_day=time_of_day)
    sim_b = eng.simulate_injection(lat_b, lon_b, category=category, time_of_day=time_of_day)

    def summarize(sim: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "gain_J": sim["composite_network_gain_J"],
            "p10_p50_p90": [
                sim["monte_carlo_envelope"]["p10_conservative"],
                sim["monte_carlo_envelope"]["p50_base"],
                sim["monte_carlo_envelope"]["p90_optimistic"],
            ],
            "viability_pct": sim["monte_carlo_envelope"]["viability_probability_pct"],
            "audience_fit": sim["local_demographics"]["audience_fit_multiplier"],
            "new_unmet_demand": sim["hop1_gravity_and_access"]["new_unmet_demand_captured"],
            "cannibalization_pct": sim["hop1_gravity_and_access"]["cannibalization_pct"],
            "residents_unlocked": sim["hop1_gravity_and_access"]["residents_unlocked_within_ideal_walk"],
            "congestion_alert": sim["hop4_bpr_congestion"]["congestion_alert"],
        }

    ja, jb = sim_a["composite_network_gain_J"], sim_b["composite_network_gain_J"]
    winner = "Location A" if ja > jb else "Location B" if jb > ja else "Tie"
    return json.dumps(
        {
            "category": category,
            "winner": winner,
            "gain_delta_A_minus_B": round(ja - jb, 2),
            "location_A": summarize(sim_a),
            "location_B": summarize(sim_b),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def run_relate_cypher_readonly(area_slug: str, cypher: str) -> str:
    """Execute a safe read-only Cypher query directly against a Relate (.rl) urban graph (max 50 rows returned)."""
    if _FORBIDDEN_CYPHER.search(cypher):
        raise ValueError("Write operations are forbidden. Only read-only MATCH/RETURN queries are allowed.")
    eng = _get_engine(area_slug)
    res = eng.relate.query(cypher, tag="mcp:cypher_readonly")
    rows = res.rows
    return json.dumps(
        {
            "row_count": len(rows),
            "elapsed_ms": round(float(res.timings.get("elapsed_ms", 0.0)), 3),
            "rows": rows[:50],
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()
