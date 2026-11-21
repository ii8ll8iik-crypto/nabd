"""
Universal Urban Service Physics (Laws Layer) + Demographic Affinity DNA.
Every urban activity—preset or user-invented—is defined by:
  - Spatial physics (beta_decay, alpha_attraction, outside_option, daily_capacity)
  - Target audience vector w_s over 6 demographic axes
  - Multi-hop Leontief synergy multipliers & Time-of-Day rhythm
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple

DEMO_AXES: Tuple[str, ...] = (
    "students",
    "youth_male",
    "youth_female",
    "families",
    "seniors",
    "commuters",
)

# Neutral baseline urban composition (sums to 1.0)
BASELINE_DEMO: Dict[str, float] = {
    "students": 0.12,
    "youth_male": 0.16,
    "youth_female": 0.16,
    "families": 0.36,
    "seniors": 0.10,
    "commuters": 0.10,
}

# Ready-to-paint Local Ground-Truth Presets (for participatory map overrides)
DEMO_ZONE_PRESETS: Dict[str, Dict[str, float]] = {
    "female_student_housing": {
        "students": 0.42, "youth_male": 0.03, "youth_female": 0.45,
        "families": 0.05, "seniors": 0.01, "commuters": 0.04,
    },
    "male_student_housing": {
        "students": 0.42, "youth_male": 0.45, "youth_female": 0.03,
        "families": 0.05, "seniors": 0.01, "commuters": 0.04,
    },
    "family_neighborhood": {
        "students": 0.08, "youth_male": 0.12, "youth_female": 0.12,
        "families": 0.52, "seniors": 0.12, "commuters": 0.04,
    },
    "youth_commercial_hub": {
        "students": 0.25, "youth_male": 0.26, "youth_female": 0.22,
        "families": 0.08, "seniors": 0.02, "commuters": 0.17,
    },
    "senior_quiet_district": {
        "students": 0.05, "youth_male": 0.08, "youth_female": 0.08,
        "families": 0.36, "seniors": 0.38, "commuters": 0.05,
    },
}


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    label_en: str
    label_ar: str
    beta_decay: float
    alpha_attraction: float
    base_attraction: float
    outside_option: float
    ideal_walk_min: float
    daily_capacity: int
    demand_per_1k_pop: float
    audience_weights: Dict[str, float] = field(default_factory=dict)  # w_s over DEMO_AXES
    synergy_induces: Dict[str, float] = field(default_factory=dict)
    time_profile: Dict[str, float] = field(default_factory=dict)
    osm_matchers: Tuple[Tuple[str, str], ...] = ()


SERVICE_CATALOG: Dict[str, ServiceSpec] = {
    "barber": ServiceSpec(
        key="barber",
        label_en="Men's Barber",
        label_ar="محل حلاقة رجالي",
        beta_decay=2.6,
        alpha_attraction=0.70,
        base_attraction=1.0,
        outside_option=0.012,
        ideal_walk_min=8.0,
        daily_capacity=35,
        demand_per_1k_pop=22.0,
        audience_weights={
            "students": 0.35, "youth_male": 1.00, "youth_female": 0.02,
            "families": 0.30, "seniors": 0.25, "commuters": 0.15,
        },
        synergy_induces={"cafe": 0.15, "grocery": 0.10},
        time_profile={"morning": 0.6, "midday": 1.1, "evening": 1.5, "night": 0.5},
        osm_matchers=(("shop", "hairdresser"),),
    ),
    "beauty_salon": ServiceSpec(
        key="beauty_salon",
        label_en="Women's Beauty Salon",
        label_ar="صالون تجميل نسائي",
        beta_decay=2.1,
        alpha_attraction=1.05,
        base_attraction=1.2,
        outside_option=0.018,
        ideal_walk_min=10.0,
        daily_capacity=28,
        demand_per_1k_pop=18.0,
        audience_weights={
            "students": 0.35, "youth_male": 0.01, "youth_female": 1.00,
            "families": 0.40, "seniors": 0.15, "commuters": 0.10,
        },
        synergy_induces={"cafe": 0.20, "pharmacy": 0.10},
        time_profile={"morning": 0.7, "midday": 1.3, "evening": 1.4, "night": 0.3},
        osm_matchers=(("shop", "beauty"),),
    ),
    "bakery": ServiceSpec(
        key="bakery",
        label_en="Bakery",
        label_ar="مخبز",
        beta_decay=2.8,
        alpha_attraction=0.80,
        base_attraction=1.2,
        outside_option=0.015,
        ideal_walk_min=7.0,
        daily_capacity=320,
        demand_per_1k_pop=170.0,
        audience_weights={
            "students": 0.50, "youth_male": 0.45, "youth_female": 0.45,
            "families": 1.00, "seniors": 0.75, "commuters": 0.55,
        },
        synergy_induces={"grocery": 0.25, "cafe": 0.15},
        time_profile={"morning": 1.8, "midday": 1.0, "evening": 0.9, "night": 0.2},
        osm_matchers=(("shop", "bakery"),),
    ),
    "grocery": ServiceSpec(
        key="grocery",
        label_en="Grocery / Produce",
        label_ar="بقالة / خضار",
        beta_decay=2.7,
        alpha_attraction=0.85,
        base_attraction=1.3,
        outside_option=0.014,
        ideal_walk_min=7.0,
        daily_capacity=280,
        demand_per_1k_pop=200.0,
        audience_weights={
            "students": 0.55, "youth_male": 0.45, "youth_female": 0.50,
            "families": 1.00, "seniors": 0.80, "commuters": 0.35,
        },
        synergy_induces={"bakery": 0.20, "pharmacy": 0.10},
        time_profile={"morning": 0.9, "midday": 1.1, "evening": 1.4, "night": 0.6},
        osm_matchers=(
            ("shop", "convenience"),
            ("shop", "supermarket"),
            ("shop", "greengrocer"),
        ),
    ),
    "pharmacy": ServiceSpec(
        key="pharmacy",
        label_en="Pharmacy",
        label_ar="صيدلية",
        beta_decay=2.4,
        alpha_attraction=0.90,
        base_attraction=1.5,
        outside_option=0.010,
        ideal_walk_min=9.0,
        daily_capacity=190,
        demand_per_1k_pop=55.0,
        audience_weights={
            "students": 0.35, "youth_male": 0.30, "youth_female": 0.55,
            "families": 0.85, "seniors": 1.00, "commuters": 0.40,
        },
        synergy_induces={"clinic": 0.20},
        time_profile={"morning": 0.9, "midday": 1.2, "evening": 1.2, "night": 0.7},
        osm_matchers=(("amenity", "pharmacy"),),
    ),
    "cafe": ServiceSpec(
        key="cafe",
        label_en="Cafe / Restaurant",
        label_ar="مقهى / مطعم",
        beta_decay=1.9,
        alpha_attraction=1.15,
        base_attraction=1.6,
        outside_option=0.025,
        ideal_walk_min=12.0,
        daily_capacity=160,
        demand_per_1k_pop=75.0,
        audience_weights={
            "students": 1.00, "youth_male": 0.85, "youth_female": 0.75,
            "families": 0.35, "seniors": 0.15, "commuters": 0.80,
        },
        synergy_induces={"bakery": 0.15, "stationery": 0.10},
        time_profile={"morning": 0.7, "midday": 1.2, "evening": 1.7, "night": 1.2},
        osm_matchers=(
            ("amenity", "cafe"),
            ("amenity", "restaurant"),
            ("amenity", "fast_food"),
        ),
    ),
    "stationery": ServiceSpec(
        key="stationery",
        label_en="Stationery / Print",
        label_ar="مكتبة / قرطاسية",
        beta_decay=2.1,
        alpha_attraction=0.90,
        base_attraction=1.1,
        outside_option=0.020,
        ideal_walk_min=10.0,
        daily_capacity=120,
        demand_per_1k_pop=25.0,
        audience_weights={
            "students": 1.00, "youth_male": 0.45, "youth_female": 0.50,
            "families": 0.45, "seniors": 0.05, "commuters": 0.20,
        },
        synergy_induces={"cafe": 0.15},
        time_profile={"morning": 1.3, "midday": 1.4, "evening": 0.8, "night": 0.1},
        osm_matchers=(
            ("shop", "stationery"),
            ("shop", "books"),
            ("shop", "copyshop"),
        ),
    ),
    "furniture": ServiceSpec(
        key="furniture",
        label_en="Carpet / Furniture",
        label_ar="سجاد / أثاث",
        beta_decay=0.85,
        alpha_attraction=1.65,
        base_attraction=2.2,
        outside_option=0.350,
        ideal_walk_min=30.0,
        daily_capacity=30,
        demand_per_1k_pop=1.6,
        audience_weights={
            "students": 0.05, "youth_male": 0.15, "youth_female": 0.20,
            "families": 1.00, "seniors": 0.45, "commuters": 0.25,
        },
        synergy_induces={"cafe": 0.10},
        time_profile={"morning": 0.5, "midday": 1.1, "evening": 1.5, "night": 0.2},
        osm_matchers=(
            ("shop", "carpet"),
            ("shop", "furniture"),
            ("shop", "interior_decoration"),
        ),
    ),
    "clinic": ServiceSpec(
        key="clinic",
        label_en="Medical Clinic",
        label_ar="عيادة / مركز صحي",
        beta_decay=1.6,
        alpha_attraction=1.35,
        base_attraction=2.8,
        outside_option=0.018,
        ideal_walk_min=15.0,
        daily_capacity=220,
        demand_per_1k_pop=35.0,
        audience_weights={
            "students": 0.30, "youth_male": 0.25, "youth_female": 0.45,
            "families": 0.85, "seniors": 1.00, "commuters": 0.25,
        },
        synergy_induces={"pharmacy": 0.85, "cafe": 0.25, "grocery": 0.15},
        time_profile={"morning": 1.4, "midday": 1.3, "evening": 0.9, "night": 0.4},
        osm_matchers=(
            ("amenity", "clinic"),
            ("amenity", "doctors"),
            ("amenity", "hospital"),
        ),
    ),
    "school": ServiceSpec(
        key="school",
        label_en="School",
        label_ar="مدرسة",
        beta_decay=1.8,
        alpha_attraction=1.20,
        base_attraction=3.5,
        outside_option=0.015,
        ideal_walk_min=14.0,
        daily_capacity=800,
        demand_per_1k_pop=95.0,
        audience_weights={
            "students": 0.20, "youth_male": 0.10, "youth_female": 0.10,
            "families": 1.00, "seniors": 0.05, "commuters": 0.05,
        },
        synergy_induces={"stationery": 0.90, "bakery": 0.45, "grocery": 0.40},
        time_profile={"morning": 2.0, "midday": 1.4, "evening": 0.1, "night": 0.0},
        osm_matchers=(("amenity", "school"), ("amenity", "kindergarten")),
    ),
    "university": ServiceSpec(
        key="university",
        label_en="University / Campus",
        label_ar="جامعة / كلية",
        beta_decay=0.65,
        alpha_attraction=1.80,
        base_attraction=8.0,
        outside_option=0.080,
        ideal_walk_min=35.0,
        daily_capacity=5000,
        demand_per_1k_pop=40.0,
        audience_weights={
            "students": 1.00, "youth_male": 0.70, "youth_female": 0.70,
            "families": 0.10, "seniors": 0.02, "commuters": 0.40,
        },
        synergy_induces={
            "cafe": 1.40,
            "stationery": 1.30,
            "grocery": 0.80,
            "pharmacy": 0.60,
            "barber": 0.55,
            "beauty_salon": 0.45,
            "clinic": 0.50,
        },
        time_profile={"morning": 1.6, "midday": 1.8, "evening": 0.7, "night": 0.1},
        osm_matchers=(("amenity", "university"), ("amenity", "college")),
    ),
}


def build_custom_spec(
    name: str,
    beta_decay: float = 2.0,
    alpha_attraction: float = 1.0,
    daily_capacity: int = 80,
    demand_per_1k_pop: float = 25.0,
    ideal_walk_min: float = 10.0,
    audience_weights: Dict[str, float] | None = None,
    competes_with_category: str = "custom",
) -> ServiceSpec:
    """Create a live ServiceSpec on the fly for ANY business not in the preset catalog."""
    aw = {ax: 0.5 for ax in DEMO_AXES}
    if audience_weights:
        for k, v in audience_weights.items():
            if k in aw:
                aw[k] = max(0.0, float(v))
    return ServiceSpec(
        key=competes_with_category,
        label_en=name,
        label_ar=name,
        beta_decay=beta_decay,
        alpha_attraction=alpha_attraction,
        base_attraction=1.3,
        outside_option=0.02,
        ideal_walk_min=ideal_walk_min,
        daily_capacity=daily_capacity,
        demand_per_1k_pop=demand_per_1k_pop,
        audience_weights=aw,
        synergy_induces={"cafe": 0.15},
        time_profile={"morning": 0.8, "midday": 1.1, "evening": 1.3, "night": 0.4},
    )


def classify_osm_tags(tags: Dict[str, str]) -> str | None:
    for key, spec in SERVICE_CATALOG.items():
        for tag_k, tag_v in spec.osm_matchers:
            if tags.get(tag_k) == tag_v:
                return key
    return None
