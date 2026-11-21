import { useState } from "react";
import {
  Activity,
  BarChart3,
  Bot,
  Box,
  ChevronDown,
  Globe,
  Languages,
  MapPin,
  Mountain,
  Satellite,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { geocodeApi } from "../api";
import { QUICK_CITIES } from "../i18n";
import type {
  AreaLayersResponse,
  CatalogResponse,
  GeocodeResult,
  Lang,
  MapStyleMode,
} from "../types";

interface Props {
  lang: Lang;
  onToggleLang: () => void;
  areaData: AreaLayersResponse | null;
  catalog: CatalogResponse | null;
  activeSlug: string;
  onSelectArea: (slug: string) => void;
  syncRadius: number;
  onChangeSyncRadius: (r: number) => void;
  onSyncLive: () => void;
  onFlyToLocation: (lat: number, lon: number, zoom?: number) => void;
  is3D: boolean;
  onToggle3D: () => void;
  mapStyle: MapStyleMode;
  onChangeMapStyle: (m: MapStyleMode) => void;
  leftOpen: boolean;
  onToggleLeft: () => void;
  rightOpen: boolean;
  onToggleRight: () => void;
  aiOpen: boolean;
  onToggleAi: () => void;
  loading: boolean;
}

const RADIUS_OPTIONS = [
  { val: 400, en: "400m (Dense)", ar: "400م (كثيف)" },
  { val: 750, en: "750m (Standard)", ar: "750م (قياسي)" },
  { val: 1200, en: "1.2km (Wide)", ar: "1.2كم (واسع)" },
  { val: 1800, en: "1.8km (District)", ar: "1.8كم (قطاع)" },
  { val: 2500, en: "2.5km (Macro)", ar: "2.5كم (شامل)" },
];

export function TopBar({
  lang,
  onToggleLang,
  areaData,
  catalog,
  activeSlug,
  onSelectArea,
  syncRadius,
  onChangeSyncRadius,
  onSyncLive,
  onFlyToLocation,
  is3D,
  onToggle3D,
  mapStyle,
  onChangeMapStyle,
  leftOpen,
  onToggleLeft,
  rightOpen,
  onToggleRight,
  aiOpen,
  onToggleAi,
  loading,
}: Props) {
  const isAr = lang === "ar";
  const [worldOpen, setWorldOpen] = useState(false);
  const [legendOpen, setLegendOpen] = useState(true);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<GeocodeResult[]>([]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setSearching(true);
    try {
      setResults(await geocodeApi(query.trim(), lang));
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <>
      <header className="cyber-panel top-bar" dir={isAr ? "rtl" : "ltr"}>
        <div className="top-left">
          <button
            className={`cyber-btn ${leftOpen ? "active-cyan" : ""}`}
            onClick={onToggleLeft}
            title={isAr ? "إظهار / إخفاء لوحة التحكم" : "Toggle Controls"}
          >
            <SlidersHorizontal size={14} /> {isAr ? "التحكم" : "Controls"}
          </button>

          <div className="brand">
            <div className="brand-orb">
              <Activity size={15} />
            </div>
            <h1>NABD · نبض</h1>
          </div>

          <button
            className={`cyber-btn ${worldOpen ? "active-cyan" : ""}`}
            onClick={() => setWorldOpen((v) => !v)}
            title={isAr ? "تغيير المدينة أو المنطقة المحفوظة وسعة السحب" : "Explore World Cities, Saved Areas & Sync Radius"}
          >
            <Globe size={14} />
            <span className="world-slug">{activeSlug}</span>
            <ChevronDown size={13} />
          </button>
        </div>

        <div className="style-switcher">
          <button
            className={`style-pill ${mapStyle === "cyber" ? "active" : ""}`}
            onClick={() => onChangeMapStyle("cyber")}
          >
            {isAr ? "سايبر 3D" : "Cyber 3D"}
          </button>
          <button
            className={`style-pill ${mapStyle === "satellite" ? "active-sat" : ""}`}
            onClick={() => onChangeMapStyle("satellite")}
          >
            <Satellite size={12} /> {isAr ? "قمر صناعي" : "Satellite"}
          </button>
          <button
            className={`style-pill ${mapStyle === "terrain" ? "active-topo" : ""}`}
            onClick={() => onChangeMapStyle("terrain")}
          >
            <Mountain size={12} /> {isAr ? "تضاريس" : "Terrain"}
          </button>
        </div>

        <div className="top-right">
          <button
            className="cyber-btn btn-neon"
            onClick={onSyncLive}
            disabled={loading}
            title={isAr ? `سحب حي للمنطقة الظاهرة (${syncRadius}م)` : `Sync live OSM data (${syncRadius}m radius)`}
          >
            <Globe size={14} /> {isAr ? "سحب حي" : "Sync Live"}
          </button>

          <button
            className={`cyber-btn ${aiOpen ? "active-violet" : ""}`}
            onClick={onToggleAi}
          >
            <Bot size={14} /> {isAr ? "AI" : "AI"}
          </button>

          <button
            className={`cyber-btn ${is3D ? "active-cyan" : ""}`}
            onClick={onToggle3D}
            title="3D / 2D"
          >
            <Box size={14} /> {is3D ? "3D" : "2D"}
          </button>

          <button
            className="cyber-btn"
            onClick={onToggleLang}
            title="Switch Language (EN / العربية)"
          >
            <Languages size={14} /> {isAr ? "EN" : "عربي"}
          </button>

          <button
            className={`cyber-btn ${rightOpen ? "active-cyan" : ""}`}
            onClick={onToggleRight}
          >
            <BarChart3 size={14} /> {isAr ? "التحليل" : "Analytics"}
          </button>
        </div>
      </header>

      {/* Clean Floating Micro-Telemetry Pill beneath TopBar */}
      {areaData && !worldOpen && (
        <div className="micro-telemetry" dir={isAr ? "rtl" : "ltr"}>
          <span>{isAr ? "مبانٍ" : "Blocks"} <strong>{areaData.stats.blocks.toLocaleString()}</strong></span>
          <span className="sep" />
          <span>{isAr ? "سكان" : "Pop"} <strong>~{areaData.stats.total_est_pop.toLocaleString()}</strong></span>
          <span className="sep" />
          <span>{isAr ? "خدمات" : "Services"} <strong>{areaData.stats.services}</strong></span>
          {areaData.stats.elev_min_m != null && areaData.stats.elev_max_m != null && (
            <>
              <span className="sep" />
              <span>
                {isAr ? "ارتفاع" : "Elev"}{" "}
                <strong>
                  {Math.round(areaData.stats.elev_min_m)}–{Math.round(areaData.stats.elev_max_m)}
                  {isAr ? "م" : "m"}
                </strong>
              </span>
            </>
          )}
        </div>
      )}

      {/* Ultra-Compact Floating Color Key (instant visual readability) */}
      {!worldOpen && (
        <div className="mini-legend-wrap" dir={isAr ? "rtl" : "ltr"}>
          {legendOpen ? (
            <div className="mini-legend">
              <span className="ml-item"><i style={{ background: "#00e699" }} />{isAr ? "فك عزلة" : "Unlocked"}</span>
              <span className="ml-item"><i style={{ background: "#00d4ff" }} />{isAr ? "سيطرة" : "Dominant"}</span>
              <span className="ml-item"><i style={{ background: "#f59e0b" }} />{isAr ? "تنافس" : "Shared"}</span>
              <span className="ml-sep" />
              <span className="ml-item"><i style={{ background: "#15803d", border: "1px solid #4ade80" }} />{isAr ? "حدائق" : "Parks"}</span>
              <span className="ml-item"><i style={{ background: "#0369a1", border: "1px solid #38bdf8" }} />{isAr ? "مياه" : "Water"}</span>
              <span className="ml-item"><i style={{ background: "#e879f9" }} />{isAr ? "سياحة" : "Tourism"}</span>
              <button
                className="ml-close"
                onClick={() => setLegendOpen(false)}
                title={isAr ? "إخفاء مفتاح الألوان" : "Hide Legend"}
              >
                <X size={11} />
              </button>
            </div>
          ) : (
            <button
              className="mini-legend ml-collapsed"
              onClick={() => setLegendOpen(true)}
              title={isAr ? "إظهار مفتاح الألوان" : "Show Color Key"}
            >
              <i style={{ background: "#00e699" }} />
              <i style={{ background: "#00d4ff" }} />
              <i style={{ background: "#f59e0b" }} />
              <span>{isAr ? "الألوان" : "Legend"}</span>
            </button>
          )}
        </div>
      )}

      {/* Unified World Explorer, Saved Areas & Sync Radius Popover */}
      {worldOpen && (
        <div className="cyber-panel search-popover" dir={isAr ? "rtl" : "ltr"}>
          <div className="search-pop-head">
            <span>
              <Globe size={13} style={{ verticalAlign: "middle" }} />{" "}
              {isAr ? "المناطق المحفوظة واستكشاف العالم" : "Saved Areas & Global Explorer"}
            </span>
            <button className="icon-close" onClick={() => setWorldOpen(false)}>
              <X size={14} />
            </button>
          </div>

          <div className="world-controls-row">
            <div className="world-field">
              <label>{isAr ? "المنطقة المحفوظة (.rl)" : "Saved Relate Graph"}</label>
              <select
                value={activeSlug}
                onChange={(e) => {
                  onSelectArea(e.target.value);
                  setWorldOpen(false);
                }}
              >
                {(catalog?.available_areas ?? ["irbid-yarmouk"]).map((slug) => (
                  <option key={slug} value={slug}>
                    {slug}
                  </option>
                ))}
              </select>
            </div>

            <div className="world-field" style={{ maxWidth: 165 }}>
              <label>{isAr ? "سعة السحب الحي" : "Sync Radius"}</label>
              <select
                value={syncRadius}
                onChange={(e) => onChangeSyncRadius(parseInt(e.target.value, 10))}
              >
                {RADIUS_OPTIONS.map((o) => (
                  <option key={o.val} value={o.val}>
                    {isAr ? o.ar : o.en}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="world-divider" />

          <form className="search-form" onSubmit={(e) => void handleSearch(e)}>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={isAr ? "ابحث عن أي مدينة (نيويورك، لندن، عمّان...)" : "Fly to any city (Manhattan, London, Tokyo...)"}
              autoFocus
            />
            <button type="submit" className="cyber-btn btn-neon" disabled={searching}>
              <Search size={14} /> {searching ? "..." : isAr ? "بحث" : "Go"}
            </button>
          </form>

          <div className="quick-cities">
            {QUICK_CITIES.map((c) => (
              <button
                key={c.nameEn}
                className="city-chip"
                onClick={() => {
                  onFlyToLocation(c.lat, c.lon, c.zoom);
                  setWorldOpen(false);
                }}
              >
                <MapPin size={11} /> {isAr ? c.nameAr : c.nameEn}
              </button>
            ))}
          </div>

          {results.length > 0 && (
            <div className="search-results">
              {results.map((r, i) => (
                <button
                  key={i}
                  className="search-res-item"
                  onClick={() => {
                    onFlyToLocation(r.lat, r.lon, 15.2);
                    setWorldOpen(false);
                  }}
                >
                  <MapPin size={13} className="c-cyan" style={{ flexShrink: 0 }} />
                  <span>{r.display_name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
}
