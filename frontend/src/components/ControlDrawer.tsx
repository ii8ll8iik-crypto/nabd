import { useState } from "react";
import {
  Building2,
  ChevronDown,
  ChevronUp,
  Compass,
  Layers,
  Paintbrush,
  Sliders,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { AXIS_LABELS_I18N, TIME_LABELS_I18N, ZONE_LABELS } from "../i18n";
import type {
  CatalogResponse,
  CustomDnaState,
  IllusionsResponse,
  Lang,
  LayersVisibility,
  MapTool,
  OptimalSite,
  SandboxState,
} from "../types";

const DNA_EXAMPLES = [
  { ar: "مطعم شاورما", en: "Shawarma Restaurant" },
  { ar: "ملعب بادل", en: "Padel Court" },
  { ar: "نادي رياضي نسائي", en: "Women's Gym" },
  { ar: "عيادة أسنان", en: "Dental Clinic" },
  { ar: "مساحة عمل ودراسة", en: "Coworking Space" },
  { ar: "مغسلة سيارات", en: "Car Wash" },
];

interface Props {
  lang: Lang;
  open: boolean;
  onClose: () => void;
  catalog: CatalogResponse | null;
  category: string;
  onChangeCategory: (c: string) => void;
  useCustomDna: boolean;
  onToggleCustomDna: (v: boolean) => void;
  customDna: CustomDnaState;
  onChangeCustomDna: (d: CustomDnaState) => void;
  onRunCustomDna: () => void;
  onSynthesizeDna: (nameOverride?: string) => void;
  synthesizingDna: boolean;
  attractionMult: number;
  onChangeAttractionMult: (v: number) => void;
  capacityMult: number;
  onChangeCapacityMult: (v: number) => void;
  timeOfDay: string;
  onChangeTimeOfDay: (t: string) => void;
  onOptimize: () => void;
  optimalSites: OptimalSite[];
  onSelectOptimalSite: (s: OptimalSite) => void;
  paintPreset: string;
  onChangePaintPreset: (p: string) => void;
  paintRadius: number;
  onChangePaintRadius: (r: number) => void;
  onSelectTool: (t: MapTool) => void;
  sandbox: SandboxState;
  onRemoveZone: (id: string) => void;
  onRemoveClosedRoad: (id: string) => void;
  onRemovePopSurge: (id: string) => void;
  onRestoreDemolished: () => void;
  layersVis: LayersVisibility;
  onChangeLayersVis: (next: LayersVisibility) => void;
  onToggleIllusions: (checked: boolean) => void;
  illusionsData: IllusionsResponse | null;
  loading: boolean;
}

export function ControlDrawer(props: Props) {
  const isAr = props.lang === "ar";
  const [tab, setTab] = useState<"project" | "reality" | "layers">("project");
  const [showAdvancedAud, setShowAdvancedAud] = useState(false);
  const serviceOptions = props.catalog ? Object.values(props.catalog.services) : [];

  const scaleLabel =
    props.attractionMult < 0.85
      ? isAr ? "محل صغير / كشك" : "Small Kiosk"
      : props.attractionMult > 1.45
      ? isAr ? "مركز رئيسي فخم" : "Flagship Hub"
      : isAr ? "حجم قياسي" : "Standard Scale";

  return (
    <aside className={`drawer-shell left ${props.open ? "open" : "closed"}`} dir={isAr ? "rtl" : "ltr"}>
      <div className="cyber-panel drawer-card">
        <div className="drawer-header">
          <div className="tab-strip">
            <button className={`tab-btn ${tab === "project" ? "active" : ""}`} onClick={() => setTab("project")}>
              <Sliders size={13} /> {isAr ? "المشروع" : "Project"}
            </button>
            <button className={`tab-btn ${tab === "reality" ? "active" : ""}`} onClick={() => setTab("reality")}>
              <Paintbrush size={13} /> {isAr ? "الواقع الحي" : "Sandbox"}
            </button>
            <button className={`tab-btn ${tab === "layers" ? "active" : ""}`} onClick={() => setTab("layers")}>
              <Layers size={13} /> {isAr ? "الطبقات" : "Layers"}
            </button>
          </div>
          <button className="icon-close" onClick={props.onClose} title={isAr ? "إغلاق اللوحة" : "Close Panel"}>
            <X size={15} />
          </button>
        </div>

        <div className="drawer-body">
          {tab === "project" && (
            <>
              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "نوع المشروع أو أي منشأة" : "Service / Any Facility DNA"}</span>
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={props.useCustomDna}
                      onChange={(e) => props.onToggleCustomDna(e.target.checked)}
                    />
                    {isAr ? "أي منشأة حرة" : "Any Facility"}
                  </label>
                </div>

                {!props.useCustomDna ? (
                  <select
                    value={props.category}
                    onChange={(e) => props.onChangeCategory(e.target.value)}
                  >
                    {serviceOptions.map((s) => (
                      <option key={s.key} value={s.key}>
                        {isAr ? `${s.label_ar} (${s.label_en})` : `${s.label_en} — ${s.label_ar}`}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="stack-sm">
                    <div style={{ display: "flex", gap: 6 }}>
                      <input
                        type="text"
                        value={props.customDna.name}
                        onChange={(e) => props.onChangeCustomDna({ ...props.customDna, name: e.target.value })}
                        placeholder={isAr ? "اكتب أي مشروع (مطعم شاورما، بادل، عيادة أسنان...)" : "Type ANY business (Padel Court, Dental Clinic...)"}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            props.onSynthesizeDna();
                          }
                        }}
                      />
                      <button
                        className="cyber-btn active-violet"
                        onClick={() => props.onSynthesizeDna()}
                        disabled={props.synthesizingDna}
                        title={isAr ? "توليد الفيزياء الرياضية والجمهور والمنافسين تلقائياً" : "Auto-synthesize urban physics & competition DNA"}
                      >
                        <Wand2 size={14} /> {props.synthesizingDna ? "..." : isAr ? "توليد" : "Auto"}
                      </button>
                    </div>

                    <div className="dna-chips">
                      {DNA_EXAMPLES.map((ex) => (
                        <button
                          key={ex.en}
                          className="dna-chip"
                          onClick={() => props.onSynthesizeDna(isAr ? ex.ar : ex.en)}
                          disabled={props.synthesizingDna}
                        >
                          {isAr ? ex.ar : ex.en}
                        </button>
                      ))}
                    </div>

                    {(props.customDna.rationale_ar || props.customDna.rationale_en) && (
                      <div className="dna-note">
                        {isAr ? props.customDna.rationale_ar : props.customDna.rationale_en}
                      </div>
                    )}

                    <div className="world-field">
                      <label>{isAr ? "المنافسون الحقيقيون على الخريطة (OSM)" : "Competes With Existing OSM Layer"}</label>
                      <select
                        value={props.customDna.competes_with_category}
                        onChange={(e) =>
                          props.onChangeCustomDna({ ...props.customDna, competes_with_category: e.target.value })
                        }
                      >
                        <option value="custom">
                          {isAr ? "فجوة جديدة (بلا منافس مباشر مسجّل)" : "Blue Ocean (New Niche / No Direct OSM Category)"}
                        </option>
                        {serviceOptions.map((s) => (
                          <option key={s.key} value={s.key}>
                            {isAr ? `ينافس: ${s.label_ar}` : `Competes with: ${s.label_en}`}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="range-box">
                      <label>
                        <span>{isAr ? "حساسية المسافة (0.6 بعيد ← 2.8 محلي)" : "Distance Decay β (0.6 Far → 2.8 Local)"}</span>
                        <strong className="mono">{props.customDna.beta_decay}</strong>
                      </label>
                      <input
                        type="range" min={0.6} max={2.8} step={0.05}
                        value={props.customDna.beta_decay}
                        onChange={(e) =>
                          props.onChangeCustomDna({ ...props.customDna, beta_decay: parseFloat(e.target.value) })
                        }
                      />
                    </div>

                    <div className="grid-2">
                      <div className="range-box">
                        <label>
                          <span>{isAr ? "السعة/يوم" : "Cap/day"}</span>
                          <strong className="mono">{props.customDna.daily_capacity}</strong>
                        </label>
                        <input
                          type="range" min={20} max={500} step={10}
                          value={props.customDna.daily_capacity}
                          onChange={(e) =>
                            props.onChangeCustomDna({ ...props.customDna, daily_capacity: parseInt(e.target.value, 10) })
                          }
                        />
                      </div>
                      <div className="range-box">
                        <label>
                          <span>{isAr ? "الطلب/1000" : "Dem/1k"}</span>
                          <strong className="mono">{props.customDna.demand_per_1k_pop}</strong>
                        </label>
                        <input
                          type="range" min={4} max={100} step={2}
                          value={props.customDna.demand_per_1k_pop}
                          onChange={(e) =>
                            props.onChangeCustomDna({ ...props.customDna, demand_per_1k_pop: parseFloat(e.target.value) })
                          }
                        />
                      </div>
                    </div>

                    <button
                      className="cyber-btn full"
                      style={{ justifyContent: "space-between", padding: "6px 10px" }}
                      onClick={() => setShowAdvancedAud((v) => !v)}
                    >
                      <span>{isAr ? "تخصيص شرائح الجمهور الست (6 فئات)" : "Fine-Tune All 6 Audience Segments"}</span>
                      {showAdvancedAud ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>

                    {showAdvancedAud && (
                      <div className="aud-box">
                        {Object.keys(AXIS_LABELS_I18N).map((ax) => (
                          <div key={ax} className="range-box" style={{ marginTop: 4 }}>
                            <label>
                              <span>{isAr ? AXIS_LABELS_I18N[ax].ar : AXIS_LABELS_I18N[ax].en}</span>
                              <strong className="mono">
                                {Math.round((props.customDna.audience_weights[ax] ?? 0.5) * 100)}%
                              </strong>
                            </label>
                            <input
                              type="range" min={0} max={1} step={0.05}
                              value={props.customDna.audience_weights[ax] ?? 0.5}
                              onChange={(e) =>
                                props.onChangeCustomDna({
                                  ...props.customDna,
                                  audience_weights: {
                                    ...props.customDna.audience_weights,
                                    [ax]: parseFloat(e.target.value),
                                  },
                                })
                              }
                            />
                          </div>
                        ))}
                      </div>
                    )}

                    <button className="cyber-btn btn-neon full" onClick={props.onRunCustomDna}>
                      {isAr ? "تشغيل المحاكاة لهذه المنشأة" : "Simulate Custom Facility"}
                    </button>
                  </div>
                )}
              </div>

              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "تخصيص المنشأة نفسها" : "Facility Scale & Power"}</span>
                  <span className="pill pill-cyan">{scaleLabel}</span>
                </div>
                <div className="range-box">
                  <label>
                    <span>{isAr ? "قوة الجذب والسمعة والعلامة" : "Brand Attraction & Reputation"}</span>
                    <strong className="mono">{props.attractionMult.toFixed(1)}x</strong>
                  </label>
                  <input
                    type="range" min={0.6} max={2.2} step={0.1}
                    value={props.attractionMult}
                    onChange={(e) => props.onChangeAttractionMult(parseFloat(e.target.value))}
                  />
                </div>
                <div className="range-box">
                  <label>
                    <span>{isAr ? "السعة الاستيعابية" : "Daily Capacity Multiplier"}</span>
                    <strong className="mono">{props.capacityMult.toFixed(1)}x</strong>
                  </label>
                  <input
                    type="range" min={0.5} max={3.0} step={0.1}
                    value={props.capacityMult}
                    onChange={(e) => props.onChangeCapacityMult(parseFloat(e.target.value))}
                  />
                </div>
              </div>

              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "إيقاع المدينة (توقيت الذروة)" : "City Rhythm (Time of Day)"}</span>
                </div>
                <div className="grid-4">
                  {(["morning", "midday", "evening", "night"] as const).map((t) => (
                    <button
                      key={t}
                      className={`chip-btn ${props.timeOfDay === t ? "active" : ""}`}
                      onClick={() => props.onChangeTimeOfDay(t)}
                    >
                      {isAr ? TIME_LABELS_I18N[t].ar : TIME_LABELS_I18N[t].en}
                    </button>
                  ))}
                </div>
              </div>

              <button
                className="cyber-btn active-emerald full"
                onClick={props.onOptimize}
                disabled={props.loading}
              >
                <Sparkles size={14} />{" "}
                {isAr ? "اكتشف أفضل 5 مواقع رياضياً" : "Find Top 5 Optimal Sites (Law 6)"}
              </button>

              {props.optimalSites.length > 0 && (
                <div className="block-box">
                  <div className="block-title">
                    <span>
                      <Compass size={13} style={{ verticalAlign: "middle" }} />{" "}
                      {isAr ? "أفضل المواقع المقترحة" : "Top Ranked Locations"}
                    </span>
                  </div>
                  {props.optimalSites.map((st, idx) => (
                    <div
                      key={st.junction_id}
                      className="row-item clickable"
                      onClick={() => props.onSelectOptimalSite(st)}
                    >
                      <span>
                        <strong className="c-emerald mono">#{idx + 1}</strong> ·{" "}
                        <span className="mono">{st.daily_visits_p50}</span>{" "}
                        {isAr ? "زيارة/يوم" : "/day"}
                      </span>
                      <span className="pill pill-emerald">J = {st.gain_J}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {tab === "reality" && (
            <>
              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "فرشاة تركيبة السكان المحلية" : "Participatory Reality Brush"}</span>
                </div>
                <div className="swatch-grid">
                  {Object.entries(ZONE_LABELS).map(([k, v]) => (
                    <button
                      key={k}
                      className={`swatch-card ${props.paintPreset === k ? "selected" : ""}`}
                      style={props.paintPreset === k ? { borderColor: v.color } : undefined}
                      onClick={() => {
                        props.onChangePaintPreset(k);
                        props.onSelectTool("paint");
                      }}
                    >
                      <span className="dot" style={{ background: v.color }} />
                      <span>{isAr ? v.ar : v.en}</span>
                    </button>
                  ))}
                </div>
                <div className="range-box" style={{ marginTop: 10 }}>
                  <label>
                    <span>{isAr ? "نصف قطر الفرشاة" : "Brush Radius"}</span>
                    <strong className="mono">{props.paintRadius}{isAr ? " متر" : " m"}</strong>
                  </label>
                  <input
                    type="range" min={80} max={500} step={20}
                    value={props.paintRadius}
                    onChange={(e) => props.onChangePaintRadius(parseInt(e.target.value, 10))}
                  />
                </div>
              </div>

              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "تعديلات الواقع الحي النشطة" : "Active Live Sandbox Overrides"}</span>
                </div>

                {props.sandbox.paintedZones.length === 0 &&
                  props.sandbox.closedRoads.length === 0 &&
                  props.sandbox.demolishedBlocks.length === 0 &&
                  props.sandbox.popSurges.length === 0 && (
                    <p className="muted-note">
                      {isAr
                        ? "اختر أي أداة من الشريط السفلي (فرشاة السكان، إغلاق طريق، هدم مبنى، أو إضافة سكان) وانقر مباشرة على الخريطة."
                        : "Pick any tool from the bottom rail (Reality Brush, Close Road, Demolish, or +1,500 Pop) and click directly on the map."}
                    </p>
                  )}

                {props.sandbox.paintedZones.map((z) => {
                  const meta = ZONE_LABELS[z.preset];
                  return (
                    <div key={z.id} className="row-item">
                      <span>
                        <span className="dot" style={{ background: z.color }} />{" "}
                        {meta ? (isAr ? meta.ar : meta.en) : z.label} ({z.radius_m}{isAr ? "م" : "m"})
                      </span>
                      <button className="icon-del" onClick={() => props.onRemoveZone(z.id)}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                  );
                })}

                {props.sandbox.closedRoads.map((r, i) => (
                  <div key={r.id} className="row-item">
                    <span className="c-rose">{isAr ? `شارع مغلق #${i + 1}` : `Closed Road #${i + 1}`}</span>
                    <button className="icon-del" onClick={() => props.onRemoveClosedRoad(r.id)}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}

                {props.sandbox.popSurges.map((p, i) => (
                  <div key={p.id} className="row-item">
                    <span className="c-emerald">
                      {isAr ? `تجمع سكاني #${i + 1}` : `Population Surge #${i + 1}`} (+{p.pop.toLocaleString()})
                    </span>
                    <button className="icon-del" onClick={() => props.onRemovePopSurge(p.id)}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}

                {props.sandbox.demolishedBlocks.length > 0 && (
                  <div className="row-item">
                    <span className="c-amber">
                      <Building2 size={13} style={{ verticalAlign: "middle" }} />{" "}
                      {isAr ? "مبانٍ مهدومة:" : "Demolished Blocks:"}{" "}
                      <strong>{props.sandbox.demolishedBlocks.length}</strong>
                    </span>
                    <button className="cyber-btn" style={{ padding: "3px 8px", fontSize: 11 }} onClick={props.onRestoreDemolished}>
                      {isAr ? "استعادة" : "Restore"}
                    </button>
                  </div>
                )}
              </div>
            </>
          )}

          {tab === "layers" && (
            <>
              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "التحكم بطبقات الخريطة" : "3D Layer Stack"}</span>
                </div>
                <label className="toggle-row">
                  <span>{isAr ? "المباني ثلاثية الأبعاد / الهولوغرام" : "3D Buildings / Holographic Outlines"}</span>
                  <input
                    type="checkbox"
                    checked={props.layersVis.buildings}
                    onChange={(e) =>
                      props.onChangeLayersVis({ ...props.layersVis, buildings: e.target.checked })
                    }
                  />
                </label>
                <label className="toggle-row">
                  <span>{isAr ? "شبكة الشوارع والانحدارات" : "Relate Street Graph & Slopes"}</span>
                  <input
                    type="checkbox"
                    checked={props.layersVis.streets}
                    onChange={(e) =>
                      props.onChangeLayersVis({ ...props.layersVis, streets: e.target.checked })
                    }
                  />
                </label>
                <label className="toggle-row">
                  <span className="c-emerald">
                    {isAr ? "الحدائق والمياه والملاعب والسياحة" : "Parks, Water, Tourism & Recreation"}
                  </span>
                  <input
                    type="checkbox"
                    checked={props.layersVis.envZones}
                    onChange={(e) =>
                      props.onChangeLayersVis({ ...props.layersVis, envZones: e.target.checked })
                    }
                  />
                </label>
                <label className="toggle-row">
                  <span>{isAr ? "الخدمات والمحلات القائمة" : "Existing OSM Services"}</span>
                  <input
                    type="checkbox"
                    checked={props.layersVis.services}
                    onChange={(e) =>
                      props.onChangeLayersVis({ ...props.layersVis, services: e.target.checked })
                    }
                  />
                </label>
                <label className="toggle-row">
                  <span className="c-rose">
                    {isAr ? "رادار وهم القرب (المباني المعزولة)" : "Topological Illusion Radar (1.6x+)"}
                  </span>
                  <input
                    type="checkbox"
                    checked={props.layersVis.illusions}
                    onChange={(e) => props.onToggleIllusions(e.target.checked)}
                  />
                </label>
                {props.illusionsData && props.layersVis.illusions && (
                  <div className="alert-strip">
                    {isAr ? (
                      <>
                        تم كشف <strong>{props.illusionsData.illusion_count}</strong> مبنى معزول (~
                        {props.illusionsData.affected_residents.toLocaleString()} ساكن) · متوسط التفاف{" "}
                        <strong className="mono">{props.illusionsData.mean_circuity}x</strong>.
                      </>
                    ) : (
                      <>
                        Detected <strong>{props.illusionsData.illusion_count}</strong> isolated blocks (~
                        {props.illusionsData.affected_residents.toLocaleString()} pop) · Mean circuity{" "}
                        <strong className="mono">{props.illusionsData.mean_circuity}x</strong>.
                      </>
                    )}
                  </div>
                )}
              </div>

              <div className="block-box">
                <div className="block-title">
                  <span>{isAr ? "الهوية البصرية (بلا تداخل ألوان)" : "Zero-Clash Visual Legend"}</span>
                </div>
                <div className="legend-row"><span className="dot" style={{ background: "#00e699" }} /> {isAr ? "مبانٍ فُكّت عزلتها لأول مرة" : "Newly Unlocked Blocks (Emerald)"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#00d4ff" }} /> {isAr ? "نطاق سيطرتك القوي (≥25%)" : "Dominant Catchment (≥25% Cyan)"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#f59e0b" }} /> {isAr ? "نطاق التنافس المشترك (6–25%)" : "Shared Competition (6–25% Gold)"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#2e365c", border: "1px solid #475569" }} /> {isAr ? "مبانٍ محايدة (نيلي منتصف الليل)" : "Neutral 3D Blocks (Midnight Indigo)"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#15803d", border: "1px solid #4ade80" }} /> {isAr ? "حدائق ومساحات خضراء (محظورة)" : "Parks & Green Reserves"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#0369a1", border: "1px solid #38bdf8" }} /> {isAr ? "مياه وأودية / مستنقعات (محظورة)" : "Waterways, Rivers & Wetlands"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#e879f9" }} /> {isAr ? "معالم سياحية وتاريخية" : "Tourism & Historic Landmarks"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#8b5cf6" }} /> {isAr ? "ملاعب ومنشآت ترفيهية" : "Sports & Recreation Hubs"}</div>
                <div className="legend-row"><span className="dot" style={{ background: "#b45309" }} /> {isAr ? "مناطق صناعية" : "Industrial Zones"}</div>
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
