"""
Mathematical Verification Suite for Nabd Urban Physics Engine (The 7 Laws).
Validates graph integrity, Huff gravity conservation, E2SFCA equity,
Leontief synergy, BPR non-linear congestion, Monte Carlo ordering,
participatory demographics, custom DNA, and live crisis sandbox overrides.
"""
from pathlib import Path
import pytest

from backend.engine.catalog import build_custom_spec
from backend.engine.physics import (
    DemographicZoneOverride,
    RealityOverrides,
    UrbanGraphEngine,
    haversine_m,
)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "irbid-yarmouk.rl"


@pytest.fixture(scope="module")
def engine() -> UrbanGraphEngine:
    assert DB_PATH.exists(), f"Missing Relate DB at {DB_PATH}"
    import shutil, tempfile
    from pathlib import Path as _Path
    with tempfile.TemporaryDirectory() as td:
        tmp_db = _Path(td) / _Path(DB_PATH).name
        shutil.copy2(DB_PATH, tmp_db)
        with UrbanGraphEngine(tmp_db) as eng:
            yield eng


def test_relate_graph_loaded(engine: UrbanGraphEngine) -> None:
    assert len(engine.junctions) > 500
    assert len(engine.streets) > 1000
    assert len(engine.blocks) > 500
    assert len(engine.services) > 50


def test_law1_topological_illusions(engine: UrbanGraphEngine) -> None:
    res = engine.detect_topological_illusions(category="pharmacy", circuity_threshold=1.6)
    assert res["illusion_count"] > 0
    assert res["mean_circuity"] >= 1.0
    for item in res["illusions"]:
        assert item["network_m"] > item["euclid_m"]
        assert item["circuity_index"] >= 1.6


def test_law2_huff_gravity_and_conservation(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    barber = engine.simulate_injection(lat, lon, category="barber")
    furniture = engine.simulate_injection(lat, lon, category="furniture")

    h1 = barber["hop1_gravity_and_access"]
    assert abs((h1["new_unmet_demand_captured"] + h1["cannibalized_visits"]) - h1["projected_daily_visits"]) <= 0.4
    assert h1["new_unmet_demand_captured"] > furniture["hop1_gravity_and_access"]["new_unmet_demand_captured"]
    assert barber["composite_network_gain_J"] > furniture["composite_network_gain_J"]


def test_law2_saturated_university_cannibalization(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    uni = engine.simulate_injection(lat, lon, category="university")
    assert uni["hop1_gravity_and_access"]["cannibalization_pct"] > 80.0
    assert uni["composite_network_gain_J"] < 0.0


def test_law3_e2sfca_spatial_equity_monotonic(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    res = engine.simulate_injection(lat, lon, category="barber")
    h1 = res["hop1_gravity_and_access"]
    assert h1["equity_score_after"] >= h1["equity_score_before"]
    assert h1["equity_gain_delta"] >= 0.0


def test_law4_leontief_induced_synergy(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    uni = engine.simulate_injection(lat, lon, category="university")
    syn_map = {s["target_category"]: s for s in uni["hop3_induced_synergy"]}
    assert "stationery" in syn_map
    assert syn_map["stationery"]["induced_daily_visits"] > 0.0


def test_law5_bpr_congestion_scales_with_capacity(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    small = engine.simulate_injection(lat, lon, category="barber", capacity_multiplier=0.5)
    large = engine.simulate_injection(lat, lon, category="barber", capacity_multiplier=2.5)
    assert small["hop4_bpr_congestion"]["service_bpr_delay_factor"] >= 1.0
    assert small["hop4_bpr_congestion"]["street_bpr_delay_factor"] >= 1.0
    assert (
        small["hop4_bpr_congestion"]["service_utilization_pct"]
        > large["hop4_bpr_congestion"]["service_utilization_pct"]
    )
    assert (
        small["hop4_bpr_congestion"]["service_bpr_delay_factor"]
        > large["hop4_bpr_congestion"]["service_bpr_delay_factor"]
    )


def test_law6_spatial_optimizer_ranking(engine: UrbanGraphEngine) -> None:
    top = engine.optimize_locations(category="barber", top_k=3, grid_size=4)
    assert len(top) == 3
    assert top[0]["gain_J"] >= top[1]["gain_J"] >= top[2]["gain_J"]
    assert top[0]["gain_J"] > 0.0


def test_law7_monte_carlo_ordering_and_scenarios(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    res = engine.simulate_injection(lat, lon, category="barber", monte_carlo_runs=200)
    mc = res["monte_carlo_envelope"]
    assert mc["p10_conservative"] <= mc["p50_base"] <= mc["p90_optimistic"]
    assert 0.0 <= mc["viability_probability_pct"] <= 100.0
    sc = res["scenarios"]
    assert sc["conservative"]["visits"] <= sc["base"]["visits"] <= sc["optimistic"]["visits"]


def test_participatory_demographic_brush(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    ov_female = RealityOverrides(
        demographic_zones=[DemographicZoneOverride(lat=lat, lon=lon, radius_m=350.0, preset="female_student_housing")]
    )
    ov_male = RealityOverrides(
        demographic_zones=[DemographicZoneOverride(lat=lat, lon=lon, radius_m=350.0, preset="male_student_housing")]
    )
    barber_f = engine.simulate_injection(lat, lon, category="barber", overrides=ov_female)
    barber_m = engine.simulate_injection(lat, lon, category="barber", overrides=ov_male)
    salon_f = engine.simulate_injection(lat, lon, category="beauty_salon", overrides=ov_female)
    salon_m = engine.simulate_injection(lat, lon, category="beauty_salon", overrides=ov_male)

    assert barber_m["local_demographics"]["audience_fit_multiplier"] > barber_f["local_demographics"]["audience_fit_multiplier"]
    assert barber_m["hop1_gravity_and_access"]["projected_daily_visits"] > barber_f["hop1_gravity_and_access"]["projected_daily_visits"]
    assert salon_f["local_demographics"]["audience_fit_multiplier"] > salon_m["local_demographics"]["audience_fit_multiplier"]
    assert salon_f["hop1_gravity_and_access"]["projected_daily_visits"] > salon_m["hop1_gravity_and_access"]["projected_daily_visits"]


def test_live_sandbox_surge_demolition_and_road_closure(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    base = engine.simulate_injection(lat, lon, category="barber")
    base_v = base["hop1_gravity_and_access"]["projected_daily_visits"]

    # 1. Population Surge increases visits
    surge = engine.simulate_injection(
        lat, lon, category="barber",
        overrides=RealityOverrides(extra_population=[{"lat": lat, "lon": lon, "pop": 2500}]),
    )
    assert surge["hop1_gravity_and_access"]["projected_daily_visits"] > base_v

    # 2. Demolishing nearest 25 residential blocks reduces visits
    nearest_ids = [
        b["id"]
        for b in sorted(engine.blocks, key=lambda b: haversine_m(lat, lon, b["lat"], b["lon"]))[:25]
    ]
    demolished = engine.simulate_injection(
        lat, lon, category="barber",
        overrides=RealityOverrides(demolished_blocks=nearest_ids),
    )
    assert demolished["hop1_gravity_and_access"]["projected_daily_visits"] < base_v

    # 3. Road Closure at snapped junction sharply cuts reachable visits
    closed = engine.simulate_injection(
        lat, lon, category="barber",
        overrides=RealityOverrides(closed_points=[{"lat": lat, "lon": lon}]),
    )
    assert closed["hop1_gravity_and_access"]["projected_daily_visits"] < base_v


def test_custom_service_dna_and_city_rhythm(engine: UrbanGraphEngine) -> None:
    lat, lon = engine.meta["center_lat"], engine.meta["center_lon"]
    gaming = build_custom_spec(
        name="Gaming Lounge",
        beta_decay=1.7,
        audience_weights={"students": 0.9, "youth_male": 1.0, "youth_female": 0.1, "families": 0.05, "seniors": 0.0, "commuters": 0.2},
    )
    r_male = engine.simulate_injection(
        lat, lon, custom_spec=gaming,
        overrides=RealityOverrides(demographic_zones=[DemographicZoneOverride(lat=lat, lon=lon, radius_m=350.0, preset="male_student_housing")]),
    )
    r_fam = engine.simulate_injection(
        lat, lon, custom_spec=gaming,
        overrides=RealityOverrides(demographic_zones=[DemographicZoneOverride(lat=lat, lon=lon, radius_m=350.0, preset="family_neighborhood")]),
    )
    assert r_male["local_demographics"]["audience_fit_multiplier"] > r_fam["local_demographics"]["audience_fit_multiplier"]

    # City Rhythm: school is closed at night (0 visits) and active in the morning
    school_night = engine.simulate_injection(lat, lon, category="school", time_of_day="night")
    school_morning = engine.simulate_injection(lat, lon, category="school", time_of_day="morning")
    assert school_night["hop1_gravity_and_access"]["projected_daily_visits"] == 0.0
    assert school_morning["hop1_gravity_and_access"]["projected_daily_visits"] > 0.0
