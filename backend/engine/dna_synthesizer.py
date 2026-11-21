"""
Nabd Universal Facility DNA Synthesizer.
Converts ANY user-entered business or public facility (Arabic or English)
into grounded urban physics parameters (beta, capacity, demand/1k, ideal walk,
6 demographic weights, time-of-day rhythm, OSM competitor category & synergies).
Works locally for free with an extensive urban-economics archetype library,
and optionally enhances unknown niche concepts via any connected LLM provider.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Dict, List, Optional

from backend.engine.catalog import DEMO_AXES, SERVICE_CATALOG

ARCHETYPES: List[Dict[str, Any]] = [
    {
        "keywords": ("شاورما", "برجر", "بيتزا", "مطعم", "مأكولات", "سندويش", "فلافل", "مشاوي", "حلويات", "كنافة", "عصير", "restaurant", "shawarma", "burger", "pizza", "fast food", "diner", "grill", "dessert", "juice", "sushi"),
        "beta_decay": 1.6, "ideal_walk_min": 10.0, "daily_capacity": 160, "demand_per_1k_pop": 45.0,
        "competes_with_category": "cafe",
        "audience_weights": {"students": 0.9, "youth_male": 0.95, "youth_female": 0.85, "families": 0.8, "seniors": 0.3, "commuters": 0.85},
        "time_profile": {"morning": 0.45, "midday": 1.15, "evening": 1.35, "night": 0.9},
        "synergy_induces": {"cafe": 0.25, "pharmacy": 0.08, "grocery": 0.12},
        "rationale_ar": "منشأة طعام وضيافة: طلب يومي مرتفع وذروة مسائية، تتنافس مع المطاعم والمقاهي وتستفيد بقوة من الجوار السياحي والحدائق والجامعات.",
        "rationale_en": "Food & hospitality DNA: high daily turnover with evening peaks, competes with nearby eateries and earns tourism/park/campus boost.",
    },
    {
        "keywords": ("نادي نسائي", "جيم نسائي", "رياضة نساء", "بيلاتس", "يوغا", "women gym", "ladies gym", "pilates", "yoga"),
        "beta_decay": 1.5, "ideal_walk_min": 12.0, "daily_capacity": 95, "demand_per_1k_pop": 22.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.75, "youth_male": 0.0, "youth_female": 1.0, "families": 0.55, "seniors": 0.2, "commuters": 0.2},
        "time_profile": {"morning": 0.85, "midday": 0.75, "evening": 1.25, "night": 0.35},
        "synergy_induces": {"cafe": 0.22, "beauty_salon": 0.2, "pharmacy": 0.1},
        "rationale_ar": "نادي رياضي نسائي: تركيز كامل على الشابات وسكن الطالبات والعائلات مع استعداد أعلى للمشي حتى 12 دقيقة.",
        "rationale_en": "Women's fitness DNA: strongly anchored to young women and student housing with a 12-min catchment tolerance.",
    },
    {
        "keywords": ("نادي رياضي", "جيم", "حديد", "لياقة", "كمال أجسام", "كروسفت", "gym", "fitness", "crossfit", "workout"),
        "beta_decay": 1.45, "ideal_walk_min": 12.0, "daily_capacity": 140, "demand_per_1k_pop": 28.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.85, "youth_male": 1.0, "youth_female": 0.45, "families": 0.25, "seniors": 0.1, "commuters": 0.35},
        "time_profile": {"morning": 0.75, "midday": 0.65, "evening": 1.4, "night": 0.85},
        "synergy_induces": {"cafe": 0.25, "grocery": 0.15, "barber": 0.1},
        "rationale_ar": "نادي لياقة بدنية: ذروة مسائية قوية وتركيز على الشباب والطلاب مع نطاق جذب متوسط.",
        "rationale_en": "Fitness center DNA: strong evening demand driven by young adults and students over a medium walking radius.",
    },
    {
        "keywords": ("بادل", "ملعب", "كرة", "بولينغ", "ترفيه", "ملاهي", "تنس", "padel", "stadium", "pitch", "bowling", "tennis", "arcade", "trampoline"),
        "beta_decay": 0.95, "ideal_walk_min": 18.0, "daily_capacity": 120, "demand_per_1k_pop": 16.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.9, "youth_male": 1.0, "youth_female": 0.55, "families": 0.5, "seniors": 0.05, "commuters": 0.35},
        "time_profile": {"morning": 0.2, "midday": 0.5, "evening": 1.45, "night": 1.25},
        "synergy_induces": {"cafe": 0.4, "grocery": 0.15},
        "rationale_ar": "منشأة رياضية/ترفيهية وجهوية: الزبائن مستعدون لقطع مسافة أطول (β منخفض) مع ذروة مسائية وليلية عالية.",
        "rationale_en": "Destination sports/recreation DNA: low distance decay (customers travel farther) with strong evening & night peaks.",
    },
    {
        "keywords": ("مساحة عمل", "كووركنج", "بيت دراسة", "ستدي هاوس", "قاعة دراسة", "coworking", "study house", "study cafe", "workspace"),
        "beta_decay": 1.35, "ideal_walk_min": 12.0, "daily_capacity": 85, "demand_per_1k_pop": 24.0,
        "competes_with_category": "cafe",
        "audience_weights": {"students": 1.0, "youth_male": 0.85, "youth_female": 0.85, "families": 0.1, "seniors": 0.05, "commuters": 0.6},
        "time_profile": {"morning": 0.95, "midday": 1.3, "evening": 1.15, "night": 0.55},
        "synergy_induces": {"cafe": 0.35, "stationery": 0.3, "bakery": 0.2},
        "rationale_ar": "مساحة عمل/دراسة: تجذب الطلاب والعاملين عن بُعد وتتنافس جزئياً مع المقاهي وتولّد طلباً على القرطاسية والقهوة.",
        "rationale_en": "Coworking / Study Hub DNA: driven by students and remote workers, competes with cafes and induces stationery/coffee demand.",
    },
    {
        "keywords": ("بلايستيشن", "ألعاب", "بلياردو", "سايبر", "إنترنت", "انترنت", "gaming", "playstation", "esports", "billiard", "lan"),
        "beta_decay": 1.65, "ideal_walk_min": 10.0, "daily_capacity": 70, "demand_per_1k_pop": 20.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.95, "youth_male": 1.0, "youth_female": 0.1, "families": 0.05, "seniors": 0.0, "commuters": 0.2},
        "time_profile": {"morning": 0.2, "midday": 0.85, "evening": 1.4, "night": 1.3},
        "synergy_induces": {"cafe": 0.3, "grocery": 0.2},
        "rationale_ar": "صالة ألعاب وترفيه شبابي: تركيز شديد على الطلاب والشباب الذكور خاصة مساءً وليلاً.",
        "rationale_en": "Gaming lounge DNA: heavily anchored to male youth & students with evening/night peaks.",
    },
    {
        "keywords": ("أسنان", "اسنان", "مختبر", "أشعة", "علاج طبيعي", "بصريات", "نظارات", "عيادة", "طبيب", "بيطري", "dental", "dentist", "lab", "physio", "optics", "vet", "veterinary", "clinic"),
        "beta_decay": 1.25, "ideal_walk_min": 14.0, "daily_capacity": 65, "demand_per_1k_pop": 18.0,
        "competes_with_category": "clinic",
        "audience_weights": {"students": 0.5, "youth_male": 0.55, "youth_female": 0.7, "families": 0.95, "seniors": 0.95, "commuters": 0.55},
        "time_profile": {"morning": 1.2, "midday": 1.15, "evening": 0.85, "night": 0.1},
        "synergy_induces": {"pharmacy": 0.45, "cafe": 0.1},
        "rationale_ar": "منشأة صحية وتخصصية: تخدم العائلات وكبار السن على نطاق جغرافي أوسع وتولّد طلباً مباشراً على الصيدليات المجاورة.",
        "rationale_en": "Healthcare / specialty clinic DNA: serves families & seniors across a wide catchment and strongly induces pharmacy visits.",
    },
    {
        "keywords": ("حضانة", "روضة", "أطفال", "مركز تعليمي", "دورات", "لغات", "أكاديمية", "nursery", "daycare", "kindergarten", "academy", "tutoring", "training"),
        "beta_decay": 1.75, "ideal_walk_min": 9.0, "daily_capacity": 90, "demand_per_1k_pop": 20.0,
        "competes_with_category": "school",
        "audience_weights": {"students": 0.45, "youth_male": 0.2, "youth_female": 0.45, "families": 1.0, "seniors": 0.25, "commuters": 0.4},
        "time_profile": {"morning": 1.45, "midday": 1.0, "evening": 0.45, "night": 0.0},
        "synergy_induces": {"stationery": 0.35, "bakery": 0.2, "cafe": 0.15},
        "rationale_ar": "حضانة/مركز تعليمي: تعتمد بشكل حاسم على أحياء العائلات وذروة الصباح وقرب المسافة الآمنة.",
        "rationale_en": "Childcare / training DNA: tightly tied to family neighborhoods, morning peaks, and short safe access.",
    },
    {
        "keywords": ("مغسلة سيارات", "غسيل سيارات", "بناشر", "ميكانيك", "صيانة سيارات", "زيت", "car wash", "auto", "mechanic", "tire", "garage"),
        "beta_decay": 0.95, "ideal_walk_min": 16.0, "daily_capacity": 75, "demand_per_1k_pop": 15.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.35, "youth_male": 0.9, "youth_female": 0.35, "families": 0.75, "seniors": 0.45, "commuters": 1.0},
        "time_profile": {"morning": 0.95, "midday": 1.15, "evening": 1.05, "night": 0.25},
        "synergy_induces": {"cafe": 0.25, "grocery": 0.15},
        "rationale_ar": "خدمات مركبات: تستهدف عابري الطرق الشريانية والشباب والعائلات، وبنطاق جذب واسع للمركبات.",
        "rationale_en": "Automotive service DNA: commuter-driven along arterial roads with wide catchment radius.",
    },
    {
        "keywords": ("دراي كلين", "مغسلة ملابس", "كوي", "خياط", "خياطة", "تصليح أحذية", "laundry", "dry clean", "tailor"),
        "beta_decay": 2.35, "ideal_walk_min": 6.0, "daily_capacity": 85, "demand_per_1k_pop": 26.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.9, "youth_male": 0.85, "youth_female": 0.75, "families": 0.85, "seniors": 0.6, "commuters": 0.45},
        "time_profile": {"morning": 0.85, "midday": 1.05, "evening": 1.2, "night": 0.2},
        "synergy_induces": {"grocery": 0.15, "bakery": 0.1},
        "rationale_ar": "خدمة حيّ يومية (غسيل/خياطة): حساسية عالية جداً للمسافة؛ تنجح وسط الكثافة السكنية وسكن الطلاب.",
        "rationale_en": "Hyper-local neighborhood service DNA: steep distance decay; thrives inside dense housing & student dorms.",
    },
    {
        "keywords": ("موبايل", "هواتف", "خلويات", "كمبيوتر", "إلكترونيات", "الكترونيات", "صيانة", "mobile", "phone", "electronics", "tech", "laptop", "computer"),
        "beta_decay": 1.4, "ideal_walk_min": 12.0, "daily_capacity": 80, "demand_per_1k_pop": 18.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.95, "youth_male": 0.95, "youth_female": 0.8, "families": 0.55, "seniors": 0.25, "commuters": 0.75},
        "time_profile": {"morning": 0.55, "midday": 1.1, "evening": 1.3, "night": 0.45},
        "synergy_induces": {"stationery": 0.2, "cafe": 0.15},
        "rationale_ar": "متجر تقنية وهواتف: طلب مرتفع قرب الجامعات والشوارع التجارية الحيوية وذروة مسائية.",
        "rationale_en": "Tech & mobile retail DNA: high affinity for students, young adults, and commercial corridors.",
    },
    {
        "keywords": ("ملابس", "أزياء", "بوتيك", "عطور", "مكياج", "إكسسوارات", "أحذية", "fashion", "clothing", "boutique", "perfume", "cosmetics", "shoes", "apparel"),
        "beta_decay": 1.25, "ideal_walk_min": 14.0, "daily_capacity": 95, "demand_per_1k_pop": 22.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.8, "youth_male": 0.65, "youth_female": 1.0, "families": 0.75, "seniors": 0.3, "commuters": 0.75},
        "time_profile": {"morning": 0.45, "midday": 1.05, "evening": 1.4, "night": 0.5},
        "synergy_induces": {"cafe": 0.3, "beauty_salon": 0.2},
        "rationale_ar": "تجزئة أزياء وعطور: تجذب المتسوقين من مدى متوسط وذروة مسائية، وتتناغم مع المقاهي وصالونات التجميل.",
        "rationale_en": "Fashion & boutique retail DNA: medium-range destination shopping with evening peaks and cafe/salon synergy.",
    },
    {
        "keywords": ("فندق", "نزل", "شقق فندقية", "منتجع", "هوستل", "hotel", "hostel", "motel", "resort", "inn", "airbnb"),
        "beta_decay": 0.75, "ideal_walk_min": 20.0, "daily_capacity": 110, "demand_per_1k_pop": 10.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.35, "youth_male": 0.6, "youth_female": 0.6, "families": 0.75, "seniors": 0.6, "commuters": 1.0},
        "time_profile": {"morning": 0.9, "midday": 0.85, "evening": 1.2, "night": 1.1},
        "synergy_induces": {"cafe": 0.55, "pharmacy": 0.15, "grocery": 0.25},
        "rationale_ar": "منشأة إيواء وسياحة: تستفيد بقوة من القرب السياحي والمحاور الرئيسية وتولّد حركة قوية للمقاهي والمطاعم.",
        "rationale_en": "Hospitality / Hotel DNA: wide regional pull anchored to commuters & tourism landmarks, heavily boosting nearby food.",
    },
    {
        "keywords": ("حيوانات", "قطط", "كلاب", "أعلاف", "pet", "pet shop", "grooming", "cat"),
        "beta_decay": 1.4, "ideal_walk_min": 12.0, "daily_capacity": 55, "demand_per_1k_pop": 12.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.6, "youth_male": 0.65, "youth_female": 0.85, "families": 0.9, "seniors": 0.55, "commuters": 0.4},
        "time_profile": {"morning": 0.7, "midday": 1.05, "evening": 1.25, "night": 0.2},
        "synergy_induces": {"grocery": 0.12, "cafe": 0.1},
        "rationale_ar": "متجر مستلزمات حيوانات أليفة: يرتكز على أحياء العائلات والشباب في نطاق حيّ متوسط.",
        "rationale_en": "Pet care retail DNA: anchored to family and young-adult residential neighborhoods.",
    },
    {
        "keywords": ("سوبرماركت", "هايبر", "خضار", "فواكه", "ملحمة", "دواجن", "ألبان", "supermarket", "hypermarket", "market", "butcher", "organic", "produce"),
        "beta_decay": 2.1, "ideal_walk_min": 7.0, "daily_capacity": 280, "demand_per_1k_pop": 85.0,
        "competes_with_category": "grocery",
        "audience_weights": {"students": 0.8, "youth_male": 0.75, "youth_female": 0.8, "families": 1.0, "seniors": 0.95, "commuters": 0.55},
        "time_profile": {"morning": 0.95, "midday": 1.05, "evening": 1.3, "night": 0.55},
        "synergy_induces": {"bakery": 0.3, "pharmacy": 0.12},
        "rationale_ar": "تموين يومي وسوبرماركت: طلب مرتفع جداً وحساسية مسافة عالية، يتنافس مباشرة مع البقالات القائمة.",
        "rationale_en": "Daily grocery / market DNA: high-frequency local demand competing directly with existing OSM grocery stores.",
    },
    {
        "keywords": ("زهور", "ورود", "هدايا", "تحف", "flower", "florist", "gift", "souvenir"),
        "beta_decay": 1.5, "ideal_walk_min": 10.0, "daily_capacity": 50, "demand_per_1k_pop": 11.0,
        "competes_with_category": "custom",
        "audience_weights": {"students": 0.65, "youth_male": 0.75, "youth_female": 0.95, "families": 0.8, "seniors": 0.5, "commuters": 0.7},
        "time_profile": {"morning": 0.65, "midday": 1.0, "evening": 1.35, "night": 0.4},
        "synergy_induces": {"cafe": 0.2, "bakery": 0.15},
        "rationale_ar": "محل هدايا وزهور: ينشط مساءً وقرب الجامعات والمستشفيات والشوارع التجارية.",
        "rationale_en": "Florist & gifts DNA: evening & commuter impulse demand near campuses, clinics, and high streets.",
    },
]


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(val)))


def _match_local_archetype(name: str) -> Optional[Dict[str, Any]]:
    low = name.lower()
    best = None
    best_score = 0
    for arch in ARCHETYPES:
        score = sum(len(kw) for kw in arch["keywords"] if kw in low)
        if score > best_score:
            best_score = score
            best = arch
    return best


def _llm_synthesize_dna(
    name: str,
    provider: str,
    api_key: str,
    model: Optional[str],
    custom_base_url: Optional[str],
) -> Optional[Dict[str, Any]]:
    valid_cats = ", ".join(list(SERVICE_CATALOG.keys()) + ["custom"])
    prompt = (
        f"You are an urban economist. Return ONLY valid JSON (no markdown) estimating realistic urban-physics parameters for: '{name}'.\n"
        "JSON schema:\n"
        "{\n"
        '  "beta_decay": float (0.6 destination to 2.8 hyper-local),\n'
        '  "ideal_walk_min": float (5 to 20),\n'
        '  "daily_capacity": int (20 to 600),\n'
        '  "demand_per_1k_pop": float (4 to 100),\n'
        f'  "competes_with_category": one of [{valid_cats}],\n'
        '  "audience_weights": {"students":0..1,"youth_male":0..1,"youth_female":0..1,"families":0..1,"seniors":0..1,"commuters":0..1},\n'
        '  "time_profile": {"morning":0..1.5,"midday":0..1.5,"evening":0..1.5,"night":0..1.5},\n'
        '  "rationale_en": "one concise sentence",\n'
        '  "rationale_ar": "جملة عربية موجزة وواضحة"\n'
        "}"
    )
    p = provider.lower().strip()
    try:
        if p == "gemini":
            m = (model or "gemini-2.5-flash").strip()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key.strip()}"
            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2}}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=18) as resp:
                txt = json.loads(resp.read().decode("utf-8"))["candidates"][0]["content"]["parts"][0]["text"]
        elif p == "anthropic":
            m = (model or "claude-3-5-sonnet-latest").strip()
            payload = {"model": m, "max_tokens": 500, "messages": [{"role": "user", "content": prompt}]}
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-api-key": api_key.strip(), "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=18) as resp:
                txt = json.loads(resp.read().decode("utf-8"))["content"][0]["text"]
        else:
            urls = {
                "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
                "deepseek": ("https://api.deepseek.com/chat/completions", "deepseek-chat"),
                "groq": ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
                "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "google/gemini-2.5-flash"),
            }
            if p in urls:
                url, def_m = urls[p]
                m = (model or def_m).strip()
            elif custom_base_url:
                url = custom_base_url.strip()
                if not url.endswith("/chat/completions"):
                    url = url.rstrip("/") + "/chat/completions"
                m = (model or "llama3.2").strip()
            else:
                return None
            headers = {"Content-Type": "application/json"}
            if api_key.strip():
                headers["Authorization"] = f"Bearer {api_key.strip()}"
            payload = {"model": m, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=18) as resp:
                txt = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]

        match = re.search(r"\{[\s\S]*\}", txt)
        if not match:
            return None
        return json.loads(match.group(0))
    except Exception:
        return None


def synthesize_facility_dna(
    name: str,
    provider: str = "local",
    api_key: str = "",
    model: Optional[str] = None,
    custom_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    clean_name = name.strip() or "Custom Facility"
    raw = None
    source = "archetype"

    if provider != "local" and (api_key.strip() or provider == "custom"):
        raw = _llm_synthesize_dna(clean_name, provider, api_key, model, custom_base_url)
        if raw:
            source = f"llm:{provider}"

    if raw is None:
        arch = _match_local_archetype(clean_name)
        if arch:
            raw = arch
            source = "urban_archetype"
        else:
            raw = {
                "beta_decay": 1.6,
                "ideal_walk_min": 10.0,
                "daily_capacity": 85,
                "demand_per_1k_pop": 22.0,
                "competes_with_category": "custom",
                "audience_weights": {"students": 0.7, "youth_male": 0.7, "youth_female": 0.7, "families": 0.7, "seniors": 0.45, "commuters": 0.55},
                "time_profile": {"morning": 0.75, "midday": 1.1, "evening": 1.2, "night": 0.35},
                "synergy_induces": {"cafe": 0.15, "grocery": 0.1},
                "rationale_ar": "ملف تجاري متوازن افتراضي — يمكنك تعديل المنافسين وشرائح الجمهور أدناه لدقة أعلى.",
                "rationale_en": "Balanced commercial baseline — fine-tune competitor match & audience weights below for precision.",
            }
            source = "general_baseline"

    comp_cat = str(raw.get("competes_with_category", "custom"))
    if comp_cat != "custom" and comp_cat not in SERVICE_CATALOG:
        comp_cat = "custom"

    aud_in = raw.get("audience_weights") or {}
    audience = {ax: round(_clamp(float(aud_in.get(ax, 0.5)), 0.0, 1.0), 2) for ax in DEMO_AXES}

    tp_in = raw.get("time_profile") or {}
    time_profile = {
        k: round(_clamp(float(tp_in.get(k, 1.0)), 0.0, 1.6), 2)
        for k in ("morning", "midday", "evening", "night")
    }

    return {
        "name": clean_name,
        "beta_decay": round(_clamp(float(raw.get("beta_decay", 1.6)), 0.5, 3.0), 2),
        "ideal_walk_min": round(_clamp(float(raw.get("ideal_walk_min", 10.0)), 4.0, 22.0), 1),
        "daily_capacity": int(_clamp(float(raw.get("daily_capacity", 85)), 10, 1500)),
        "demand_per_1k_pop": round(_clamp(float(raw.get("demand_per_1k_pop", 22.0)), 2.0, 150.0), 1),
        "competes_with_category": comp_cat,
        "audience_weights": audience,
        "time_profile": time_profile,
        "synergy_induces": raw.get("synergy_induces") or {"cafe": 0.15},
        "rationale_ar": str(raw.get("rationale_ar", "")),
        "rationale_en": str(raw.get("rationale_en", "")),
        "source": source,
    }
