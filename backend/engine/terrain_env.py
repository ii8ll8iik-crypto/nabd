"""
Nabd Terrain Elevation (Tobler's Asymmetric Hiking Slope Physics)
+ Environmental, Water, Park, Recreation, Tourism & Land-Use Zoning Layer.
"""
from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw"

OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
)

RESTRICTED_ZONES = {"water", "wetland", "park", "cemetery"}
ZONE_EN_LABELS = {
    "water": "Water Body / Wadi",
    "wetland": "Wetland / Marsh",
    "park": "Public Park / Green Reserve",
    "cemetery": "Cemetery",
    "tourism": "Tourism & Historic Landmark",
    "recreation": "Sports & Recreation Hub",
    "industrial": "Industrial Zone",
}
DRIVER_EN_TITLES = {
    "tourism": "Tourism & Historic Proximity",
    "park": "Park & Green Space Proximity",
    "water": "Waterfront Proximity",
    "recreation": "Sports & Recreation Hub",
    "university": "University Campus Hub",
    "school": "School Corridor",
    "industrial": "Adjacent Industrial Zone",
}
FOOD_CATEGORIES = {"cafe", "bakery", "grocery"}
FOOD_KEYWORDS = ("طعام", "مطعم", "مقهى", "كافيه", "قهوة", "مخبز", "عصير", "حلويات", "food", "cafe", "restaurant", "coffee", "bakery", "burger", "pizza")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def tobler_speed_ratio(slope: float) -> float:
    """
    Asymmetric Tobler's Hiking Function normalized to flat ground (slope=0 -> 1.0):
    - Gentle downhill (-5%): ~1.19x faster
    - Uphill (+8%): ~0.75x slower (~32% longer walk time)
    - Steep uphill (+15%): ~0.59x slower (~69% longer walk time)
    """
    s = max(-0.35, min(0.35, float(slope)))
    return math.exp(-3.5 * (abs(s + 0.05) - 0.05))


def _fetch_elevation_batch(coords: List[Tuple[str, float, float]]) -> Dict[str, float]:
    lats = ",".join(f"{lat:.5f}" for _, lat, _ in coords)
    lons = ",".join(f"{lon:.5f}" for _, _, lon in coords)
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
    req = urllib.request.Request(url, headers={"User-Agent": "NabdUrbanPhysics/2.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elevs = data.get("elevation", [])
    out: Dict[str, float] = {}
    for idx, (jid, _, _) in enumerate(coords):
        if idx < len(elevs) and elevs[idx] is not None:
            out[jid] = round(float(elevs[idx]), 1)
    return out


def load_or_fetch_elevations(slug: str, junctions: List[Dict[str, Any]]) -> Dict[str, float]:
    """Fetch real DEM elevation (meters) for every Relate junction and cache permanently."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{slug}.elev.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and len(cached) >= len(junctions) * 0.8:
                return {str(k): float(v) for k, v in cached.items()}
        except Exception:
            pass

    if not junctions:
        return {}

    coords = [(j["id"], float(j["lat"]), float(j["lon"])) for j in junctions]
    batch_size = 100
    batches = [coords[i : i + batch_size] for i in range(0, len(coords), batch_size)]

    elev_map: Dict[str, float] = {}
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            for res in pool.map(_fetch_elevation_batch, batches):
                elev_map.update(res)
    except Exception:
        pass

    if elev_map:
        cache_path.write_text(json.dumps(elev_map), encoding="utf-8")
    return elev_map


def _classify_env_tags(tags: Dict[str, str]) -> Optional[Tuple[str, str, bool]]:
    """Return (zone_type, arabic_label, is_restricted)."""
    nat = tags.get("natural", "")
    leis = tags.get("leisure", "")
    lu = tags.get("landuse", "")
    tour = tags.get("tourism", "")
    ww = tags.get("waterway", "")
    hist = tags.get("historic", "")

    if nat == "wetland":
        return ("wetland", "مستنقع / أرض رطبة", True)
    if nat == "water" or lu in ("reservoir", "basin") or ww in ("river", "stream", "canal", "wadi", "riverbank"):
        return ("water", "مسطح مائي / وادي", True)
    if lu == "cemetery" or tags.get("amenity") == "grave_yard":
        return ("cemetery", "مقبرة", True)
    if tour in ("attraction", "museum", "viewpoint", "gallery", "theme_park", "hotel", "artwork") or hist:
        return ("tourism", "معلم سياحي / تاريخي", False)
    if leis in ("park", "garden", "nature_reserve") or nat == "wood" or lu in ("forest", "meadow", "village_green"):
        return ("park", "حديقة / مساحة خضراء", True)
    if leis in ("stadium", "pitch", "sports_centre", "playground", "water_park", "amusement_arcade", "fitness_centre"):
        return ("recreation", "منشأة رياضية / ترفيهية", False)
    if lu in ("industrial", "quarry", "landfill"):
        return ("industrial", "منطقة صناعية", False)
    return None


def load_or_fetch_env_zones(
    slug: str, center_lat: float, center_lon: float, radius_m: float
) -> List[Dict[str, Any]]:
    """Fetch Parks, Water, Wetlands, Recreation, Tourism, and Industrial zones from OSM and cache."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DIR / f"{slug}.env.json"
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    r = int(max(300, min(radius_m + 150, 2800)))
    query = f"""
    [out:json][timeout:10];
    (
      nwr["natural"~"^(water|wetland|wood)$"](around:{r},{center_lat},{center_lon});
      nwr["waterway"~"^(river|stream|canal|wadi)$"](around:{r},{center_lat},{center_lon});
      nwr["leisure"~"^(park|garden|nature_reserve|stadium|pitch|sports_centre|playground|water_park|amusement_arcade)$"](around:{r},{center_lat},{center_lon});
      nwr["tourism"~"^(attraction|museum|viewpoint|gallery|theme_park|hotel)$"](around:{r},{center_lat},{center_lon});
      nwr["historic"](around:{r},{center_lat},{center_lon});
      nwr["landuse"~"^(industrial|cemetery|forest|reservoir|basin|meadow)$"](around:{r},{center_lat},{center_lon});
    );
    out body;
    >;
    out skel qt;
    """

    raw_osm: Optional[Dict[str, Any]] = None
    for mirror in OVERPASS_MIRRORS:
        try:
            body = urllib.parse.urlencode({"data": query}).encode("utf-8")
            req = urllib.request.Request(mirror, data=body, headers={"User-Agent": "NabdUrbanPhysics/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_osm = json.loads(resp.read().decode("utf-8"))
            break
        except Exception:
            continue

    if not raw_osm:
        return []

    nodes: Dict[int, Tuple[float, float]] = {}
    for el in raw_osm.get("elements", []):
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            nodes[el["id"]] = (float(el["lat"]), float(el["lon"]))

    zones: List[Dict[str, Any]] = []
    for el in raw_osm.get("elements", []):
        tags = el.get("tags") or {}
        if not tags:
            continue
        cls = _classify_env_tags(tags)
        if not cls:
            continue
        ztype, label_ar, is_restricted = cls
        name = tags.get("name:ar") or tags.get("name") or label_ar

        if el["type"] == "node" and "lat" in el:
            lat, lon = float(el["lat"]), float(el["lon"])
            zones.append({
                "id": f"env_n_{el['id']}",
                "name": name,
                "zone_type": ztype,
                "label_ar": label_ar,
                "is_restricted": is_restricted,
                "geom_type": "Point",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "coordinates": [lon, lat],
            })
        elif el["type"] == "way":
            pts = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
            if len(pts) < 2:
                continue
            clat = sum(p[0] for p in pts) / len(pts)
            clon = sum(p[1] for p in pts) / len(pts)
            is_poly = len(pts) >= 3 and (pts[0] == pts[-1] or ztype in ("park", "water", "wetland", "recreation", "industrial", "cemetery"))
            if is_poly:
                ring = [[p[1], p[0]] for p in pts]
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                zones.append({
                    "id": f"env_w_{el['id']}",
                    "name": name,
                    "zone_type": ztype,
                    "label_ar": label_ar,
                    "is_restricted": is_restricted,
                    "geom_type": "Polygon",
                    "lat": round(clat, 6),
                    "lon": round(clon, 6),
                    "coordinates": [ring],
                })
            else:
                zones.append({
                    "id": f"env_l_{el['id']}",
                    "name": name,
                    "zone_type": ztype,
                    "label_ar": label_ar,
                    "is_restricted": is_restricted,
                    "geom_type": "LineString",
                    "lat": round(clat, 6),
                    "lon": round(clon, 6),
                    "coordinates": [[p[1], p[0]] for p in pts],
                })

    cache_path.write_text(json.dumps(zones, ensure_ascii=False), encoding="utf-8")
    return zones


def _point_in_ring(lon: float, lat: float, ring: List[List[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def evaluate_site_environment(
    lat: float,
    lon: float,
    category: str,
    label_text: str,
    env_zones: List[Dict[str, Any]],
    services: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate:
    1) Zoning Guardrail (is the point inside water/wetland/park/cemetery?)
    2) Investment & Foot-Traffic Boost near parks, water, tourism, recreation, universities & schools
       (with amplified bonus for Food & Hospitality businesses near tourism/recreation/parks).
    """
    txt_low = (category + " " + label_text).lower()
    is_food = category in FOOD_CATEGORIES or any(k in txt_low for k in FOOD_KEYWORDS)

    restricted_hit: Optional[Dict[str, Any]] = None
    nearest: Dict[str, Tuple[float, str]] = {}

    for z in env_zones:
        ztype = z["zone_type"]
        if z["geom_type"] == "Polygon" and z["is_restricted"]:
            if _point_in_ring(lon, lat, z["coordinates"][0]):
                restricted_hit = z

        d = haversine_m(lat, lon, float(z["lat"]), float(z["lon"]))
        if z["geom_type"] == "Polygon":
            # Also check vertices for large parks/waterfronts so edge proximity is accurate
            for vx, vy in z["coordinates"][0][::max(1, len(z["coordinates"][0]) // 12)]:
                dv = haversine_m(lat, lon, vy, vx)
                if dv < d:
                    d = dv
        if ztype not in nearest or d < nearest[ztype][0]:
            nearest[ztype] = (d, z["name"])

    # Also measure proximity to universities & schools from Relate services
    for s in services:
        sc = s["category"]
        if sc in ("university", "school"):
            d = haversine_m(lat, lon, float(s["lat"]), float(s["lon"]))
            if sc not in nearest or d < nearest[sc][0]:
                nearest[sc] = (d, s["name"])

    boost = 1.0
    drivers: List[Dict[str, Any]] = []

    def apply_driver(key: str, max_dist: float, food_bonus: float, std_bonus: float, title_ar: str) -> None:
        nonlocal boost
        if key not in nearest:
            return
        dist_m, name = nearest[key]
        if dist_m <= max_dist:
            decay = 1.0 - 0.55 * (dist_m / max_dist)
            delta = (food_bonus if is_food else std_bonus) * decay
            boost += delta
            drivers.append({
                "type": key,
                "name": name,
                "title_ar": title_ar,
                "title_en": DRIVER_EN_TITLES.get(key, key),
                "distance_m": round(dist_m),
                "effect_pct": round(delta * 100.0, 1),
            })

    apply_driver("tourism", 300.0, 0.28, 0.12, "جوار سياحي وتاريخي")
    apply_driver("park", 220.0, 0.20, 0.09, "جوار حديقة / مساحة خضراء")
    apply_driver("water", 220.0, 0.18, 0.08, "إطلالة / قرب مائي")
    apply_driver("recreation", 260.0, 0.22, 0.11, "جوار ملاعب ومنشآت ترفيهية")
    apply_driver("university", 350.0, 0.18, 0.10, "محيط جامعي حيوي")
    apply_driver("school", 240.0, 0.12, 0.07, "جوار مدارس وحركة طلابية")

    if "industrial" in nearest and nearest["industrial"][0] <= 220.0:
        dist_m, name = nearest["industrial"]
        pen = -0.18 if (is_food or category in ("clinic", "school", "beauty_salon")) else -0.08
        boost += pen
        drivers.append({
            "type": "industrial",
            "name": name,
            "title_ar": "تأثير منطقة صناعية مجاورة",
            "title_en": "Adjacent Industrial Zone",
            "distance_m": round(dist_m),
            "effect_pct": round(pen * 100.0, 1),
        })

    boost = max(0.72, min(1.55, boost))
    drivers.sort(key=lambda x: abs(x["effect_pct"]), reverse=True)

    return {
        "is_restricted": restricted_hit is not None,
        "restricted_reason": (
            f"منطقة محظورة للبناء: {restricted_hit['label_ar']} ({restricted_hit['name']})"
            if restricted_hit
            else None
        ),
        "restricted_reason_en": (
            f"Restricted Zoning: {ZONE_EN_LABELS.get(restricted_hit['zone_type'], restricted_hit['zone_type'])} ({restricted_hit['name']})"
            if restricted_hit
            else None
        ),
        "is_food_or_hospitality": is_food,
        "env_boost_multiplier": round(boost, 3),
        "proximity_drivers": drivers[:5],
    }


def env_zones_to_geojson(env_zones: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for z in env_zones:
        features.append({
            "type": "Feature",
            "geometry": {"type": z["geom_type"], "coordinates": z["coordinates"]},
            "properties": {
                "id": z["id"],
                "name": z["name"],
                "zone_type": z["zone_type"],
                "label_ar": z["label_ar"],
                "label_en": ZONE_EN_LABELS.get(z["zone_type"], z["zone_type"]),
                "is_restricted": z["is_restricted"],
            },
        })
    return {"type": "FeatureCollection", "features": features}
