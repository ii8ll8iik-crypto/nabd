import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bookmark,
  Building2,
  CheckCircle2,
  Database,
  GitCompare,
  Layers,
  Moon,
  Mountain,
  ShieldAlert,
  Sun,
  Terminal,
  Trees,
  X,
} from "lucide-react";
import { AXIS_LABELS_I18N } from "../i18n";
import type { Lang, PinnedSite, ScenarioKey, SimulationResponse } from "../types";

interface Props {
  lang: Lang;
  open: boolean;
  onClose: () => void;
  simResult: SimulationResponse | null;
  scenario: ScenarioKey;
  onChangeScenario: (s: ScenarioKey) => void;
  pinnedA: PinnedSite | null;
  onPinCurrentAsA: () => void;
  onClearPinA: () => void;
  errorText: string | null;
  onCommitDecision?: (
    status: "APPROVED" | "REJECTED" | "WATCHLIST",
    reason: string,
    blockOwnership: boolean
  ) => Promise<void> | void;
  decisionBusy?: boolean;
  decisionFeedback?: string | null;
  onOpenRelateTrace?: () => void;
}

export function TelemetryDrawer({
  lang,
  open,
  onClose,
  simResult,
  scenario,
  onChangeScenario,
  pinnedA,
  onPinCurrentAsA,
  onClearPinA,
  errorText,
  onCommitDecision,
  decisionBusy = false,
  decisionFeedback = null,
  onOpenRelateTrace,
}: Props) {
  const isAr = lang === "ar";
  const [tab, setTab] = useState<"summary" | "ripples" | "compare">("summary");
  const [decisionNote, setDecisionNote] = useState("");

  const activeScenario = simResult?.scenarios?.[scenario] ?? {
    visits: simResult?.monte_carlo_envelope.p50_base ?? 0,
    new_unmet_demand: simResult?.hop1_gravity_and_access.new_unmet_demand_captured ?? 0,
    service_utilization_pct: simResult?.hop4_bpr_congestion.service_utilization_pct ?? 0,
    street_bpr_delay_factor: simResult?.hop4_bpr_congestion.street_bpr_delay_factor ?? 1,
    congestion_alert: simResult?.hop4_bpr_congestion.congestion_alert ?? false,
  };

  const tz = simResult?.terrain_and_zoning;
  const pc = simResult?.parcel_context;
  const rtx = simResult?.relate_transaction;
  const dayPop = pc?.day_pop ?? 0;
  const nightPop = pc?.night_pop ?? 0;
  const dayPct = dayPop + nightPop > 0 ? Math.round((dayPop / (dayPop + nightPop)) * 100) : 50;

  const verdict = !simResult
    ? null
    : tz?.is_restricted
    ? { text: isAr ? "منطقة محظورة للبناء" : "Restricted Zoning", cls: "pill-rose" }
    : simResult.composite_network_gain_J >= 20
    ? { text: isAr ? "موقع ممتاز وقوي" : "Strong Prime Site", cls: "pill-emerald" }
    : simResult.composite_network_gain_J >= 5
    ? { text: isAr ? "موقع مقبول بحذر" : "Moderate Viability", cls: "pill-amber" }
    : { text: isAr ? "موقع ضعيف أو متشبع" : "Saturated / Weak", cls: "pill-rose" };

  return (
    <aside className={`drawer-shell right ${open ? "open" : "closed"}`} dir={isAr ? "rtl" : "ltr"}>
      <div className="cyber-panel drawer-card">
        <div className="drawer-header">
          <div className="tab-strip">
            <button className={`tab-btn ${tab === "summary" ? "active" : ""}`} onClick={() => setTab("summary")}>
              <Activity size={13} /> {isAr ? "الجدوى" : "Feasibility"}
            </button>
            <button className={`tab-btn ${tab === "ripples" ? "active" : ""}`} onClick={() => setTab("ripples")}>
              <Layers size={13} /> {isAr ? "التأثيرات" : "Ripples"}
            </button>
            <button className={`tab-btn ${tab === "compare" ? "active" : ""}`} onClick={() => setTab("compare")}>
              <GitCompare size={13} /> {isAr ? "مقارنة A/B" : "A/B Compare"}
            </button>
          </div>
          <button className="icon-close" onClick={onClose} title={isAr ? "إغلاق التحليل" : "Close Analytics"}>
            <X size={15} />
          </button>
        </div>

        <div className="drawer-body">
          {errorText && (
            <div className="alert-strip">
              <AlertTriangle size={14} style={{ verticalAlign: "middle" }} /> {errorText}
            </div>
          )}

          {!simResult ? (
            <p className="muted-note">
              {isAr
                ? "انقر على أي شارع في الخريطة لزرع المشروع وعرض التحليل الكامل."
                : "Click any street on the 3D map to inject a service and compute the 7 Laws."}
            </p>
          ) : (
            <>
              {tab === "summary" && (
                <>
                  {tz?.is_restricted && (
                    <div className="alert-strip" style={{ marginTop: 0 }}>
                      <AlertTriangle size={14} style={{ verticalAlign: "middle" }} />{" "}
                      <strong>{isAr ? tz.restricted_reason : (tz.restricted_reason_en ?? tz.restricted_reason)}</strong>
                      {isAr
                        ? " — المحرك يستبعد هذه المنطقة تلقائياً من المواقع المثلى."
                        : " — automatically excluded by Law 6 spatial optimizer."}
                    </div>
                  )}

                  <div className="block-box">
                    <div className="block-title">
                      <span className="trunc">{isAr ? simResult.injection.label_ar : simResult.injection.label_en}</span>
                      {verdict && <span className={`pill ${verdict.cls}`}>{verdict.text}</span>}
                    </div>

                    <div className="scenario-switch">
                      {(
                        [
                          { k: "conservative", ar: "متحفظ", en: "Conservative" },
                          { k: "base", ar: "متوقع", en: "Expected" },
                          { k: "optimistic", ar: "متفائل", en: "Optimistic" },
                        ] as const
                      ).map((sc) => (
                        <button
                          key={sc.k}
                          className={`sc-btn ${scenario === sc.k ? "active" : ""}`}
                          onClick={() => onChangeScenario(sc.k)}
                        >
                          {isAr ? sc.ar : sc.en}
                        </button>
                      ))}
                    </div>

                    <div className="kpi-grid">
                      <div className="kpi-card">
                        <span className="kpi-name">{isAr ? "الزيارات اليومية" : "Daily Visits"}</span>
                        <strong className="kpi-num c-cyan">{activeScenario.visits}</strong>
                        <span className="kpi-hint">
                          {isAr ? "تقييم الشبكة:" : "Gain J:"}{" "}
                          <span className="mono">{simResult.composite_network_gain_J}</span>
                        </span>
                      </div>

                      <div className="kpi-card">
                        <span className="kpi-name">{isAr ? "احتمال النجاح" : "Viability (200 MC)"}</span>
                        <strong
                          className={`kpi-num ${
                            simResult.monte_carlo_envelope.viability_probability_pct >= 70
                              ? "c-emerald"
                              : simResult.monte_carlo_envelope.viability_probability_pct >= 35
                              ? "c-amber"
                              : "c-rose"
                          }`}
                        >
                          {simResult.monte_carlo_envelope.viability_probability_pct}%
                        </strong>
                        <span className="kpi-hint">
                          {isAr ? "توافق الجمهور:" : "Audience Fit:"}{" "}
                          <span className="mono">{simResult.local_demographics.audience_fit_multiplier}x</span>
                        </span>
                      </div>

                      <div className="kpi-card">
                        <span className="kpi-name">{isAr ? "طلب جديد حقيقي" : "New Unmet Demand"}</span>
                        <strong className="kpi-num c-emerald">+{activeScenario.new_unmet_demand}</strong>
                        <span className="kpi-hint">
                          {isAr ? "سحب من منافسين:" : "Cannibalization:"}{" "}
                          <span className="mono">{simResult.hop1_gravity_and_access.cannibalization_pct}%</span>
                        </span>
                      </div>

                      <div className="kpi-card">
                        <span className="kpi-name">{isAr ? "سكان فُكّت عزلتهم" : "Residents Unlocked"}</span>
                        <strong className="kpi-num c-violet">
                          {simResult.hop1_gravity_and_access.residents_unlocked_within_ideal_walk.toLocaleString()}
                        </strong>
                        <span className="kpi-hint">
                          {isAr ? "عدالة التغطية:" : "E2SFCA:"}{" "}
                          <span className="mono">
                            {simResult.hop1_gravity_and_access.equity_score_before} →{" "}
                            {simResult.hop1_gravity_and_access.equity_score_after}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>

                  {pc?.parcel_id && (
                    <div className="block-box parcel-card">
                      <div className="block-title">
                        <span>
                          <Building2 size={13} style={{ verticalAlign: "middle" }} />{" "}
                          {isAr ? "بطاقة العقار 3D ومعاملة Relate" : "3D Parcel & Relate ACID Context"}
                        </span>
                        <span className={`pill ${pc.ownership_status === "BLOCKED_OWNERSHIP" ? "pill-rose" : "pill-cyan"}`}>
                          {pc.ownership_status === "BLOCKED_OWNERSHIP"
                            ? isAr ? "ملكية محجوبة" : "BLOCKED"
                            : (pc.land_use ?? "parcel").replace("_", " ")}
                        </span>
                      </div>

                      <div className="parcel-meta-grid">
                        <div className="p-stat">
                          <span className="p-lbl">{isAr ? "القسيمة" : "Parcel"}</span>
                          <span className="p-val mono">{pc.parcel_id}</span>
                        </div>
                        <div className="p-stat">
                          <span className="p-lbl">{isAr ? "الارتفاع / المساحة" : "Floors · GFA"}</span>
                          <span className="p-val tabular">
                            {pc.levels ?? 1}F · {Math.round(pc.gfa_m2 ?? 0).toLocaleString()} m²
                          </span>
                        </div>
                        <div className="p-stat">
                          <span className="p-lbl">{isAr ? "الصلاحية" : "Suitability"}</span>
                          <span className="p-val">{(pc.site_suitability ?? "—").replace(/_/g, " ")}</span>
                        </div>
                        <div className="p-stat">
                          <span className="p-lbl">{isAr ? "بعد عن النقرة" : "Parcel Snap"}</span>
                          <span className="p-val tabular">{pc.dist_to_click_m ?? 0} m</span>
                        </div>
                      </div>

                      <div className="pulse-split">
                        <div className="pulse-row">
                          <span className="c-amber tabular">
                            <Sun size={11} style={{ verticalAlign: "middle" }} /> {isAr ? "نهار" : "Day"} {dayPop.toLocaleString()}
                          </span>
                          <span className="c-violet tabular">
                            {nightPop.toLocaleString()} {isAr ? "ليل" : "Night"} <Moon size={11} style={{ verticalAlign: "middle" }} />
                          </span>
                        </div>
                        <div className="pulse-track">
                          <div className="pulse-day" style={{ width: `${dayPct}%` }} />
                        </div>
                      </div>

                      {rtx && (
                        <div className="tx-strip">
                          <div className="tx-strip-left">
                            <span className="tx-dot" />
                            <Database size={12} />
                            <span className="mono">{rtx.tx_state}</span>
                            {rtx.elapsed_ms != null && (
                              <span className="mono tx-ms">{rtx.elapsed_ms.toFixed(2)}ms</span>
                            )}
                          </div>
                          {onOpenRelateTrace && (
                            <button className="tx-trace-btn" onClick={onOpenRelateTrace}>
                              <Terminal size={11} /> {isAr ? "سجل Cypher" : "Trace"}
                            </button>
                          )}
                        </div>
                      )}

                      {rtx?.multi_hop_context && (
                        <div className="hop-micro-row tabular">
                          <span>
                            {isAr ? "خدمات 2-Hop:" : "2-Hop Services:"}{" "}
                            <strong>{rtx.multi_hop_context.nearby_services ?? 0}</strong>
                          </span>
                          <span>
                            {isAr ? "منافسون:" : "Competitors:"}{" "}
                            <strong>{rtx.multi_hop_context.nearby_competitors ?? 0}</strong>
                          </span>
                          {(rtx.multi_hop_context.nearby_env_zones?.length ?? 0) > 0 && (
                            <span className="trunc">
                              {isAr ? "جوار:" : "Near:"} {rtx.multi_hop_context.nearby_env_zones?.slice(0, 2).join(", ")}
                            </span>
                          )}
                        </div>
                      )}

                      {onCommitDecision && (
                        <div className="decision-box">
                          <input
                            className="decision-input"
                            type="text"
                            value={decisionNote}
                            onChange={(e) => setDecisionNote(e.target.value)}
                            placeholder={
                              isAr
                                ? "ملاحظة قرار الوكيل (مثلاً: خلاف ورثة / إيجار ممتاز)..."
                                : "Decision rationale (e.g. Prime corner lease / Heirs dispute)..."
                            }
                          />
                          <div className="decision-actions">
                            <button
                              className="dec-btn dec-approve"
                              disabled={decisionBusy}
                              onClick={() => {
                                const rsn = decisionNote.trim() || (isAr ? "اعتماد الموقع بناءً على جدوى القوانين السبعة" : "Approved via 7-Law volumetric simulation");
                                void onCommitDecision("APPROVED", rsn, false);
                                setDecisionNote("");
                              }}
                            >
                              <CheckCircle2 size={12} /> {isAr ? "اعتماد COMMIT" : "Approve"}
                            </button>
                            <button
                              className="dec-btn dec-watch"
                              disabled={decisionBusy}
                              onClick={() => {
                                const rsn = decisionNote.trim() || (isAr ? "قيد المتابعة والمراقبة" : "Watchlist for seasonal demand");
                                void onCommitDecision("WATCHLIST", rsn, false);
                                setDecisionNote("");
                              }}
                            >
                              <Bookmark size={12} /> {isAr ? "متابعة" : "Watch"}
                            </button>
                            <button
                              className="dec-btn dec-block"
                              disabled={decisionBusy}
                              onClick={() => {
                                const rsn = decisionNote.trim() || (isAr ? "رفض العقار وحجب ملكيته من التحسين" : "Rejected & ownership blocked from Law 6 optimizer");
                                void onCommitDecision("REJECTED", rsn, true);
                                setDecisionNote("");
                              }}
                            >
                              <ShieldAlert size={12} /> {isAr ? "رفض وحجب" : "Reject & Block"}
                            </button>
                          </div>
                          {decisionFeedback && <div className="dec-feedback">{decisionFeedback}</div>}
                        </div>
                      )}
                    </div>
                  )}

                  {tz && (
                    <div className="block-box">
                      <div className="block-title">
                        <span>
                          <Mountain size={13} style={{ verticalAlign: "middle" }} />{" "}
                          {isAr ? "التضاريس والجوار البيئي والسياحي" : "Terrain Slope & Eco-Tourism"}
                        </span>
                        <span className={`pill ${tz.env_boost_multiplier >= 1.05 ? "pill-emerald" : tz.env_boost_multiplier < 0.98 ? "pill-rose" : "pill-cyan"}`}>
                          {isAr ? `جوار ${tz.env_boost_multiplier}x` : `Boost ${tz.env_boost_multiplier}x`}
                        </span>
                      </div>

                      <div className="row-item">
                        <span>{isAr ? "ارتفاع الموقع وتأثير الميل" : "Elevation & Slope Friction"}</span>
                        <strong className="mono">
                          {tz.elevation_m != null ? `${tz.elevation_m}${isAr ? "م" : "m"}` : "—"} (
                          {tz.slope_walk_friction_pct > 0 ? `+${tz.slope_walk_friction_pct}%` : `${tz.slope_walk_friction_pct}%`})
                        </strong>
                      </div>
                      <div style={{ fontSize: 11.5, color: "#94a3b8", paddingBottom: 6 }}>
                        {isAr ? tz.terrain_verdict_ar : (tz.terrain_verdict_en ?? tz.terrain_verdict_ar)}
                        {tz.is_food_or_hospitality && (
                          <span className="pill pill-amber" style={{ marginInlineStart: 6 }}>
                            {isAr ? "ميزة طعام وسياحة" : "Food & Tourism Bonus"}
                          </span>
                        )}
                      </div>

                      {tz.proximity_drivers.length > 0 ? (
                        tz.proximity_drivers.map((d, i) => (
                          <div key={i} className="row-item">
                            <span className="trunc">
                              <Trees size={12} style={{ verticalAlign: "middle", marginInlineEnd: 4 }} className="c-emerald" />
                              {isAr ? d.title_ar : (d.title_en ?? d.title_ar)}{" "}
                              <span className="muted">({d.distance_m}{isAr ? "م" : "m"})</span>
                            </span>
                            <span className={`mono ${d.effect_pct >= 0 ? "c-emerald" : "c-rose"}`} dir="ltr">
                              {d.effect_pct >= 0 ? `+${d.effect_pct}%` : `${d.effect_pct}%`}
                            </span>
                          </div>
                        ))
                      ) : (
                        <p className="muted-note">
                          {isAr
                            ? "محيط حضري قياسي (لا توجد حدائق أو معالم سياحية ملاصقة ضمن 300م)."
                            : "Standard urban catchment (no parks or tourism landmarks within 300m)."}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="block-box">
                    <div className="block-title">
                      <span>{isAr ? "تركيبة السكان حول هذا الموقع" : "Catchment Demographics"}</span>
                      <span className="pill pill-cyan">
                        {isAr ? `توافق ${simResult.local_demographics.audience_fit_multiplier}x` : `${simResult.local_demographics.audience_fit_multiplier}x fit`}
                      </span>
                    </div>
                    {Object.entries(simResult.local_demographics.composition_pct).map(([ax, pct]) => (
                      <div key={ax} className="demo-bar">
                        <span className="demo-lbl">
                          {AXIS_LABELS_I18N[ax] ? (isAr ? AXIS_LABELS_I18N[ax].ar : AXIS_LABELS_I18N[ax].en) : ax}
                        </span>
                        <div className="track">
                          <div className="fill" style={{ width: `${Math.min(100, pct * 1.9)}%` }} />
                        </div>
                        <span className="demo-val mono">{pct}%</span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {tab === "ripples" && (
                <>
                  <div className="block-box">
                    <div className="block-title">
                      <span>{isAr ? "تأثر المنافسين المجاورين" : "Hop 2 · Competitor Ripple"}</span>
                      <span className="mono muted">
                        {simResult.hop2_competitor_ripple.impacted_count}/
                        {simResult.hop2_competitor_ripple.existing_competitors_in_area}
                      </span>
                    </div>
                    {simResult.hop2_competitor_ripple.top_impacted.length === 0 ? (
                      <p className="c-emerald" style={{ margin: 0, fontSize: 12 }}>
                        {isAr
                          ? "لا يوجد تآكل منافسة — فجوة سوقية حقيقية بالكامل."
                          : "Zero cannibalization — pure blue-ocean gap!"}
                      </p>
                    ) : (
                      simResult.hop2_competitor_ripple.top_impacted.slice(0, 6).map((c) => (
                        <div key={c.service_id} className="row-item">
                          <span className="trunc">{c.name}</span>
                          <span className="c-amber mono" dir="ltr">
                            -{c.visits_lost}/d ({c.pct_change}%)
                          </span>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="block-box">
                    <div className="block-title">
                      <span>{isAr ? "فرص وخدمات مساندة ستنشأ حولك" : "Hop 3 · Leontief Induced Synergy"}</span>
                    </div>
                    {simResult.hop3_induced_synergy.slice(0, 5).map((syn) => (
                      <div key={syn.target_category} className="row-item">
                        <span>
                          {isAr ? syn.label_ar : syn.label_en}{" "}
                          <span className="muted" style={{ fontSize: 11 }}>
                            ({syn.nearby_existing_count} {isAr ? "قريب" : "nearby"})
                          </span>
                        </span>
                        <span className={`pill ${syn.status === "NEW_DEFICIT" ? "pill-amber" : "pill-emerald"}`}>
                          {syn.status === "NEW_DEFICIT"
                            ? isAr ? `فجوة +${syn.unmet_synergy_deficit}` : `+${syn.unmet_synergy_deficit} gap`
                            : isAr ? "مغطّى" : "Absorbed"}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="block-box">
                    <div className="block-title">
                      <span>{isAr ? "ضغط الزحام والقدرة الاستيعابية" : "Hop 4 · BPR Congestion"}</span>
                      <span className={`pill ${activeScenario.congestion_alert ? "pill-rose" : "pill-emerald"}`}>
                        {activeScenario.congestion_alert
                          ? isAr ? "تنبيه ضغط مرتفع" : "OVERLOAD"
                          : isAr ? "مستقر" : "STABLE"}
                      </span>
                    </div>
                    <div className="row-item">
                      <span>{isAr ? "نسبة إشغال السعة اليومية" : "Service Capacity Load"}</span>
                      <strong className="mono">{activeScenario.service_utilization_pct}%</strong>
                    </div>
                    <div className="row-item">
                      <span>{isAr ? "تأخير الشارع الملاصق" : "Adjacent Street BPR Delay"}</span>
                      <strong className="mono">{activeScenario.street_bpr_delay_factor}x</strong>
                    </div>
                  </div>
                </>
              )}

              {tab === "compare" && (
                <div className="block-box">
                  <div className="block-title">
                    <span>{isAr ? "مقارنة موقع A ضد الموقع الحالي B" : "Head-to-Head Site A vs Current B"}</span>
                  </div>
                  {!pinnedA ? (
                    <div className="stack-sm">
                      <p className="muted-note">
                        {isAr
                          ? "ثبّت الموقع الحالي كـ «موقع A»، ثم انقر أو اسحب المؤشر لموقع ثانٍ لتقارن بينهما بالأرقام المباشرة."
                          : "Pin the current pin as Site A, then click or drag to a second location to compare both under identical 7-Law physics."}
                      </p>
                      <button className="cyber-btn btn-neon full" onClick={onPinCurrentAsA}>
                        {isAr ? "تثبيت هذا الموقع كـ موقع A" : "Pin Current Location as Site A"}
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="compare-table">
                        <div className="cmp-head">
                          <span>{isAr ? "المعيار" : "Metric"}</span>
                          <span>{isAr ? "موقع A" : "Site A"}</span>
                          <span>{isAr ? "الحالي B" : "Current B"}</span>
                        </div>
                        <div className="cmp-row">
                          <span>{isAr ? "تقييم الجدوى" : "Network Gain J"}</span>
                          <strong className="mono">{pinnedA.result.composite_network_gain_J}</strong>
                          <strong className="mono c-cyan">{simResult.composite_network_gain_J}</strong>
                        </div>
                        <div className="cmp-row">
                          <span>{isAr ? "الزيارات/يوم" : "Visits / Day"}</span>
                          <strong className="mono">{pinnedA.result.monte_carlo_envelope.p50_base}</strong>
                          <strong className="mono c-cyan">{simResult.monte_carlo_envelope.p50_base}</strong>
                        </div>
                        <div className="cmp-row">
                          <span>{isAr ? "طلب جديد" : "Unmet Demand"}</span>
                          <strong className="mono">+{pinnedA.result.hop1_gravity_and_access.new_unmet_demand_captured}</strong>
                          <strong className="mono c-emerald">+{simResult.hop1_gravity_and_access.new_unmet_demand_captured}</strong>
                        </div>
                        <div className="cmp-row">
                          <span>{isAr ? "جوار بيئي" : "Eco-Tourism"}</span>
                          <strong className="mono">{pinnedA.result.terrain_and_zoning?.env_boost_multiplier ?? 1}x</strong>
                          <strong className="mono c-emerald">{simResult.terrain_and_zoning?.env_boost_multiplier ?? 1}x</strong>
                        </div>
                        <div className="cmp-row">
                          <span>{isAr ? "فكّ عزلة سكان" : "Unlocked Pop"}</span>
                          <strong className="mono">{pinnedA.result.hop1_gravity_and_access.residents_unlocked_within_ideal_walk}</strong>
                          <strong className="mono c-violet">{simResult.hop1_gravity_and_access.residents_unlocked_within_ideal_walk}</strong>
                        </div>
                      </div>

                      <div className="winner-banner">
                        {simResult.composite_network_gain_J > pinnedA.result.composite_network_gain_J
                          ? isAr ? "الأفضل رياضياً الآن: الموقع الحالي (B)" : "Mathematical Winner: Current Site (B)"
                          : simResult.composite_network_gain_J < pinnedA.result.composite_network_gain_J
                          ? isAr ? "الأفضل رياضياً الآن: الموقع المثبّت (A)" : "Mathematical Winner: Pinned Site (A)"
                          : isAr ? "الموقعان متكافئان رياضياً" : "Sites are mathematically tied"}
                      </div>

                      <div className="grid-2" style={{ marginTop: 10 }}>
                        <button className="cyber-btn" onClick={onPinCurrentAsA}>
                          {isAr ? "استبدال A بالحالي" : "Replace A with B"}
                        </button>
                        <button className="cyber-btn active-rose" onClick={onClearPinA}>
                          {isAr ? "إلغاء التثبيت" : "Clear Pin A"}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
