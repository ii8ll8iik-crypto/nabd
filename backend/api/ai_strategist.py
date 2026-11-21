"""
Nabd Universal Hybrid AI Strategist (Full Bilingual EN / AR).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from backend.engine.catalog import SERVICE_CATALOG
from backend.engine.physics import RealityOverrides, UrbanGraphEngine

CATEGORY_HINTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("beauty_salon", ("صالون", "تجميل", "نسائي", "بنات", "beauty", "salon")),
    ("barber", ("حلاق", "حلاقة", "barber")),
    ("cafe", ("مقهى", "مطعم", "كافيه", "قهوة", "طعام", "أكل", "اكل", "cafe", "coffee", "restaurant", "food")),
    ("bakery", ("مخبز", "خبز", "معجنات", "حلويات", "bakery")),
    ("grocery", ("بقالة", "سوبرماركت", "خضار", "دكان", "grocery", "supermarket")),
    ("pharmacy", ("صيدلية", "دواء", "pharmacy")),
    ("stationery", ("مكتبة", "قرطاسية", "طباعة", "كتب", "stationery", "book", "print")),
    ("furniture", ("سجاد", "أثاث", "اثاث", "مفروشات", "carpet", "furniture")),
    ("clinic", ("عيادة", "طبيب", "مركز صحي", "مستشفى", "clinic", "medical", "doctor")),
    ("school", ("مدرسة", "روضة", "school")),
    ("university", ("جامعة", "كلية", "university", "college")),
]

PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "gemini": {"model": "gemini-2.5-flash"},
    "openai": {"url": "https://api.openai.com/v1/chat/completions", "model": "gpt-4o-mini"},
    "anthropic": {"url": "https://api.anthropic.com/v1/messages", "model": "claude-3-5-sonnet-latest"},
    "deepseek": {"url": "https://api.deepseek.com/chat/completions", "model": "deepseek-chat"},
    "groq": {"url": "https://api.groq.com/openai/v1/chat/completions", "model": "llama-3.3-70b-versatile"},
    "openrouter": {"url": "https://openrouter.ai/api/v1/chat/completions", "model": "google/gemini-2.5-flash"},
}


def _detect_categories(msg: str, fallback: str) -> List[str]:
    low = msg.lower()
    found: List[str] = []
    for cat, kws in CATEGORY_HINTS:
        if any(kw in low for kw in kws):
            found.append(cat)
    return found if found else [fallback if fallback in SERVICE_CATALOG else "barber"]


def _format_local_brief(intent: str, facts: Dict[str, Any], lang: str = "en") -> str:
    is_ar = lang == "ar"

    if intent == "optimize":
        cat_lbl = facts["category_ar"] if is_ar else facts["category_en"]
        top = facts["top_locations"]
        best = facts["best_site_detail"]
        tz = best["terrain_and_zoning"]
        mc = best["monte_carlo_envelope"]
        h1 = best["hop1_gravity_and_access"]
        if is_ar:
            lines = [
                f"تم مسح كامل شبكة الشوارع والتضاريس لإيجاد أفضل مواقع **{cat_lbl}**، ونقلت الكاميرا الآن إلى الموقع #1 رياضياً:",
                f"- **التقييم الشبكي:** `{best['composite_network_gain_J']}` | **احتمال النجاح:** `{mc['viability_probability_pct']}%`",
                f"- **الزيارات اليومية المتوقعة:** `{mc['p50_base']}` زيارة/يوم (نطاق `{mc['p10_conservative']}` ← `{mc['p90_optimistic']}`)",
                f"- **الطلب الجديد الحقيقي:** `+{h1['new_unmet_demand_captured']}` زيارة (تآكل المنافسة `{h1['cannibalization_pct']}%`) مع فكّ عزلة `{h1['residents_unlocked_within_ideal_walk']}` ساكن.",
                f"- **التضاريس والبيئة:** ارتفاع `{tz['elevation_m']}م` ({tz['terrain_verdict_ar']}) | معامل الجوار `{tz['env_boost_multiplier']}x`.",
            ]
            if len(top) >= 3:
                lines.append(f"- **البدائل التالية:** #2 (تقييم `{top[1]['gain_J']}` · `{top[1]['daily_visits_p50']}`/يوم)، #3 (تقييم `{top[2]['gain_J']}` · `{top[2]['daily_visits_p50']}`/يوم).")
            return "\n".join(lines)
        lines = [
            f"Scanned the full street & terrain graph for **{cat_lbl}** — camera moved to the #1 mathematically optimal site:",
            f"- **Network Gain (J):** `{best['composite_network_gain_J']}` | **Viability (200 MC):** `{mc['viability_probability_pct']}%`",
            f"- **Projected Daily Visits (P50):** `{mc['p50_base']}/day` (Conservative `{mc['p10_conservative']}` → Optimistic `{mc['p90_optimistic']}`)",
            f"- **True Unmet Demand:** `+{h1['new_unmet_demand_captured']}` visits (`{h1['cannibalization_pct']}%` cannibalization) · unlocks `{h1['residents_unlocked_within_ideal_walk']}` residents.",
            f"- **Terrain & Environment:** Elevation `{tz['elevation_m']}m` ({tz.get('terrain_verdict_en', '')}) | Proximity boost `{tz['env_boost_multiplier']}x`.",
        ]
        if len(top) >= 3:
            lines.append(f"- **Runner-up Sites:** #2 (`J={top[1]['gain_J']}` · `{top[1]['daily_visits_p50']}`/day), #3 (`J={top[2]['gain_J']}` · `{top[2]['daily_visits_p50']}`/day).")
        return "\n".join(lines)

    if intent == "compare":
        a, b = facts["site_a"], facts["site_b"]
        winner = a if a["composite_network_gain_J"] >= b["composite_network_gain_J"] else b
        if is_ar:
            return "\n".join([
                f"مقارنة رياضية مباشرة على نفس النقطة بين **{a['injection']['label_ar']}** و **{b['injection']['label_ar']}**:",
                f"- **{a['injection']['label_ar']}:** تقييم `{a['composite_network_gain_J']}` | زيارات `{a['monte_carlo_envelope']['p50_base']}`/يوم | نجاح `{a['monte_carlo_envelope']['viability_probability_pct']}%` | تآكل `{a['hop1_gravity_and_access']['cannibalization_pct']}%`.",
                f"- **{b['injection']['label_ar']}:** تقييم `{b['composite_network_gain_J']}` | زيارات `{b['monte_carlo_envelope']['p50_base']}`/يوم | نجاح `{b['monte_carlo_envelope']['viability_probability_pct']}%` | تآكل `{b['hop1_gravity_and_access']['cannibalization_pct']}%`.",
                f"- **الخلاصة الحاسمة:** **{winner['injection']['label_ar']}** يتفوّق رياضياً هنا.",
            ])
        return "\n".join([
            f"Head-to-head 7-Law comparison at this location: **{a['injection']['label_en']}** vs **{b['injection']['label_en']}**:",
            f"- **{a['injection']['label_en']}:** `J={a['composite_network_gain_J']}` | `{a['monte_carlo_envelope']['p50_base']}` visits/day | Viability `{a['monte_carlo_envelope']['viability_probability_pct']}%` | Cannibalization `{a['hop1_gravity_and_access']['cannibalization_pct']}%`.",
            f"- **{b['injection']['label_en']}:** `J={b['composite_network_gain_J']}` | `{b['monte_carlo_envelope']['p50_base']}` visits/day | Viability `{b['monte_carlo_envelope']['viability_probability_pct']}%` | Cannibalization `{b['hop1_gravity_and_access']['cannibalization_pct']}%`.",
            f"- **Verdict:** **{winner['injection']['label_en']}** is mathematically superior at this site.",
        ])

    if intent == "illusions":
        ill = facts["illusions"]
        cat_lbl = facts["category_ar"] if is_ar else facts["category_en"]
        if is_ar:
            lines = [
                f"نتائج **رادار وهم القرب الجغرافي** لخدمة **{cat_lbl}** (تم تفعيل الطبقة الحمراء):",
                f"- عدد المباني المعزولة شبكياً (`>1.6x` التفاف): **`{ill['illusion_count']}`** مبنى (~**`{ill['affected_residents']:,}`** ساكن) · متوسط الالتفاف **`{ill['mean_circuity']}x`**.",
            ]
            if ill["illusions"]:
                w = ill["illusions"][0]
                lines.append(f"- **أسوأ حالة:** مسافة مستقيمة `{w['euclid_m']}م` لكن المشي الفعلي `{w['network_m']}م` (**{w['circuity_index']}x**) لأقرب خدمة ({w['nearest_service']}).")
            return "\n".join(lines)
        lines = [
            f"**Topological Illusion Radar** results for **{cat_lbl}** (red layer enabled on map):",
            f"- Isolated blocks (`>1.6x` street circuity): **`{ill['illusion_count']}`** (~**`{ill['affected_residents']:,}`** residents) · Mean circuity **`{ill['mean_circuity']}x`**.",
        ]
        if ill["illusions"]:
            w = ill["illusions"][0]
            lines.append(f"- **Worst case:** `{w['euclid_m']}m` straight line vs `{w['network_m']}m` real street walk (**{w['circuity_index']}x** detour) to `{w['nearest_service']}`.")
        return "\n".join(lines)

    sim = facts["simulation"]
    tz = sim["terrain_and_zoning"]
    mc = sim["monte_carlo_envelope"]
    h1 = sim["hop1_gravity_and_access"]
    h4 = sim["hop4_bpr_congestion"]
    if is_ar:
        lines = [f"تحليل الجدوى الكامل لمشروع **{sim['injection']['label_ar']}** في موقعك الحالي:"]
        if tz["is_restricted"]:
            lines.append(f"- **تحذير حظر عمراني:** {tz['restricted_reason']} — لا يُنصح بالبناء هنا.")
        lines.extend([
            f"- **التقييم الشبكي:** `{sim['composite_network_gain_J']}` | **احتمال النجاح:** `{mc['viability_probability_pct']}%` | **توافق الجمهور:** `{sim['local_demographics']['audience_fit_multiplier']}x`.",
            f"- **الزيارات اليومية:** متوقع `{mc['p50_base']}` (متحفظ `{mc['p10_conservative']}` ← متفائل `{mc['p90_optimistic']}`).",
            f"- **جودة الطلب:** `+{h1['new_unmet_demand_captured']}` طلب جديد مقابل `{h1['cannibalization_pct']}%` تآكل منافسة، ويفكّ العزلة عن `{h1['residents_unlocked_within_ideal_walk']}` ساكن.",
            f"- **التضاريس والبيئة:** ارتفاع `{tz['elevation_m']}م` · جهد الميل `{tz['slope_walk_friction_pct']}%` ({tz['terrain_verdict_ar']}) · جوار `{tz['env_boost_multiplier']}x`.",
            f"- **الزحام والسعة:** إشغال السعة `{h4['service_utilization_pct']}%` · تأخير الشارع `{h4['street_bpr_delay_factor']}x`.",
        ])
        return "\n".join(lines)

    lines = [f"Full 7-Law Feasibility Brief for **{sim['injection']['label_en']}** at the active pin:"]
    if tz["is_restricted"]:
        lines.append(f"- **Zoning Guardrail Alert:** {tz.get('restricted_reason_en') or tz['restricted_reason']} — site blocked from optimal recommendations.")
    lines.extend([
        f"- **Network Gain (J):** `{sim['composite_network_gain_J']}` | **Viability:** `{mc['viability_probability_pct']}%` | **Audience Fit:** `{sim['local_demographics']['audience_fit_multiplier']}x`.",
        f"- **Daily Visits:** Base `{mc['p50_base']}` (Conservative `{mc['p10_conservative']}` → Optimistic `{mc['p90_optimistic']}`).",
        f"- **Demand Quality:** `+{h1['new_unmet_demand_captured']}` true unmet demand vs `{h1['cannibalization_pct']}%` cannibalization · unlocks `{h1['residents_unlocked_within_ideal_walk']}` residents.",
        f"- **Terrain & Environment:** Elevation `{tz['elevation_m']}m` · slope friction `{tz['slope_walk_friction_pct']}%` ({tz.get('terrain_verdict_en', '')}) · proximity boost `{tz['env_boost_multiplier']}x`.",
        f"- **BPR Congestion:** Capacity load `{h4['service_utilization_pct']}%` · adjacent street delay `{h4['street_bpr_delay_factor']}x`.",
    ])
    gaps = [s for s in sim["hop3_induced_synergy"] if s["status"] == "NEW_DEFICIT"]
    if gaps:
        lines.append(f"- **Hop-3 Induced Opportunity:** Opens a new `+{gaps[0]['unmet_synergy_deficit']}` visit deficit for **{gaps[0]['label_en']}**.")
    return "\n".join(lines)


def _call_external_llm(
    provider: str,
    api_key: str,
    model: Optional[str],
    custom_base_url: Optional[str],
    user_message: str,
    facts: Dict[str, Any],
    history: List[Dict[str, str]],
    lang: str = "en",
) -> str:
    lang_rule = (
        "Respond in crisp, executive Arabic."
        if lang == "ar"
        else "Respond in crisp, executive English."
    )
    sys_prompt = (
        "You are Nabd AI Strategist inside a real 7-Law Urban Physics & Relate Graph engine.\n"
        f"1. {lang_rule}\n"
        "2. Ground EVERY single number strictly in GROUND_TRUTH_PHYSICS below. Never invent statistics.\n"
        "3. Highlight terrain slope impact, zoning restrictions, tourism/park boost, competitor cannibalization, and an actionable verdict."
    )
    grounded_user = (
        f"User Query:\n{user_message}\n\n"
        f"GROUND_TRUTH_PHYSICS:\n{json.dumps(facts, ensure_ascii=False)}"
    )

    p = provider.lower().strip()
    if p == "gemini":
        m = (model or PROVIDER_DEFAULTS["gemini"]["model"]).strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key.strip()}"
        contents = [
            {"role": "model" if h.get("role") == "assistant" else "user", "parts": [{"text": h.get("content", "")}]}
            for h in history[-6:]
        ]
        contents.append({"role": "user", "parts": [{"text": grounded_user}]})
        payload = {
            "system_instruction": {"parts": [{"text": sys_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 900},
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]

    if p == "anthropic":
        m = (model or PROVIDER_DEFAULTS["anthropic"]["model"]).strip()
        msgs = [{"role": h["role"], "content": h["content"]} for h in history[-6:] if h.get("role") in ("user", "assistant")]
        msgs.append({"role": "user", "content": grounded_user})
        payload = {"model": m, "max_tokens": 900, "system": sys_prompt, "messages": msgs}
        req = urllib.request.Request(
            PROVIDER_DEFAULTS["anthropic"]["url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-api-key": api_key.strip(), "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]

    if p in PROVIDER_DEFAULTS:
        url = PROVIDER_DEFAULTS[p]["url"]
        m = (model or PROVIDER_DEFAULTS[p]["model"]).strip()
    else:
        if not custom_base_url:
            raise ValueError("Custom provider requires a base URL.")
        url = custom_base_url.strip()
        if not url.endswith("/chat/completions"):
            url = url.rstrip("/") + "/chat/completions"
        m = (model or "llama3.2").strip()

    msgs = [{"role": "system", "content": sys_prompt}]
    for h in history[-6:]:
        if h.get("role") in ("user", "assistant"):
            msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": grounded_user})

    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    if p == "openrouter":
        headers["HTTP-Referer"] = "http://localhost:5173"
        headers["X-Title"] = "Nabd Urban Physics"

    payload = {"model": m, "messages": msgs, "temperature": 0.35, "max_tokens": 900}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def run_hybrid_strategist(
    eng: UrbanGraphEngine,
    message: str,
    lat: float,
    lon: float,
    active_category: str = "barber",
    time_of_day: str = "midday",
    overrides: Optional[RealityOverrides] = None,
    provider: str = "local",
    api_key: str = "",
    model: Optional[str] = None,
    custom_base_url: Optional[str] = None,
    history: Optional[List[Dict[str, str]]] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    low = message.lower()
    cats = _detect_categories(message, active_category)
    primary_cat = cats[0]
    cat_ar = SERVICE_CATALOG[primary_cat].label_ar
    cat_en = SERVICE_CATALOG[primary_cat].label_en

    map_action: Optional[Dict[str, Any]] = None

    if any(k in low for k in ("أفضل", "افضل", "وين", "أين", "اين", "اقترح", "best", "optimal", "where")):
        intent = "optimize"
        top = eng.optimize_locations(category=primary_cat, time_of_day=time_of_day, top_k=5, overrides=overrides)
        best_lat = top[0]["lat"] if top else lat
        best_lon = top[0]["lon"] if top else lon
        best_detail = eng.simulate_injection(best_lat, best_lon, category=primary_cat, time_of_day=time_of_day, overrides=overrides)
        best_detail.pop("spatial_effects", None)
        facts = {"intent": intent, "category": primary_cat, "category_ar": cat_ar, "category_en": cat_en, "top_locations": top, "best_site_detail": best_detail}
        if top:
            map_action = {"type": "fly_and_inject", "lat": best_lat, "lon": best_lon, "category": primary_cat, "optimal_sites": top}
    elif len(cats) >= 2 and any(k in low for k in ("قارن", "مقابل", "ولا", "أو", "او", "vs", "compare", "or")):
        intent = "compare"
        sim_a = eng.simulate_injection(lat, lon, category=cats[0], time_of_day=time_of_day, overrides=overrides)
        sim_b = eng.simulate_injection(lat, lon, category=cats[1], time_of_day=time_of_day, overrides=overrides)
        sim_a.pop("spatial_effects", None)
        sim_b.pop("spatial_effects", None)
        facts = {"intent": intent, "site_a": sim_a, "site_b": sim_b}
    elif any(k in low for k in ("وهم", "معزول", "التفاف", "رادار", "illusion", "isolated", "circuity")):
        intent = "illusions"
        ill = eng.detect_topological_illusions(category=primary_cat, overrides=overrides)
        ill["illusions"] = ill["illusions"][:8]
        facts = {"intent": intent, "category": primary_cat, "category_ar": cat_ar, "category_en": cat_en, "illusions": ill}
        map_action = {"type": "show_illusions", "category": primary_cat}
    else:
        intent = "analyze"
        sim = eng.simulate_injection(lat, lon, category=primary_cat, time_of_day=time_of_day, overrides=overrides)
        sim.pop("spatial_effects", None)
        facts = {"intent": intent, "category": primary_cat, "category_ar": cat_ar, "category_en": cat_en, "simulation": sim}
        if primary_cat != active_category:
            map_action = {"type": "fly_and_inject", "lat": lat, "lon": lon, "category": primary_cat}

    used_mode = "local"
    warning = None

    if provider != "local" and (api_key.strip() or provider == "custom"):
        try:
            reply = _call_external_llm(
                provider=provider, api_key=api_key, model=model,
                custom_base_url=custom_base_url, user_message=message,
                facts=facts, history=history or [], lang=lang,
            )
            used_mode = f"{provider}:{model or PROVIDER_DEFAULTS.get(provider, {}).get('model', 'custom')}"
        except Exception as exc:
            warning = (
                f"تعذّر الاتصال بنموذج {provider} ({exc}) — تم التحويل للمستشار المحلي."
                if lang == "ar"
                else f"External provider '{provider}' failed ({exc}) — fell back to built-in local strategist."
            )
            reply = _format_local_brief(intent, facts, lang)
    else:
        reply = _format_local_brief(intent, facts, lang)

    return {"reply": reply, "engine_mode": used_mode, "intent": intent, "warning": warning, "map_action": map_action}
