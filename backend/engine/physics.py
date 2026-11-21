"""
Nabd Urban Physics Engine v2 — Live Transactional Relate Core + 3D Volumetric Parcels
+ Bounded Local Subgraph + 7 Laws + Tobler's Terrain + Environmental Guardrail + Agent Memory.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from backend.engine.catalog import (
    BASELINE_DEMO,
    DEMO_AXES,
    DEMO_ZONE_PRESETS,
    SERVICE_CATALOG,
    ServiceSpec,
)
from backend.engine.terrain_env import (
    evaluate_site_environment,
    haversine_m,
    tobler_speed_ratio,
)
from backend.relate_core import RelateClient


def _dict_to_demo_vec(d: Dict[str, float]) -> np.ndarray:
    v = np.array([max(0.0, float(d.get(ax, 0.0))) for ax in DEMO_AXES], dtype=np.float64)
    s = float(v.sum())
    return v / s if s > 1e-9 else np.array([BASELINE_DEMO[ax] for ax in DEMO_AXES], dtype=np.float64)


BASELINE_VEC = _dict_to_demo_vec(BASELINE_DEMO)


@dataclass
class DemographicZoneOverride:
    lat: float
    lon: float
    radius_m: float = 250.0
    preset: Optional[str] = None
    profile: Optional[Dict[str, float]] = None
    strength: float = 0.88


@dataclass
class RealityOverrides:
    closed_junctions: List[str] = field(default_factory=list)
    closed_points: List[Dict[str, float]] = field(default_factory=list)
    demolished_blocks: List[str] = field(default_factory=list)
    extra_population: List[Dict[str, Any]] = field(default_factory=list)
    extra_services: List[Dict[str, Any]] = field(default_factory=list)
    demographic_zones: List[DemographicZoneOverride] = field(default_factory=list)


class UrbanGraphEngine:
    def __init__(self, db_path: Path | str, read_only: bool = False) -> None:
        self.db_path = Path(db_path).resolve()
        self.relate = RelateClient(self.db_path, read_only=read_only)
        self._load_from_relate()

    def close(self) -> None:
        self.relate.close()

    def __enter__(self) -> "UrbanGraphEngine":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _load_from_relate(self) -> None:
        metas = self.relate.query(
            "MATCH (m:Meta) RETURN m.slug AS slug, m.label AS label, m.schema_version AS schema_version, "
            "m.center_lat AS center_lat, m.center_lon AS center_lon, m.radius_m AS radius_m, "
            "m.synced_at AS synced_at, m.total_est_pop AS total_est_pop, "
            "m.total_day_pop AS total_day_pop, m.total_night_pop AS total_night_pop, "
            "m.total_gfa_m2 AS total_gfa_m2, m.min_elev_m AS min_elev_m, m.max_elev_m AS max_elev_m",
            tag="boot:meta",
        ).rows
        self.meta: Dict[str, Any] = metas[0] if metas else {}

        self.synergies: Dict[str, List[Dict[str, Any]]] = {}
        for row in self.relate.query(
            "MATCH (a:ServiceType)-[r:SYNERGIZES_WITH]->(b:ServiceType) "
            "RETURN a.key AS src, b.key AS dst, r.multiplier AS multiplier, r.decay_gamma AS decay_gamma",
            tag="boot:synergies",
        ).rows:
            self.synergies.setdefault(row["src"], []).append(row)

        self.junctions = self.relate.query(
            "MATCH (j:Junction) RETURN j.id AS id, j.lat AS lat, j.lon AS lon, j.elev_m AS elev_m",
            tag="boot:junctions",
        ).rows
        self.j_index: Dict[str, int] = {j["id"]: i for i, j in enumerate(self.junctions)}
        self.j_coords = np.array([[j["lat"], j["lon"]] for j in self.junctions], dtype=np.float64)
        self.j_tree = cKDTree(self.j_coords)

        valid_elevs = [float(j["elev_m"]) for j in self.junctions if j.get("elev_m") is not None]
        self.has_elevation = len(valid_elevs) > 0 and (max(valid_elevs) - min(valid_elevs) > 0.01 or max(valid_elevs) > 0.1)
        med_elev = float(np.median(valid_elevs)) if valid_elevs else 0.0
        self.elev_map: Dict[str, float] = {
            j["id"]: (float(j["elev_m"]) if j.get("elev_m") is not None else med_elev)
            for j in self.junctions
        }
        self.j_elev = np.array([self.elev_map[j["id"]] for j in self.junctions], dtype=np.float64)

        env_rows = self.relate.query(
            "MATCH (z:EnvZone) RETURN z.id AS id, z.name AS name, z.zone_type AS zone_type, "
            "z.label_ar AS label_ar, z.geom_type AS geom_type, z.lat AS lat, z.lon AS lon, "
            "z.is_restricted AS is_restricted, z.coordinates_json AS coordinates_json",
            tag="boot:env_zones",
        ).rows
        self.env_zones: List[Dict[str, Any]] = []
        for r in env_rows:
            try:
                coords = json.loads(r.get("coordinates_json") or "[]")
            except Exception:
                coords = [r.get("lon", 0.0), r.get("lat", 0.0)]
            self.env_zones.append({
                "id": r["id"],
                "name": r.get("name") or r.get("zone_type") or "Zone",
                "zone_type": r.get("zone_type") or "park",
                "label_ar": r.get("label_ar") or r.get("zone_type") or "منطقة",
                "geom_type": r.get("geom_type") or "Point",
                "lat": float(r.get("lat") or 0.0),
                "lon": float(r.get("lon") or 0.0),
                "is_restricted": bool(r.get("is_restricted", False)),
                "coordinates": coords,
            })

        self.streets = self.relate.query(
            "MATCH (a:Junction)-[e:STREET]->(b:Junction) "
            "RETURN a.id AS src, b.id AS dst, e.length_m AS length_m, e.walk_min AS walk_min, "
            "e.drive_min AS drive_min, e.highway AS highway, e.capacity AS capacity, e.oneway AS oneway",
            tag="boot:streets",
        ).rows

        self.blocks = self.relate.query(
            "MATCH (b:Parcel)-[r:FRONTS_ON]->(j:Junction) "
            "RETURN b.id AS id, b.lat AS lat, b.lon AS lon, b.area_m2 AS area_m2, "
            "b.levels AS levels, b.gfa_m2 AS gfa_m2, b.est_pop AS est_pop, "
            "b.day_pop AS day_pop, b.night_pop AS night_pop, b.kind AS kind, "
            "b.land_use AS land_use, b.site_suitability AS site_suitability, "
            "b.ownership_status AS ownership_status, b.env_restricted AS env_restricted, "
            "j.id AS junction_id, r.euclid_m AS snap_m, r.walk_min AS snap_walk_min",
            tag="boot:parcels",
        ).rows
        self.parcels = self.blocks
        self.p_index: Dict[str, int] = {b["id"]: i for i, b in enumerate(self.blocks)}
        self.p_coords = np.array([[b["lat"], b["lon"]] for b in self.blocks], dtype=np.float64) if self.blocks else np.zeros((0, 2))
        self.p_tree = cKDTree(self.p_coords) if len(self.blocks) else None

        self.services = self.relate.query(
            "MATCH (s:Service)-[r:LOCATED_ON]->(j:Junction) "
            "RETURN s.id AS id, s.name AS name, s.category AS category, s.lat AS lat, s.lon AS lon, "
            "s.attraction AS attraction, s.capacity AS capacity, "
            "j.id AS junction_id, r.euclid_m AS snap_m, r.walk_min AS snap_walk_min",
            tag="boot:services",
        ).rows

        (
            self._base_walk_T,
            self._base_flat_walk_T,
            self._base_len_T,
            self._incident_cap,
            self._arterial_j,
        ) = self._build_sparse_graphs(set())
        self._base_block_demo = self._infer_graph_demographics()

    def snap_parcel(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Snap a map click to the nearest real 3D (:Parcel) rather than an intersection."""
        if self.p_tree is None or not self.blocks:
            return None
        _, p_idx = self.p_tree.query([lat, lon])
        p = self.blocks[int(p_idx)]
        dist_m = round(haversine_m(lat, lon, float(p["lat"]), float(p["lon"])), 1)
        return {**p, "dist_to_click_m": dist_m}

    def run_whatif_relate_context(
        self,
        parcel: Optional[Dict[str, Any]],
        category: str,
        label_en: str,
    ) -> Dict[str, Any]:
        """Run a real ACID What-If injection + multi-hop context traversal inside Relate, then ROLLBACK."""
        if not parcel:
            return {"tx_state": "SKIPPED", "parcel": {}, "multi_hop_context": {}}
        if self.relate.read_only:
            r1 = self.relate.query(
                "MATCH (p:Parcel {id: $pid})-[:FRONTS_ON]->(j:Junction) "
                "RETURN p.id AS parcel_id, p.land_use AS land_use, p.site_suitability AS suitability, "
                "p.ownership_status AS ownership, p.levels AS levels, p.gfa_m2 AS gfa_m2, j.elev_m AS elev_m",
                {"pid": parcel["id"]},
                tag=f"context:{category}:site",
            )
            r2 = self.relate.query(
                "MATCH (p:Parcel {id: $pid})-[:FRONTS_ON]->(j:Junction) "
                "OPTIONAL MATCH (j)-[:STREET*1..2]-(nj:Junction)<-[:LOCATED_ON]-(s:Service) "
                "WITH j, collect(DISTINCT CASE WHEN s.category = $cat THEN s.name ELSE null END) AS comp_names, "
                "     count(DISTINCT s) AS nearby_services "
                "OPTIONAL MATCH (j)-[:NEAR_ZONE]->(z:EnvZone) "
                "RETURN nearby_services, size([x IN comp_names WHERE x IS NOT NULL]) AS nearby_competitors, "
                "       collect(DISTINCT z.name)[0..5] AS nearby_env_zones",
                {"pid": parcel["id"], "cat": category},
                tag=f"context:{category}:hops",
            )
            return {
                "tx_state": "READ_ONLY_CONTEXT",
                "elapsed_ms": round(
                    float(r1.timings.get("elapsed_ms", 0.0)) + float(r2.timings.get("elapsed_ms", 0.0)), 3
                ),
                "parcel": r1.rows[0] if r1.rows else {},
                "multi_hop_context": r2.rows[0] if r2.rows else {},
            }

        sim_id = f"whatif_{uuid.uuid4().hex[:8]}"
        res = self.relate.whatif_rollback(
            [
                (
                    "MATCH (p:Parcel {id: $pid})-[:FRONTS_ON]->(j:Junction) "
                    "CREATE (wf:WhatIfFacility {id: $sid, category: $cat, label: $lbl})-[:PROPOSED_AT]->(p) "
                    "RETURN wf.id AS sim_id, p.id AS parcel_id, p.land_use AS land_use, "
                    "p.site_suitability AS suitability, p.ownership_status AS ownership, "
                    "p.levels AS levels, p.gfa_m2 AS gfa_m2, j.elev_m AS elev_m",
                    {"pid": parcel["id"], "sid": sim_id, "cat": category, "lbl": label_en},
                ),
                (
                    "MATCH (wf:WhatIfFacility {id: $sid})-[:PROPOSED_AT]->(p:Parcel)-[:FRONTS_ON]->(j:Junction) "
                    "OPTIONAL MATCH (j)-[:STREET*1..2]-(nj:Junction)<-[:LOCATED_ON]-(s:Service) "
                    "WITH wf, j, collect(DISTINCT CASE WHEN s.category = $cat THEN s.name ELSE null END) AS comp_names, "
                    "     count(DISTINCT s) AS nearby_services "
                    "OPTIONAL MATCH (j)-[:NEAR_ZONE]->(z:EnvZone) "
                    "RETURN nearby_services, size([x IN comp_names WHERE x IS NOT NULL]) AS nearby_competitors, "
                    "       collect(DISTINCT z.name)[0..5] AS nearby_env_zones",
                    {"sid": sim_id, "cat": category},
                ),
            ],
            tag=f"whatif:{category}",
        )
        site_row = res[0].rows[0] if res and res[0].rows else {}
        hop_row = res[1].rows[0] if len(res) > 1 and res[1].rows else {}
        total_ms = round(sum(float(r.timings.get("elapsed_ms", 0.0)) for r in res), 3)
        return {
            "tx_state": "ROLLED_BACK",
            "elapsed_ms": total_ms,
            "parcel": site_row,
            "multi_hop_context": hop_row,
        }

    def commit_agent_decision(
        self,
        parcel_id: str,
        category: str,
        status: str,
        reason: str,
        actor: str = "studio",
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist an APPROVED / REJECTED / WATCHLIST decision node connected to (:Parcel) via ACID COMMIT."""
        did = f"dec_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        m_json = json.dumps(metrics or {}, ensure_ascii=False)
        res = self.relate.commit_transaction(
            [
                (
                    "MATCH (p:Parcel {id: $pid}) "
                    "CREATE (d:AgentDecision {id: $did, category: $cat, status: $st, reason: $rsn, "
                    "actor: $actor, created_at: $ts, metrics_json: $mj})-[:EVALUATES]->(p) "
                    "RETURN d.id AS id, d.status AS status, d.category AS category, d.reason AS reason, "
                    "d.actor AS actor, d.created_at AS created_at, p.id AS parcel_id, p.lat AS lat, p.lon AS lon",
                    {
                        "pid": parcel_id,
                        "did": did,
                        "cat": category,
                        "st": status.upper(),
                        "rsn": reason,
                        "actor": actor,
                        "ts": now,
                        "mj": m_json,
                    },
                )
            ],
            tag=f"commit:decision:{status.lower()}",
        )
        return res[0].rows[0] if res and res[0].rows else {"id": did, "status": status.upper()}

    def list_agent_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self.relate.query(
            "MATCH (d:AgentDecision)-[:EVALUATES]->(p:Parcel) "
            "RETURN d.id AS id, d.category AS category, d.status AS status, d.reason AS reason, "
            "d.actor AS actor, d.created_at AS created_at, d.metrics_json AS metrics_json, "
            "p.id AS parcel_id, p.lat AS lat, p.lon AS lon, p.land_use AS land_use, "
            "p.ownership_status AS ownership_status "
            "ORDER BY d.created_at DESC LIMIT $lim",
            {"lim": int(limit)},
            tag="read:decisions",
        ).rows
        for r in rows:
            try:
                r["metrics"] = json.loads(r.pop("metrics_json", "{}") or "{}")
            except Exception:
                r["metrics"] = {}
        return rows

    def set_parcel_ownership(self, parcel_id: str, ownership_status: str, note: str = "") -> Dict[str, Any]:
        """Update real-world parcel ownership / lease readiness (e.g. BLOCKED_OWNERSHIP) in Relate via COMMIT."""
        res = self.relate.commit_transaction(
            [
                (
                    "MATCH (p:Parcel {id: $pid}) "
                    "SET p.ownership_status = $st, p.ownership_note = $note "
                    "RETURN p.id AS parcel_id, p.ownership_status AS ownership_status, p.site_suitability AS site_suitability",
                    {"pid": parcel_id, "st": ownership_status, "note": note},
                )
            ],
            tag="commit:parcel_ownership",
        )
        if parcel_id in self.p_index:
            self.blocks[self.p_index[parcel_id]]["ownership_status"] = ownership_status
        return res[0].rows[0] if res and res[0].rows else {"parcel_id": parcel_id, "ownership_status": ownership_status}

    def _build_sparse_graphs(
        self, closed_jids: set[str]
    ) -> Tuple[csr_matrix, csr_matrix, csr_matrix, Dict[int, float], set[int]]:
        n = len(self.junctions)
        rows, cols, w_slope_vals, w_flat_vals, l_vals = [], [], [], [], []
        incident_cap: Dict[int, float] = {}
        arterial_j: set[int] = set()

        for e in self.streets:
            if e["src"] in closed_jids or e["dst"] in closed_jids:
                continue
            u = self.j_index.get(e["src"])
            v = self.j_index.get(e["dst"])
            if u is None or v is None:
                continue

            length_m = max(float(e["length_m"]), 0.5)
            flat_w = max(float(e["walk_min"]), 1e-4)

            # Directed Tobler slope cost for walking u -> v (uphill slows you down; gentle downhill speeds you up)
            if self.has_elevation:
                dh = float(self.j_elev[v] - self.j_elev[u])
                slope = dh / length_m
                speed_ratio = tobler_speed_ratio(slope)
                slope_w = flat_w / max(speed_ratio, 0.25)
            else:
                slope_w = flat_w

            rows.append(v)
            cols.append(u)
            w_slope_vals.append(slope_w)
            w_flat_vals.append(flat_w)
            l_vals.append(length_m)
            incident_cap[u] = incident_cap.get(u, 0.0) + float(e["capacity"])
            if e["highway"] in ("primary", "secondary", "primary_link", "secondary_link"):
                arterial_j.add(u)
                arterial_j.add(v)

        walk_T = csr_matrix((w_slope_vals, (rows, cols)), shape=(n, n))
        flat_walk_T = csr_matrix((w_flat_vals, (rows, cols)), shape=(n, n))
        len_T = csr_matrix((l_vals, (rows, cols)), shape=(n, n))
        return walk_T, flat_walk_T, len_T, incident_cap, arterial_j

    def _infer_graph_demographics(self) -> np.ndarray:
        n_b = len(self.blocks)
        if n_b == 0:
            return np.zeros((0, len(DEMO_AXES)), dtype=np.float64)

        b_j = np.array([self.j_index[b["junction_id"]] for b in self.blocks], dtype=np.int64)
        demo = np.tile(BASELINE_VEC, (n_b, 1))

        def min_walk_to_indices(j_indices: List[int]) -> np.ndarray:
            if not j_indices:
                return np.full(n_b, np.inf)
            mat = dijkstra(self._base_walk_T, directed=True, indices=j_indices, limit=25.0)
            return mat[b_j] if mat.ndim == 1 else np.min(mat[:, b_j], axis=0)

        uni_j = [self.j_index[s["junction_id"]] for s in self.services if s["category"] == "university"]
        school_j = [self.j_index[s["junction_id"]] for s in self.services if s["category"] == "school"]
        art_j = list(self._arterial_j)

        t_uni = min_walk_to_indices(uni_j)
        t_school = min_walk_to_indices(school_j)
        t_art = min_walk_to_indices(art_j)

        uni_pull = np.where(np.isfinite(t_uni), np.exp(-t_uni / 8.0), 0.0)
        school_pull = np.where(np.isfinite(t_school), np.exp(-t_school / 7.0), 0.0)
        art_pull = np.where(np.isfinite(t_art), np.exp(-t_art / 3.5), 0.0)

        demo[:, 0] += 0.32 * uni_pull
        demo[:, 1] += 0.14 * uni_pull
        demo[:, 2] += 0.14 * uni_pull
        demo[:, 3] += 0.24 * school_pull
        demo[:, 5] += 0.20 * art_pull

        return demo / np.maximum(demo.sum(axis=1, keepdims=True), 1e-9)

    def snap_point(self, lat: float, lon: float) -> Tuple[int, str, float, float]:
        _, idx = self.j_tree.query([lat, lon])
        j_idx = int(idx)
        j = self.junctions[j_idx]
        dist_m = haversine_m(lat, lon, j["lat"], j["lon"])
        return j_idx, j["id"], round(dist_m, 2), round((dist_m / 1.25) / 60.0, 4)

    def _active_state(
        self, overrides: Optional[RealityOverrides]
    ) -> Tuple[csr_matrix, csr_matrix, csr_matrix, Dict[int, float], List[Dict[str, Any]], np.ndarray, List[Dict[str, Any]]]:
        if not overrides:
            return (
                self._base_walk_T, self._base_flat_walk_T, self._base_len_T,
                self._incident_cap, self.blocks, self._base_block_demo, self.services,
            )

        closed_set = set(overrides.closed_junctions)
        for cp in overrides.closed_points:
            _, jid, _, _ = self.snap_point(float(cp["lat"]), float(cp["lon"]))
            closed_set.add(jid)

        if closed_set:
            walk_T, flat_walk_T, len_T, inc_cap, _ = self._build_sparse_graphs(closed_set)
        else:
            walk_T, flat_walk_T, len_T, inc_cap = (
                self._base_walk_T, self._base_flat_walk_T, self._base_len_T, self._incident_cap
            )

        demolished = set(overrides.demolished_blocks)
        keep_idx = [i for i, b in enumerate(self.blocks) if b["id"] not in demolished]
        active_blocks = [self.blocks[i] for i in keep_idx]
        active_demo = self._base_block_demo[keep_idx].copy() if keep_idx else np.zeros((0, len(DEMO_AXES)))

        if overrides.extra_population:
            extra_demos = []
            for idx, ep in enumerate(overrides.extra_population):
                _, jid, snap_m, snap_w = self.snap_point(float(ep["lat"]), float(ep["lon"]))
                active_blocks.append({
                    "id": f"live_pop_{idx}",
                    "lat": float(ep["lat"]), "lon": float(ep["lon"]),
                    "area_m2": 600.0, "levels": 4.0,
                    "est_pop": max(1, int(ep["pop"])),
                    "kind": "live_override_surge",
                    "junction_id": jid, "snap_m": snap_m, "snap_walk_min": snap_w,
                })
                prof = ep.get("profile")
                extra_demos.append(_dict_to_demo_vec(prof) if isinstance(prof, dict) else BASELINE_VEC.copy())
            active_demo = np.vstack([active_demo, np.array(extra_demos)]) if len(active_demo) else np.array(extra_demos)

        if overrides.demographic_zones and active_blocks:
            for zone in overrides.demographic_zones:
                if zone.profile:
                    target_vec = _dict_to_demo_vec(zone.profile)
                elif zone.preset and zone.preset in DEMO_ZONE_PRESETS:
                    target_vec = _dict_to_demo_vec(DEMO_ZONE_PRESETS[zone.preset])
                else:
                    continue
                strength = max(0.0, min(1.0, float(zone.strength)))
                for bi, b in enumerate(active_blocks):
                    d_m = haversine_m(b["lat"], b["lon"], zone.lat, zone.lon)
                    if d_m <= zone.radius_m:
                        w = strength * (1.0 - 0.35 * (d_m / max(zone.radius_m, 1.0)))
                        active_demo[bi] = (1.0 - w) * active_demo[bi] + w * target_vec
            active_demo = active_demo / np.maximum(active_demo.sum(axis=1, keepdims=True), 1e-9)

        active_services = list(self.services)
        for idx, es in enumerate(overrides.extra_services):
            cat = es["category"]
            if cat not in SERVICE_CATALOG:
                continue
            sp = SERVICE_CATALOG[cat]
            _, jid, snap_m, snap_w = self.snap_point(float(es["lat"]), float(es["lon"]))
            active_services.append({
                "id": f"local_srv_{idx}",
                "name": es.get("name", f"Local {sp.label_en}"),
                "category": cat,
                "lat": float(es["lat"]), "lon": float(es["lon"]),
                "attraction": float(es.get("attraction", sp.base_attraction)),
                "capacity": int(es.get("capacity", sp.daily_capacity)),
                "junction_id": jid, "snap_m": snap_m, "snap_walk_min": snap_w,
            })

        return walk_T, flat_walk_T, len_T, inc_cap, active_blocks, active_demo, active_services

    def detect_topological_illusions(
        self,
        category: str,
        overrides: Optional[RealityOverrides] = None,
        circuity_threshold: float = 1.6,
    ) -> Dict[str, Any]:
        walk_T, _, len_T, _, blocks, _, services = self._active_state(overrides)
        cat_services = [s for s in services if s["category"] == category]
        if not cat_services or not blocks:
            return {"category": category, "illusion_count": 0, "affected_residents": 0, "mean_circuity": 1.0, "illusions": []}

        srv_j = [self.j_index[s["junction_id"]] for s in cat_services]
        dist_m_matrix = dijkstra(len_T, directed=True, indices=srv_j, limit=2500.0)
        walk_m_matrix = dijkstra(walk_T, directed=True, indices=srv_j, limit=35.0)
        if dist_m_matrix.ndim == 1:
            dist_m_matrix = dist_m_matrix[None, :]
            walk_m_matrix = walk_m_matrix[None, :]

        illusions: List[Dict[str, Any]] = []
        circuities: List[float] = []

        for b in blocks:
            bj = self.j_index[b["junction_id"]]
            best_net, best_euclid, best_walk, nearest_srv = float("inf"), float("inf"), float("inf"), None
            for si, s in enumerate(cat_services):
                d_net = float(dist_m_matrix[si, bj]) + float(b["snap_m"]) + float(s["snap_m"])
                if math.isfinite(d_net) and d_net < best_net:
                    best_net = d_net
                    best_euclid = haversine_m(b["lat"], b["lon"], s["lat"], s["lon"])
                    best_walk = float(walk_m_matrix[si, bj]) + float(b["snap_walk_min"]) + float(s["snap_walk_min"])
                    nearest_srv = s["name"]

            if math.isfinite(best_net) and best_euclid >= 50.0:
                ci = best_net / best_euclid
                circuities.append(ci)
                if ci >= circuity_threshold:
                    illusions.append({
                        "block_id": b["id"], "lat": b["lat"], "lon": b["lon"], "est_pop": b["est_pop"],
                        "euclid_m": round(best_euclid, 1), "network_m": round(best_net, 1),
                        "walk_min": round(best_walk, 1), "circuity_index": round(ci, 2),
                        "nearest_service": nearest_srv,
                    })

        illusions.sort(key=lambda x: x["circuity_index"], reverse=True)
        return {
            "category": category,
            "illusion_count": len(illusions),
            "affected_residents": sum(x["est_pop"] for x in illusions),
            "mean_circuity": round(float(np.mean(circuities)), 2) if circuities else 1.0,
            "illusions": illusions[:35],
        }

    def simulate_injection(
        self,
        lat: float,
        lon: float,
        category: Optional[str] = "barber",
        custom_spec: Optional[ServiceSpec] = None,
        time_of_day: str = "midday",
        attraction_multiplier: float = 1.0,
        capacity_multiplier: float = 1.0,
        overrides: Optional[RealityOverrides] = None,
        monte_carlo_runs: int = 200,
        seed: int = 42,
        include_relate_tx: bool = True,
    ) -> Dict[str, Any]:
        if custom_spec is not None:
            spec = custom_spec
        else:
            if not category or category not in SERVICE_CATALOG:
                raise ValueError(f"Unknown service category: {category}")
            spec = SERVICE_CATALOG[category]

        rhythm = spec.time_profile.get(time_of_day, 1.0)
        eff_capacity = max(5.0, float(spec.daily_capacity) * max(0.3, float(capacity_multiplier)))

        walk_T, flat_walk_T, _, inc_cap, blocks, block_demo, services = self._active_state(overrides)
        inj_j_idx, inj_jid, inj_snap_m, inj_snap_w = self.snap_point(lat, lon)

        # Environmental Zoning Guardrail + Parks/Water/Tourism/Recreation Boost
        env_eval = evaluate_site_environment(
            lat, lon, spec.key, f"{spec.label_en} {spec.label_ar}", self.env_zones, services
        )
        env_boost = float(env_eval["env_boost_multiplier"])
        eff_attraction = spec.base_attraction * max(0.3, float(attraction_multiplier)) * env_boost

        existing = [s for s in services if s["category"] == spec.key]
        all_srv_j = [self.j_index[s["junction_id"]] for s in existing] + [inj_j_idx]
        all_snap_w = np.array([float(s["snap_walk_min"]) for s in existing] + [inj_snap_w], dtype=np.float64)
        all_attr = np.array([float(s["attraction"]) for s in existing] + [eff_attraction], dtype=np.float64)
        all_cap = np.array([float(s["capacity"]) for s in existing] + [eff_capacity], dtype=np.float64)

        max_walk_bound = max(45.0, spec.ideal_walk_min * 3.0)
        walk_from_targets = dijkstra(walk_T, directed=True, indices=all_srv_j, limit=max_walk_bound)
        if walk_from_targets.ndim == 1:
            walk_from_targets = walk_from_targets[None, :]

        # Flat walk time to injected site only (to measure pure terrain uphill/downhill friction!)
        flat_to_inj = dijkstra(flat_walk_T, directed=True, indices=inj_j_idx, limit=max_walk_bound)

        b_j = np.array([self.j_index[b["junction_id"]] for b in blocks], dtype=np.int64)
        b_snap = np.array([float(b["snap_walk_min"]) for b in blocks], dtype=np.float64)
        day_w = {"morning": 0.60, "midday": 0.72, "evening": 0.35, "late_night": 0.15}.get(time_of_day, 0.55)
        b_pop = np.array([
            max(
                1.0,
                day_w * float(b.get("day_pop") if b.get("day_pop") is not None else b["est_pop"])
                + (1.0 - day_w) * float(b.get("night_pop") if b.get("night_pop") is not None else b["est_pop"]),
            )
            for b in blocks
        ], dtype=np.float64)

        w_s = np.array([float(spec.audience_weights.get(ax, 0.5)) for ax in DEMO_AXES], dtype=np.float64)
        base_affinity = max(float(np.dot(BASELINE_VEC, w_s)), 1e-6)
        block_affinity_mult = (block_demo @ w_s) / base_affinity
        b_demand = b_pop * block_affinity_mult * (spec.demand_per_1k_pop / 1000.0) * rhythm

        T_all = walk_from_targets[:, b_j].T + b_snap[:, None] + all_snap_w[None, :]
        T_eff = np.maximum(T_all, 0.5)
        reachable = np.isfinite(T_all) & (T_all <= max(45.0, spec.ideal_walk_min * 3.0))

        # Terrain & Elevation Telemetry around the injected site
        site_elev_m = round(float(self.j_elev[inj_j_idx]), 1) if self.has_elevation else None
        near_mask = T_all[:, -1] <= spec.ideal_walk_min
        if self.has_elevation and np.any(near_mask):
            t_slope_near = T_all[near_mask, -1]
            t_flat_near = flat_to_inj[b_j[near_mask]] + b_snap[near_mask] + inj_snap_w
            valid_t = np.isfinite(t_slope_near) & np.isfinite(t_flat_near) & (t_flat_near > 0.3)
            if np.any(valid_t):
                friction_pct = float(np.mean((t_slope_near[valid_t] / t_flat_near[valid_t] - 1.0) * 100.0))
                dh_mean = float(np.mean(site_elev_m - self.j_elev[b_j[near_mask][valid_t]]))
            else:
                friction_pct, dh_mean = 0.0, 0.0
            if friction_pct >= 6.0:
                terrain_verdict = "مرتفع يتطلب صعوداً شاقاً للوصول"
                terrain_verdict_en = "Elevated ridge — steep uphill walk approach"
            elif friction_pct <= -4.0:
                terrain_verdict = "موقع منخفض نسبياً (نزول مريح للمشاة)"
                terrain_verdict_en = "Lower elevation — gentle downhill walk access"
            else:
                terrain_verdict = "أرض شبه مستوية وسهلة المشي"
                terrain_verdict_en = "Flat & comfortable pedestrian grade"
        else:
            friction_pct, dh_mean = 0.0, 0.0
            terrain_verdict = "أرض مستوية"
            terrain_verdict_en = "Flat grade"

        if np.any(near_mask):
            near_pop = b_pop[near_mask]
            local_demo_vec = (near_pop[:, None] * block_demo[near_mask]).sum(axis=0) / max(near_pop.sum(), 1.0)
            local_match_mult = float(np.sum(near_pop * block_affinity_mult[near_mask]) / max(near_pop.sum(), 1.0))
        else:
            local_demo_vec, local_match_mult = BASELINE_VEC, 1.0
        local_demo_dict = {ax: round(float(local_demo_vec[i]) * 100.0, 1) for i, ax in enumerate(DEMO_AXES)}

        # LAW 2: Competitive Huff Gravity + Outside Option U_0 (with Slope-Adjusted Walk Times!)
        beta, alpha, u0 = spec.beta_decay, spec.alpha_attraction, spec.outside_option
        util_all = np.where(reachable, (all_attr[None, :] ** alpha) * (T_eff ** (-beta)), 0.0)
        util_before = util_all[:, :-1]

        denom_before = util_before.sum(axis=1, keepdims=True) + u0
        P_before = util_before / denom_before
        visits_before = (b_demand[:, None] * P_before).sum(axis=0) if len(existing) else np.array([])

        denom_after = util_all.sum(axis=1, keepdims=True) + u0
        P_after = util_all / denom_after
        visits_after_all = (b_demand[:, None] * P_after).sum(axis=0)

        injected_visits = float(visits_after_all[-1])
        visits_after_existing = visits_after_all[:-1] if len(existing) else np.array([])

        total_captured_before = float((b_demand * P_before.sum(axis=1)).sum()) if len(existing) else 0.0
        total_captured_after = float((b_demand * P_after.sum(axis=1)).sum())
        new_unmet_captured = max(0.0, total_captured_after - total_captured_before)
        cannibalized_total = max(0.0, injected_visits - new_unmet_captured)

        competitor_impacts: List[Dict[str, Any]] = []
        for idx, s in enumerate(existing):
            vb, va = float(visits_before[idx]), float(visits_after_existing[idx])
            loss = vb - va
            if loss > 0.2:
                competitor_impacts.append({
                    "service_id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
                    "visits_before": round(vb, 1), "visits_after": round(va, 1),
                    "visits_lost": round(loss, 1), "pct_change": round((-loss / max(vb, 1e-6)) * 100.0, 1),
                })
        competitor_impacts.sort(key=lambda x: x["visits_lost"], reverse=True)

        # LAW 3: E2SFCA Equity + Spatial Glow Masks
        def compute_e2sfca(t_mat: np.ndarray, caps: np.ndarray) -> np.ndarray:
            if t_mat.shape[1] == 0:
                return np.zeros(len(blocks), dtype=np.float64)
            cutoff = spec.ideal_walk_min * 2.5
            W = np.where(np.isfinite(t_mat) & (t_mat <= cutoff), np.exp(-((t_mat / spec.ideal_walk_min) ** 2)), 0.0)
            catch_demand = (b_demand[:, None] * W).sum(axis=0)
            R = caps / np.maximum(catch_demand, 1.0)
            return (W * R[None, :]).sum(axis=1)

        acc_before = compute_e2sfca(T_all[:, :-1], all_cap[:-1])
        acc_after = compute_e2sfca(T_all, all_cap)
        eff_weights = b_pop * block_affinity_mult
        equity_before = float(np.sum(eff_weights * np.minimum(acc_before, 1.5)) / max(np.sum(eff_weights), 1.0))
        equity_after = float(np.sum(eff_weights * np.minimum(acc_after, 1.5)) / max(np.sum(eff_weights), 1.0))
        equity_delta = equity_after - equity_before

        min_walk_before = np.min(T_all[:, :-1], axis=1) if len(existing) else np.full(len(blocks), np.inf)
        min_walk_after = np.min(T_all, axis=1)
        unlocked_mask = (min_walk_before > spec.ideal_walk_min) & (min_walk_after <= spec.ideal_walk_min)
        residents_unlocked = int(b_pop[unlocked_mask].sum())

        unlocked_block_ids = [blocks[int(i)]["id"] for i in np.where(unlocked_mask)[0]]
        served_mask = (~unlocked_mask) & (P_after[:, -1] >= 0.25) & (T_all[:, -1] <= spec.ideal_walk_min * 1.5)
        served_block_ids = [blocks[int(i)]["id"] for i in np.where(served_mask)[0]]
        shared_mask = (~unlocked_mask) & (~served_mask) & (P_after[:, -1] >= 0.06) & (T_all[:, -1] <= spec.ideal_walk_min * 1.8)
        shared_block_ids = [blocks[int(i)]["id"] for i in np.where(shared_mask)[0]]

        # LAW 4: Induced Synergy (Hop 3)
        synergy_rules = self.synergies.get(spec.key, [])
        if not synergy_rules and spec.synergy_induces:
            synergy_rules = [{"dst": k, "multiplier": v, "decay_gamma": 0.22} for k, v in spec.synergy_induces.items()]
        walk_from_inj = walk_from_targets[-1]
        hop3_synergies: List[Dict[str, Any]] = []

        for rule in synergy_rules:
            dst_cat = rule["dst"]
            if dst_cat not in SERVICE_CATALOG:
                continue
            mult, gamma = float(rule["multiplier"]), float(rule["decay_gamma"])
            dst_spec = SERVICE_CATALOG[dst_cat]
            induced_visits = injected_visits * mult * 0.65
            nearby_count, spare_cap = 0, 0.0
            for s in services:
                if s["category"] != dst_cat:
                    continue
                t_walk = float(walk_from_inj[self.j_index[s["junction_id"]]]) + inj_snap_w + float(s["snap_walk_min"])
                if math.isfinite(t_walk) and t_walk <= 12.0:
                    weight = math.exp(-gamma * t_walk)
                    nearby_count += 1
                    spare_cap += float(s["capacity"]) * 0.35 * weight
            net_deficit = max(0.0, induced_visits - spare_cap)
            hop3_synergies.append({
                "target_category": dst_cat, "label_en": dst_spec.label_en, "label_ar": dst_spec.label_ar,
                "multiplier": mult, "induced_daily_visits": round(induced_visits, 1),
                "nearby_existing_count": nearby_count, "unmet_synergy_deficit": round(net_deficit, 1),
                "status": "NEW_DEFICIT" if net_deficit > 15.0 else "ABSORBED",
            })
        hop3_synergies.sort(key=lambda x: x["unmet_synergy_deficit"], reverse=True)

        # LAW 5: BPR Congestion
        utilization = injected_visits / eff_capacity
        service_bpr_factor = 1.0 + 0.15 * (utilization ** 4)
        j_cap = max(inc_cap.get(inj_j_idx, 700.0), 300.0)
        street_load_ratio = 0.45 + (injected_visits * 0.18) / j_cap
        street_bpr_factor = 1.0 + 0.15 * (street_load_ratio ** 4)

        # LAW 7: Monte Carlo Uncertainty Envelope
        rng = np.random.default_rng(seed)
        pop_scale = np.clip(rng.normal(1.0, 0.14, size=monte_carlo_runs), 0.65, 1.45)
        beta_mc = np.clip(rng.normal(beta, 0.22, size=monte_carlo_runs), 0.35, 3.8)
        attr_scale = np.clip(rng.normal(1.0, 0.15, size=monte_carlo_runs), 0.60, 1.50)

        mc_visits = np.empty(monte_carlo_runs, dtype=np.float64)
        t_inj, r_inj = T_eff[:, -1], reachable[:, -1]
        u_exist_base = util_before.sum(axis=1)

        for m in range(monte_carlo_runs):
            bm, am, pm = beta_mc[m], attr_scale[m], pop_scale[m]
            u_new = np.where(r_inj, ((eff_attraction * am) ** alpha) * (t_inj ** (-bm)), 0.0)
            ratio_factor = np.where(r_inj, t_inj ** (beta - bm), 1.0)
            p_new = u_new / (u_exist_base * ratio_factor + u_new + u0)
            mc_visits[m] = float(np.sum((b_demand * pm) * p_new))

        p10, p50, p90 = [round(float(x), 1) for x in np.percentile(mc_visits, [10, 50, 90])]
        cannib_ratio = cannibalized_total / max(injected_visits, 1e-6)
        unmet_ratio = new_unmet_captured / max(injected_visits, 1e-6)
        viable_bar = max(10.0, eff_capacity * 0.25)
        healthy_factor = 1.0 - 0.55 * cannib_ratio
        viability_prob = round(float(np.mean((mc_visits * healthy_factor) >= viable_bar)) * 100.0, 1)

        def build_scenario(v: float) -> Dict[str, Any]:
            u = v / eff_capacity
            sl = 0.45 + (v * 0.18) / j_cap
            return {
                "visits": round(v, 1),
                "new_unmet_demand": round(v * unmet_ratio, 1),
                "service_utilization_pct": round(u * 100.0, 1),
                "street_bpr_delay_factor": round(1.0 + 0.15 * (sl ** 4), 3),
                "congestion_alert": u > 0.90 or sl > 0.85,
            }

        is_infra = spec.key in ("clinic", "school", "university")
        svc_overload = max(0.0, utilization - 1.0) * (35.0 if is_infra else 4.0)
        overflow_penalty = svc_overload + max(0.0, street_load_ratio - 0.85) * 30.0
        env_bonus_pts = (env_boost - 1.0) * 28.0
        zoning_penalty = 85.0 if env_eval["is_restricted"] else 0.0
        if env_eval["is_restricted"]:
            viability_prob = 0.0

        gain_score = (
            equity_delta * 100.0
            + (new_unmet_captured / eff_capacity) * 60.0
            + env_bonus_pts
            - cannib_ratio * 25.0
            - overflow_penalty
            - zoning_penalty
        )

        snapped_parcel = self.snap_parcel(lat, lon)
        relate_tx = (
            self.run_whatif_relate_context(snapped_parcel, spec.key, spec.label_en)
            if include_relate_tx
            else {"tx_state": "BATCH_SKIPPED"}
        )

        return {
            "parcel_context": {
                "parcel_id": snapped_parcel["id"] if snapped_parcel else None,
                "land_use": snapped_parcel.get("land_use") if snapped_parcel else None,
                "site_suitability": snapped_parcel.get("site_suitability") if snapped_parcel else None,
                "ownership_status": snapped_parcel.get("ownership_status") if snapped_parcel else None,
                "levels": snapped_parcel.get("levels") if snapped_parcel else None,
                "gfa_m2": snapped_parcel.get("gfa_m2") if snapped_parcel else None,
                "day_pop": snapped_parcel.get("day_pop") if snapped_parcel else None,
                "night_pop": snapped_parcel.get("night_pop") if snapped_parcel else None,
                "dist_to_click_m": snapped_parcel.get("dist_to_click_m") if snapped_parcel else None,
            },
            "relate_transaction": relate_tx,
            "injection": {
                "lat": round(lat, 6), "lon": round(lon, 6),
                "snapped_junction": inj_jid, "snap_m": inj_snap_m,
                "category": spec.key, "label_en": spec.label_en, "label_ar": spec.label_ar,
                "time_of_day": time_of_day, "rhythm_multiplier": rhythm,
                "effective_capacity": round(eff_capacity, 1),
                "attraction_multiplier": round(attraction_multiplier, 2),
            },
            "terrain_and_zoning": {
                "elevation_m": site_elev_m,
                "mean_approach_delta_m": round(dh_mean, 1),
                "slope_walk_friction_pct": round(friction_pct, 1),
                "terrain_verdict_ar": terrain_verdict,
                "terrain_verdict_en": terrain_verdict_en,
                **env_eval,
            },
            "local_demographics": {
                "audience_fit_multiplier": round(local_match_mult, 2),
                "composition_pct": local_demo_dict,
            },
            "hop1_gravity_and_access": {
                "projected_daily_visits": round(injected_visits, 1),
                "new_unmet_demand_captured": round(new_unmet_captured, 1),
                "cannibalized_visits": round(cannibalized_total, 1),
                "cannibalization_pct": round(cannib_ratio * 100.0, 1),
                "residents_unlocked_within_ideal_walk": residents_unlocked,
                "equity_score_before": round(equity_before, 3),
                "equity_score_after": round(equity_after, 3),
                "equity_gain_delta": round(equity_delta, 4),
            },
            "hop2_competitor_ripple": {
                "existing_competitors_in_area": len(existing),
                "impacted_count": len(competitor_impacts),
                "top_impacted": competitor_impacts[:8],
            },
            "hop3_induced_synergy": hop3_synergies,
            "hop4_bpr_congestion": {
                "service_utilization_pct": round(utilization * 100.0, 1),
                "service_bpr_delay_factor": round(service_bpr_factor, 3),
                "street_load_ratio": round(street_load_ratio, 3),
                "street_bpr_delay_factor": round(street_bpr_factor, 3),
                "congestion_alert": utilization > 0.90 or street_load_ratio > 0.85,
            },
            "monte_carlo_envelope": {
                "runs": monte_carlo_runs,
                "p10_conservative": p10, "p50_base": p50, "p90_optimistic": p90,
                "viability_probability_pct": viability_prob,
            },
            "scenarios": {
                "conservative": build_scenario(p10),
                "base": build_scenario(p50),
                "optimistic": build_scenario(p90),
            },
            "spatial_effects": {
                "unlocked_block_ids": unlocked_block_ids,
                "served_block_ids": served_block_ids,
                "shared_block_ids": shared_block_ids,
            },
            "composite_network_gain_J": round(gain_score, 2),
        }

    def optimize_locations(
        self,
        category: Optional[str] = "barber",
        time_of_day: str = "midday",
        top_k: int = 5,
        grid_size: int = 6,
        overrides: Optional[RealityOverrides] = None,
        custom_spec: Optional[ServiceSpec] = None,
    ) -> List[Dict[str, Any]]:
        """Rank real buildable/leasable (:Parcel) sites queried from Relate — never street intersections."""
        spec_key = custom_spec.key if custom_spec is not None else (category or "barber")
        standalone_cats = {"school", "sports", "hospital", "park"}

        elig_rows = self.relate.query(
            "MATCH (p:Parcel)-[:FRONTS_ON]->(j:Junction) "
            "WHERE coalesce(p.env_restricted, false) = false "
            "  AND coalesce(p.ownership_status, '') <> 'BLOCKED_OWNERSHIP' "
            "  AND coalesce(p.site_suitability, '') <> 'restricted_env' "
            "RETURN p.id AS id, p.lat AS lat, p.lon AS lon, p.land_use AS land_use, "
            "       p.site_suitability AS site_suitability, p.ownership_status AS ownership_status, "
            "       p.levels AS levels, p.gfa_m2 AS gfa_m2, j.id AS junction_id",
            tag=f"optimize:eligible_parcels:{spec_key}",
        ).rows
        if not elig_rows:
            return []

        if spec_key in standalone_cats:
            preferred = [p for p in elig_rows if p.get("site_suitability") in ("vacant_buildable", "mixed_ground_floor", "storefront_lease")]
        else:
            preferred = [p for p in elig_rows if p.get("site_suitability") in ("storefront_lease", "mixed_ground_floor", "vacant_buildable")]
        pool = preferred if len(preferred) >= max(top_k, 8) else elig_rows

        p_arr = np.array([[float(p["lat"]), float(p["lon"])] for p in pool], dtype=np.float64)
        p_kd = cKDTree(p_arr)
        lat_bins = np.linspace(p_arr[:, 0].min(), p_arr[:, 0].max(), grid_size + 1)
        lon_bins = np.linspace(p_arr[:, 1].min(), p_arr[:, 1].max(), grid_size + 1)

        candidates: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for i in range(grid_size):
            for k in range(grid_size):
                _, idx = p_kd.query([0.5 * (lat_bins[i] + lat_bins[i + 1]), 0.5 * (lon_bins[k] + lon_bins[k + 1])])
                cand = pool[int(idx)]
                if cand["id"] not in seen_ids:
                    seen_ids.add(cand["id"])
                    candidates.append(cand)

        scored: List[Dict[str, Any]] = []
        for cand in candidates:
            sim = self.simulate_injection(
                float(cand["lat"]),
                float(cand["lon"]),
                category=category,
                custom_spec=custom_spec,
                time_of_day=time_of_day,
                overrides=overrides,
                monte_carlo_runs=60,
                include_relate_tx=False,
            )
            if sim["terrain_and_zoning"]["is_restricted"]:
                continue
            scored.append({
                "parcel_id": cand["id"],
                "junction_id": cand["junction_id"],
                "land_use": cand.get("land_use"),
                "site_suitability": cand.get("site_suitability"),
                "ownership_status": cand.get("ownership_status"),
                "levels": cand.get("levels"),
                "gfa_m2": cand.get("gfa_m2"),
                "lat": round(float(cand["lat"]), 6),
                "lon": round(float(cand["lon"]), 6),
                "gain_J": sim["composite_network_gain_J"],
                "audience_fit": sim["local_demographics"]["audience_fit_multiplier"],
                "env_boost": sim["terrain_and_zoning"]["env_boost_multiplier"],
                "elevation_m": sim["terrain_and_zoning"]["elevation_m"],
                "daily_visits_p50": sim["monte_carlo_envelope"]["p50_base"],
                "new_unmet_demand": sim["hop1_gravity_and_access"]["new_unmet_demand_captured"],
                "cannibalization_pct": sim["hop1_gravity_and_access"]["cannibalization_pct"],
                "residents_unlocked": sim["hop1_gravity_and_access"]["residents_unlocked_within_ideal_walk"],
                "viability_pct": sim["monte_carlo_envelope"]["viability_probability_pct"],
            })

        scored.sort(key=lambda x: x["gain_J"], reverse=True)
        return scored[:top_k]
