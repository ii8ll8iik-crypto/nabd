import { useCallback, useEffect, useRef, useState } from "react";
import { Database, Moon, Sparkles, Sun, Terminal } from "lucide-react";
import {
  buildOverridesPayload,
  createAgentDecisionApi,
  fetchAreaLayers,
  fetchCatalog,
  illusionsApi,
  optimizeApi,
  simulateApi,
  syncLiveAreaApi,
  synthesizeDnaApi,
} from "./api";
import { AiStrategistPanel } from "./components/AiStrategistPanel";
import { ControlDrawer } from "./components/ControlDrawer";
import { TelemetryDrawer } from "./components/TelemetryDrawer";
import { ToolRail } from "./components/ToolRail";
import { CommandPalette, type PaletteAction } from "./components/CommandPalette";
import { RelateInspectorPanel } from "./components/RelateInspectorPanel";
import { TopBar } from "./components/TopBar";
import { TOOL_HINTS_I18N, ZONE_LABELS } from "./i18n";
import type {
  AiMapAction,
  AreaLayersResponse,
  CatalogResponse,
  CustomDnaState,
  GeoFeatureCollection,
  IllusionsResponse,
  Lang,
  LayersVisibility,
  MapStyleMode,
  MapTool,
  OptimalSite,
  PinnedSite,
  SandboxState,
  ScenarioKey,
  SimulationResponse,
} from "./types";

const maplibregl = (window as any).maplibregl;
const DARK_BASEMAP =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const EMPTY_FC: GeoFeatureCollection = { type: "FeatureCollection", features: [] };
const EMPTY_SANDBOX: SandboxState = {
  paintedZones: [],
  closedRoads: [],
  demolishedBlocks: [],
  popSurges: [],
};

function makeCirclePolygon(lat: number, lon: number, radiusM: number, points = 38): number[][] {
  const coords: number[][] = [];
  const dLat = radiusM / 111320;
  const dLon = radiusM / (111320 * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= points; i++) {
    const a = (i / points) * Math.PI * 2;
    coords.push([lon + Math.cos(a) * dLon, lat + Math.sin(a) * dLat]);
  }
  return coords;
}

function fastDistM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dy = (lat2 - lat1) * 111320;
  const dx = (lon2 - lon1) * 111320 * Math.cos((lat1 * Math.PI) / 180);
  return Math.sqrt(dx * dx + dy * dy);
}

function buildCurvedArc(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
  archHeight = 0.24,
  steps = 22
): number[][] {
  const dx = lon2 - lon1;
  const dy = lat2 - lat1;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1e-6;
  const nx = -dy / dist;
  const ny = dx / dist;
  const midLon = (lon1 + lon2) * 0.5 + nx * dist * archHeight;
  const midLat = (lat1 + lat2) * 0.5 + ny * dist * archHeight;
  const pts: number[][] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    pts.push([
      u * u * lon1 + 2 * u * t * midLon + t * t * lon2,
      u * u * lat1 + 2 * u * t * midLat + t * t * lat2,
    ]);
  }
  return pts;
}

export default function App() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const mapReadyRef = useRef(false);
  const markerRef = useRef<any>(null);
  const isDraggingRef = useRef(false);
  const justDraggedRef = useRef(false);
  const lastDragSimRef = useRef(0);
  const simSeqRef = useRef(0);

  // Default English for international judging panel; 1-click toggle to Arabic
  const [lang, setLang] = useState<Lang>("en");
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [activeSlug, setActiveSlug] = useState("irbid-yarmouk");
  const [syncRadius, setSyncRadius] = useState<number>(750);
  const [areaData, setAreaData] = useState<AreaLayersResponse | null>(null);

  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(() => (typeof window === "undefined" ? true : window.innerWidth > 768));
  const [relateOpen, setRelateOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [traceRefresh, setTraceRefresh] = useState(0);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionFeedback, setDecisionFeedback] = useState<string | null>(null);
  const [flightBanner, setFlightBanner] = useState<string | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [is3D, setIs3D] = useState(true);
  const [mapStyle, setMapStyle] = useState<MapStyleMode>("cyber");

  const [activeTool, setActiveTool] = useState<MapTool>("inject");
  const [scenario, setScenario] = useState<ScenarioKey>("base");
  const [category, setCategory] = useState("barber");
  const [useCustomDna, setUseCustomDna] = useState(false);
  const [synthesizingDna, setSynthesizingDna] = useState(false);
  const [customDna, setCustomDna] = useState<CustomDnaState>({
    name: "Padel Court / ملعب بادل",
    beta_decay: 0.95,
    ideal_walk_min: 18.0,
    daily_capacity: 120,
    demand_per_1k_pop: 16,
    competes_with_category: "custom",
    audience_weights: {
      students: 0.9, youth_male: 1.0, youth_female: 0.55,
      families: 0.5, seniors: 0.05, commuters: 0.35,
    },
    rationale_en: "Destination sports/recreation DNA: low distance decay with strong evening & night peaks.",
    rationale_ar: "منشأة رياضية/ترفيهية وجهوية: الزبائن مستعدون لقطع مسافة أطول مع ذروة مسائية وليلية.",
  });

  const [attractionMult, setAttractionMult] = useState(1.0);
  const [capacityMult, setCapacityMult] = useState(1.0);
  const [timeOfDay, setTimeOfDay] = useState("midday");

  const [paintPreset, setPaintPreset] = useState("female_student_housing");
  const [paintRadius, setPaintRadius] = useState(240);
  const [sandbox, setSandbox] = useState<SandboxState>(EMPTY_SANDBOX);

  const [layersVis, setLayersVis] = useState<LayersVisibility>({
    buildings: true,
    streets: true,
    services: true,
    envZones: true,
    illusions: false,
  });

  const [clickedPoint, setClickedPoint] = useState<{ lat: number; lon: number } | null>(null);
  const [simResult, setSimResult] = useState<SimulationResponse | null>(null);
  const [pinnedA, setPinnedA] = useState<PinnedSite | null>(null);
  const [illusionsData, setIllusionsData] = useState<IllusionsResponse | null>(null);
  const [optimalSites, setOptimalSites] = useState<OptimalSite[]>([]);

  const [loadingText, setLoadingText] = useState<string | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);

  const stateRef = useRef({
    lang, activeTool, activeSlug, category, useCustomDna, customDna,
    attractionMult, capacityMult, timeOfDay, paintPreset, paintRadius, sandbox, clickedPoint,
  });
  stateRef.current = {
    lang, activeTool, activeSlug, category, useCustomDna, customDna,
    attractionMult, capacityMult, timeOfDay, paintPreset, paintRadius, sandbox, clickedPoint,
  };

  const updateMapSource = useCallback((sourceId: string, data: GeoFeatureCollection) => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    const src = map.getSource(sourceId) as any;
    if (src) src.setData(data);
  }, []);

  const refresh3DBuildings = useCallback(
    (
      base: AreaLayersResponse | null,
      sb: SandboxState,
      sim: SimulationResponse | null,
      tod: string = "midday"
    ) => {
      if (!base) return;
      const demolishedSet = new Set(sb.demolishedBlocks);
      const unlockedSet = new Set(sim?.spatial_effects?.unlocked_block_ids ?? []);
      const servedSet = new Set(sim?.spatial_effects?.served_block_ids ?? []);
      const sharedSet = new Set(sim?.spatial_effects?.shared_block_ids ?? []);
      const isNight = tod === "night" || tod === "evening";
      const activeParcelId = sim?.parcel_context?.parcel_id ?? "";

      const styled: GeoFeatureCollection = {
        type: "FeatureCollection",
        features: base.buildings.features.map((f) => {
          const id = String(f.properties.id ?? "");
          const origH = Number(f.properties.height ?? 7.6);
          const own = String(f.properties.ownership_status ?? "");
          const decStatus = String(f.properties.decision_status ?? "");
          const dayRatio = Number(f.properties.day_ratio ?? 0.45);
          const landUse = String(f.properties.land_use ?? "residential");

          if (demolishedSet.has(id)) {
            return { ...f, properties: { ...f.properties, height: 0.6, override_color: "#7f1d1d" } };
          }
          // Crystallized persisted Relate AgentMemory & Ownership states
          if (own === "BLOCKED_OWNERSHIP") {
            return { ...f, properties: { ...f.properties, height: Math.max(origH, 12), override_color: "#e11d48" } };
          }
          if (decStatus === "APPROVED") {
            return { ...f, properties: { ...f.properties, height: Math.max(origH, 12), override_color: "#10b981" } };
          }
          if (decStatus === "WATCHLIST") {
            return { ...f, properties: { ...f.properties, height: origH, override_color: "#f59e0b" } };
          }
          if (id && id === activeParcelId) {
            return { ...f, properties: { ...f.properties, height: Math.max(origH, 10), override_color: "#38bdf8" } };
          }
          if (unlockedSet.has(id)) {
            return { ...f, properties: { ...f.properties, height: origH, override_color: "#00e699" } };
          }
          if (servedSet.has(id)) {
            return { ...f, properties: { ...f.properties, height: origH, override_color: "#00d4ff" } };
          }
          void sharedSet;
          if (sb.paintedZones.length > 0) {
            const rings = f.geometry.coordinates as number[][][];
            const pt = rings?.[0]?.[0];
            if (pt) {
              for (let i = sb.paintedZones.length - 1; i >= 0; i--) {
                const z = sb.paintedZones[i];
                if (fastDistM(pt[1], pt[0], z.lat, z.lon) <= z.radius_m) {
                  return { ...f, properties: { ...f.properties, height: origH, override_color: z.color } };
                }
              }
            }
          }

          // Volumetric Day/Night Breathing driven by Relate 3D day_pop vs night_pop
          let pulseColor = "";
          if (!isNight) {
            if (dayRatio >= 0.62 || landUse === "office" || landUse === "commercial") {
              pulseColor = "#0284c7"; // Illuminated daytime office/commercial towers
            } else if (dayRatio >= 0.48 || landUse === "civic") {
              pulseColor = "#334155";
            } else {
              pulseColor = "#1e2640"; // Quiet daytime residential
            }
          } else {
            if (dayRatio <= 0.42 || landUse === "residential") {
              pulseColor = "#6d28d9"; // Illuminated evening/night residential neighborhoods
            } else if (landUse === "mixed_use") {
              pulseColor = "#4c1d95";
            } else {
              pulseColor = "#111827"; // Darkened office skyscrapers at night
            }
          }

          return { ...f, properties: { ...f.properties, height: origH, override_color: pulseColor } };
        }),
      };
      updateMapSource("nabd-buildings", styled);
    },
    [updateMapSource]
  );

  const runSimulation = useCallback(
    async (
      lat: number,
      lon: number,
      opts?: {
        slug?: string; cat?: string; tod?: string; custom?: boolean;
        attr?: number; cap?: number; sb?: SandboxState; silent?: boolean; dnaOverride?: CustomDnaState;
      }
    ) => {
      const seq = ++simSeqRef.current;
      const s = stateRef.current;
      const slug = opts?.slug ?? s.activeSlug;
      const cat = opts?.cat ?? s.category;
      const tod = opts?.tod ?? s.timeOfDay;
      const isCustom = opts?.custom ?? s.useCustomDna;
      const attr = opts?.attr ?? s.attractionMult;
      const cap = opts?.cap ?? s.capacityMult;
      const sb = opts?.sb ?? s.sandbox;

      if (!opts?.silent) {
        setLoadingText(
          s.lang === "ar"
            ? "جارٍ حساب القوانين السبعة والتضاريس والبيئة..."
            : "Computing 7-Law urban physics, terrain slopes & 200 MC worlds..."
        );
      }
      setErrorText(null);
      try {
        const body: Record<string, unknown> = {
          lat, lon,
          time_of_day: tod,
          attraction_multiplier: attr,
          capacity_multiplier: cap,
          overrides: buildOverridesPayload(sb),
          monte_carlo_runs: 200,
        };
        if (isCustom) {
          const activeDna = opts?.dnaOverride ?? s.customDna;
          body.custom_dna = {
            ...activeDna,
            alpha_attraction: 1.0,
          };
        } else {
          body.category = cat;
        }

        const data = await simulateApi(slug, body);
        if (seq !== simSeqRef.current) return;
        setSimResult(data);
        setClickedPoint({ lat, lon });
        setDecisionFeedback(null);
        setTraceRefresh((n) => n + 1);
        if (markerRef.current && !isDraggingRef.current) {
          markerRef.current.setLngLat([lon, lat]);
        }

        updateMapSource("injection-pin", {
          type: "FeatureCollection",
          features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: {} }],
        });

        updateMapSource("ripple-lines", {
          type: "FeatureCollection",
          features: data.hop2_competitor_ripple.top_impacted.map((c, idx) => ({
            type: "Feature",
            geometry: {
              type: "LineString",
              coordinates: buildCurvedArc(lat, lon, c.lon, c.lat, idx % 2 === 0 ? 0.25 : -0.22),
            },
            properties: { kind: "competitor", name: c.name, loss: c.visits_lost },
          })),
        });
      } catch (err) {
        setErrorText(err instanceof Error ? err.message : "Simulation failed");
      } finally {
        if (!opts?.silent && seq === simSeqRef.current) setLoadingText(null);
      }
    },
    [updateMapSource]
  );

  const loadArea = useCallback(
    async (slug: string) => {
      setLoadingText(
        stateRef.current.lang === "ar"
          ? `جارٍ تحميل شبكة وتضاريس ${slug}.rl...`
          : `Loading Relate graph & terrain for ${slug}.rl...`
      );
      setErrorText(null);
      try {
        const data = await fetchAreaLayers(slug);
        setAreaData(data);
        setActiveSlug(slug);
        setSandbox(EMPTY_SANDBOX);
        setPinnedA(null);
        setOptimalSites([]);
        setIllusionsData(null);

        const map = mapRef.current;
        if (map && mapReadyRef.current) {
          updateMapSource("nabd-buildings", data.buildings);
          updateMapSource("nabd-streets", data.streets);
          updateMapSource("nabd-services", data.services);
          updateMapSource("env-zones", data.env_zones ?? EMPTY_FC);
          updateMapSource("optimal-sites", EMPTY_FC);
          updateMapSource("illusions-layer", EMPTY_FC);
          map.flyTo({
            center: [data.meta.center_lon, data.meta.center_lat],
            zoom: 15.3, pitch: 54, bearing: -18, duration: 1200,
          });
          setIs3D(true);
        }
        await runSimulation(data.meta.center_lat, data.meta.center_lon, { slug, sb: EMPTY_SANDBOX });
      } catch (err) {
        setErrorText(err instanceof Error ? err.message : "Failed to load area");
      } finally {
        setLoadingText(null);
      }
    },
    [runSimulation, updateMapSource]
  );

  useEffect(() => {
    fetchCatalog()
      .then(setCatalog)
      .catch(() => setErrorText("Cannot reach FastAPI physics server on port 8001."));
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current || typeof map.setLight !== "function") return;
    if (timeOfDay === "night") {
      map.setLight({ anchor: "viewport", color: "#818cf8", intensity: 0.32, position: [1.5, 210, 35] });
    } else if (timeOfDay === "evening") {
      map.setLight({ anchor: "viewport", color: "#fb923c", intensity: 0.44, position: [1.5, 240, 25] });
    } else if (timeOfDay === "morning") {
      map.setLight({ anchor: "viewport", color: "#fde68a", intensity: 0.52, position: [1.5, 110, 45] });
    } else {
      map.setLight({ anchor: "viewport", color: "#e0f2fe", intensity: 0.58, position: [1.5, 150, 65] });
    }
  }, [timeOfDay, activeSlug]);

  useEffect(() => {
    refresh3DBuildings(areaData, sandbox, simResult, timeOfDay);
  }, [areaData, sandbox, simResult, timeOfDay, refresh3DBuildings]);

  useEffect(() => {
    updateMapSource("painted-zones", {
      type: "FeatureCollection",
      features: sandbox.paintedZones.map((z) => ({
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [makeCirclePolygon(z.lat, z.lon, z.radius_m)] },
        properties: { color: z.color },
      })),
    });
    updateMapSource("closed-roads", {
      type: "FeatureCollection",
      features: sandbox.closedRoads.map((r) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [r.lon, r.lat] },
        properties: {},
      })),
    });
    updateMapSource("pop-surges", {
      type: "FeatureCollection",
      features: sandbox.popSurges.map((p) => ({
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [makeCirclePolygon(p.lat, p.lon, 95, 28)] },
        properties: { pop: p.pop },
      })),
    });
  }, [sandbox, updateMapSource]);

  useEffect(() => {
    updateMapSource("pinned-a", pinnedA ? {
      type: "FeatureCollection",
      features: [{ type: "Feature", geometry: { type: "Point", coordinates: [pinnedA.lon, pinnedA.lat] }, properties: {} }],
    } : EMPTY_FC);
  }, [pinnedA, updateMapSource]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    if (typeof maplibregl.setRTLTextPlugin === "function" && (!maplibregl.getRTLTextPluginStatus || maplibregl.getRTLTextPluginStatus() === "unavailable")) {
      maplibregl.setRTLTextPlugin(
        "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.3.0/dist/mapbox-gl-rtl-text.js",
        true
      );
    }
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DARK_BASEMAP,
      center: [35.8555, 32.5365],
      zoom: 15.2,
      pitch: 54,
      bearing: -18,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");

    map.on("load", () => {
      mapReadyRef.current = true;

      map.addSource("sat-imagery", {
        type: "raster",
        tiles: [
          "https://mt0.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
          "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
          "https://mt2.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
          "https://mt3.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        ],
        tileSize: 256,
        maxzoom: 19,
      });
      map.addLayer({
        id: "layer-satellite",
        type: "raster",
        source: "sat-imagery",
        layout: { visibility: "none" },
        paint: { "raster-opacity": 1.0, "raster-brightness-max": 0.96 },
      });

      map.addSource("terrain-imagery-en", {
        type: "raster",
        tiles: [
          "https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
          "https://mt1.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
          "https://mt2.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
          "https://mt3.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
        ],
        tileSize: 256,
        maxzoom: 19,
      });
      map.addLayer({
        id: "layer-terrain-en",
        type: "raster",
        source: "terrain-imagery-en",
        layout: { visibility: "none" },
        paint: { "raster-opacity": 1.0, "raster-contrast": 0.08 },
      });

      map.addSource("terrain-imagery-ar", {
        type: "raster",
        tiles: [
          "https://mt0.google.com/vt/lyrs=p&hl=ar&x={x}&y={y}&z={z}",
          "https://mt1.google.com/vt/lyrs=p&hl=ar&x={x}&y={y}&z={z}",
          "https://mt2.google.com/vt/lyrs=p&hl=ar&x={x}&y={y}&z={z}",
          "https://mt3.google.com/vt/lyrs=p&hl=ar&x={x}&y={y}&z={z}",
        ],
        tileSize: 256,
        maxzoom: 19,
      });
      map.addLayer({
        id: "layer-terrain-ar",
        type: "raster",
        source: "terrain-imagery-ar",
        layout: { visibility: "none" },
        paint: { "raster-opacity": 1.0, "raster-contrast": 0.08 },
      });

      map.addSource("env-zones", { type: "geojson", data: EMPTY_FC });
      map.addSource("nabd-streets", { type: "geojson", data: EMPTY_FC });
      map.addSource("nabd-buildings", { type: "geojson", data: EMPTY_FC });
      map.addSource("nabd-services", { type: "geojson", data: EMPTY_FC });
      map.addSource("painted-zones", { type: "geojson", data: EMPTY_FC });
      map.addSource("pop-surges", { type: "geojson", data: EMPTY_FC });
      map.addSource("closed-roads", { type: "geojson", data: EMPTY_FC });
      map.addSource("brush-cursor", { type: "geojson", data: EMPTY_FC });
      map.addSource("illusions-layer", { type: "geojson", data: EMPTY_FC });
      map.addSource("ripple-lines", { type: "geojson", data: EMPTY_FC });
      map.addSource("optimal-sites", { type: "geojson", data: EMPTY_FC });
      map.addSource("pinned-a", { type: "geojson", data: EMPTY_FC });
      map.addSource("injection-pin", { type: "geojson", data: EMPTY_FC });

      map.addLayer({
        id: "layer-env-fill",
        type: "fill",
        source: "env-zones",
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: {
          "fill-color": [
            "match", ["get", "zone_type"],
            "park", "#15803d",
            "water", "#0369a1",
            "wetland", "#115e59",
            "recreation", "#6d28d9",
            "tourism", "#a21caf",
            "industrial", "#78350f",
            "cemetery", "#475569",
            "#15803d",
          ],
          "fill-opacity": [
            "match", ["get", "zone_type"],
            "water", 0.62,
            "park", 0.50,
            "wetland", 0.52,
            0.38,
          ],
        },
      });
      map.addLayer({
        id: "layer-env-line",
        type: "line",
        source: "env-zones",
        paint: {
          "line-color": [
            "match", ["get", "zone_type"],
            "park", "#4ade80",
            "water", "#38bdf8",
            "wetland", "#2dd4bf",
            "recreation", "#a78bfa",
            "tourism", "#e879f9",
            "industrial", "#b45309",
            "#94a3b8",
          ],
          "line-width": [
            "match", ["get", "zone_type"],
            "water", 3.2,
            2.1,
          ],
          "line-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "layer-env-points",
        type: "circle",
        source: "env-zones",
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 6.5,
          "circle-color": [
            "match", ["get", "zone_type"],
            "tourism", "#e879f9",
            "recreation", "#8b5cf6",
            "park", "#22c55e",
            "water", "#0284c7",
            "#e879f9",
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.addLayer({
        id: "layer-streets",
        type: "line",
        source: "nabd-streets",
        paint: {
          "line-color": [
            "match", ["get", "highway"],
            "primary", "#f59e0b",
            "secondary", "#38bdf8",
            "tertiary", "#0ea5e9",
            "#334155",
          ],
          "line-width": ["match", ["get", "highway"], "primary", 3.2, "secondary", 2.4, "tertiary", 1.7, 1.0],
          "line-opacity": 0.78,
        },
      });

      map.addLayer({
        id: "layer-painted-fill",
        type: "fill",
        source: "painted-zones",
        paint: { "fill-color": ["get", "color"], "fill-opacity": 0.14 },
      });
      map.addLayer({
        id: "layer-painted-line",
        type: "line",
        source: "painted-zones",
        paint: { "line-color": ["get", "color"], "line-width": 2, "line-dasharray": [4, 2] },
      });

      map.addLayer({
        id: "layer-pop-surges",
        type: "fill",
        source: "pop-surges",
        paint: { "fill-color": "#10b981", "fill-opacity": 0.32, "fill-outline-color": "#6ee7b7" },
      });

      map.addLayer({
        id: "layer-buildings-3d",
        type: "fill-extrusion",
        source: "nabd-buildings",
        paint: {
          "fill-extrusion-color": [
            "case",
            ["!=", ["coalesce", ["get", "override_color"], ""], ""],
            ["get", "override_color"],
            [
              "match", ["get", "dominant_demo"],
              "students", "#2e365c",
              "commuters", "#2c3148",
              "families", "#232a46",
              "#262d47",
            ],
          ],
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.86,
        },
      });

      map.addLayer({
        id: "layer-buildings-sat-fill",
        type: "fill",
        source: "nabd-buildings",
        layout: { visibility: "none" },
        paint: {
          "fill-color": [
            "case",
            ["!=", ["coalesce", ["get", "override_color"], ""], ""],
            ["get", "override_color"],
            "#000000",
          ],
          "fill-opacity": [
            "case",
            ["!=", ["coalesce", ["get", "override_color"], ""], ""],
            0.22,
            0.01,
          ],
        },
      });
      map.addLayer({
        id: "layer-buildings-sat-outline",
        type: "line",
        source: "nabd-buildings",
        layout: { visibility: "none" },
        paint: {
          "line-color": [
            "case",
            ["!=", ["coalesce", ["get", "override_color"], ""], ""],
            ["get", "override_color"],
            "rgba(255,255,255,0)",
          ],
          "line-width": [
            "case",
            ["!=", ["coalesce", ["get", "override_color"], ""], ""],
            2.2,
            0,
          ],
          "line-opacity": 0.95,
        },
      });

      map.addLayer({
        id: "layer-brush-fill",
        type: "fill",
        source: "brush-cursor",
        paint: { "fill-color": ["get", "color"], "fill-opacity": 0.14 },
      });
      map.addLayer({
        id: "layer-brush-ring",
        type: "line",
        source: "brush-cursor",
        paint: { "line-color": ["get", "color"], "line-width": 2.4 },
      });

      map.addLayer({
        id: "layer-services",
        type: "circle",
        source: "nabd-services",
        paint: {
          "circle-radius": 4.6,
          "circle-color": [
            "match", ["get", "category"],
            "university", "#a855f7",
            "pharmacy", "#10b981",
            "cafe", "#f97316",
            "barber", "#38bdf8",
            "beauty_salon", "#ec4899",
            "grocery", "#84cc16",
            "bakery", "#eab308",
            "clinic", "#ef4444",
            "#cbd5e1",
          ],
          "circle-stroke-width": 1.3,
          "circle-stroke-color": "#020617",
        },
      });

      map.addLayer({
        id: "layer-illusions",
        type: "circle",
        source: "illusions-layer",
        paint: {
          "circle-radius": 8.5, "circle-color": "#f43f5e",
          "circle-opacity": 0.72, "circle-stroke-width": 2, "circle-stroke-color": "#fecdd3",
        },
      });

      map.addLayer({
        id: "layer-closed-roads",
        type: "circle",
        source: "closed-roads",
        paint: { "circle-radius": 9.5, "circle-color": "#e11d48", "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff" },
      });

      map.addLayer({
        id: "layer-ripple-glow",
        type: "line",
        source: "ripple-lines",
        paint: { "line-color": "#f43f5e", "line-width": 7, "line-blur": 5, "line-opacity": 0.34 },
      });
      map.addLayer({
        id: "layer-ripples",
        type: "line",
        source: "ripple-lines",
        paint: { "line-color": "#fb923c", "line-width": 2.4, "line-dasharray": [2, 2], "line-opacity": 0.92 },
      });

      map.addLayer({
        id: "layer-optimal",
        type: "circle",
        source: "optimal-sites",
        paint: { "circle-radius": 9.5, "circle-color": "#10b981", "circle-stroke-width": 2.5, "circle-stroke-color": "#ffffff" },
      });

      map.addLayer({
        id: "layer-pinned-a",
        type: "circle",
        source: "pinned-a",
        paint: { "circle-radius": 11, "circle-color": "#a855f7", "circle-stroke-width": 3, "circle-stroke-color": "#ffffff" },
      });

      map.addLayer({
        id: "layer-injection-halo",
        type: "circle",
        source: "injection-pin",
        paint: {
          "circle-radius": 28, "circle-color": "#22d3ee", "circle-opacity": 0.16,
          "circle-stroke-width": 1.6, "circle-stroke-color": "#22d3ee",
          "circle-pitch-alignment": "map",
        },
      });

      const beaconEl = document.createElement("div");
      beaconEl.className = "drag-beacon";
      beaconEl.title = "Drag to fine-tune location";
      beaconEl.innerHTML = '<div class="drag-beacon-ring"></div><div class="drag-beacon-core"></div>';
      const marker = new maplibregl.Marker({ element: beaconEl, draggable: true, anchor: "center" })
        .setLngLat([35.8555, 32.5365])
        .addTo(map);
      markerRef.current = marker;

      marker.on("dragstart", () => {
        isDraggingRef.current = true;
        beaconEl.classList.add("dragging");
      });
      marker.on("drag", () => {
        const { lat, lng } = marker.getLngLat();
        updateMapSource("injection-pin", {
          type: "FeatureCollection",
          features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lng, lat] }, properties: {} }],
        });
        const now = Date.now();
        if (now - lastDragSimRef.current > 240) {
          lastDragSimRef.current = now;
          void runSimulation(lat, lng, { silent: true });
        }
      });
      marker.on("dragend", () => {
        isDraggingRef.current = false;
        justDraggedRef.current = true;
        beaconEl.classList.remove("dragging");
        const { lat, lng } = marker.getLngLat();
        void runSimulation(lat, lng);
        setTimeout(() => { justDraggedRef.current = false; }, 160);
      });

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mouseenter", "layer-services", (e: any) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as Record<string, string>;
        const isArNow = stateRef.current.lang === "ar";
        popup
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="color:#0f172a;font-size:12px;font-family:sans-serif;direction:${isArNow ? "rtl" : "ltr"};"><strong>${p.name}</strong><br/>${isArNow ? p.label_ar : p.category}</div>`
          )
          .addTo(map);
      });
      map.on("mouseleave", "layer-services", () => popup.remove());

      const showEnvPopup = (e: any) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as Record<string, any>;
        const isArNow = stateRef.current.lang === "ar";
        const badge = p.is_restricted
          ? `<span style="color:#dc2626;font-weight:700;"> · ${isArNow ? "محظور للبناء" : "Restricted"}</span>`
          : "";
        popup
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="color:#0f172a;font-size:12px;font-family:sans-serif;direction:${isArNow ? "rtl" : "ltr"};"><strong>${p.name}</strong><br/>${isArNow ? p.label_ar : (p.label_en || p.zone_type)}${badge}</div>`
          )
          .addTo(map);
      };
      map.on("mouseenter", "layer-env-fill", showEnvPopup);
      map.on("mouseenter", "layer-env-points", showEnvPopup);
      map.on("mouseleave", "layer-env-fill", () => popup.remove());
      map.on("mouseleave", "layer-env-points", () => popup.remove());

      map.on("mousemove", (e: any) => {
        const s = stateRef.current;
        if (s.activeTool !== "paint") return;
        const meta = ZONE_LABELS[s.paintPreset] ?? { color: "#a855f7" };
        updateMapSource("brush-cursor", {
          type: "FeatureCollection",
          features: [{
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [makeCirclePolygon(e.lngLat.lat, e.lngLat.lng, s.paintRadius, 32)] },
            properties: { color: meta.color },
          }],
        });
      });
      map.on("mouseout", () => updateMapSource("brush-cursor", EMPTY_FC));

      map.on("click", (e: any) => {
        if (justDraggedRef.current) return;
        const s = stateRef.current;
        const { lat, lng } = e.lngLat;

        if (s.activeTool === "inject") {
          void runSimulation(lat, lng);
          return;
        }
        if (s.activeTool === "paint") {
          const meta = ZONE_LABELS[s.paintPreset] ?? { ar: s.paintPreset, en: s.paintPreset, color: "#a855f7" };
          const nextSb: SandboxState = {
            ...s.sandbox,
            paintedZones: [
              ...s.sandbox.paintedZones,
              {
                id: `z_${Date.now()}`,
                lat,
                lon: lng,
                radius_m: s.paintRadius,
                preset: s.paintPreset,
                label: s.lang === "ar" ? meta.ar : meta.en,
                color: meta.color,
              },
            ],
          };
          setSandbox(nextSb);
          if (s.clickedPoint) void runSimulation(s.clickedPoint.lat, s.clickedPoint.lon, { sb: nextSb });
          return;
        }
        if (s.activeTool === "close_road") {
          const nextSb: SandboxState = {
            ...s.sandbox,
            closedRoads: [...s.sandbox.closedRoads, { id: `r_${Date.now()}`, lat, lon: lng }],
          };
          setSandbox(nextSb);
          if (s.clickedPoint) void runSimulation(s.clickedPoint.lat, s.clickedPoint.lon, { sb: nextSb });
          return;
        }
        if (s.activeTool === "demolish") {
          const activeBLayer =
            map.getLayoutProperty("layer-buildings-3d", "visibility") !== "none"
              ? "layer-buildings-3d"
              : "layer-buildings-sat-fill";
          const feats = map.queryRenderedFeatures(e.point, { layers: [activeBLayer] });
          const blkId = feats?.[0]?.properties?.id ? String(feats[0].properties.id) : null;
          if (!blkId) return;
          const exists = s.sandbox.demolishedBlocks.includes(blkId);
          const nextDemo = exists
            ? s.sandbox.demolishedBlocks.filter((b) => b !== blkId)
            : [...s.sandbox.demolishedBlocks, blkId];
          const nextSb: SandboxState = { ...s.sandbox, demolishedBlocks: nextDemo };
          setSandbox(nextSb);
          if (s.clickedPoint) void runSimulation(s.clickedPoint.lat, s.clickedPoint.lon, { sb: nextSb });
          return;
        }
        if (s.activeTool === "add_pop") {
          const nextSb: SandboxState = {
            ...s.sandbox,
            popSurges: [...s.sandbox.popSurges, { id: `p_${Date.now()}`, lat, lon: lng, pop: 1500 }],
          };
          setSandbox(nextSb);
          if (s.clickedPoint) void runSimulation(s.clickedPoint.lat, s.clickedPoint.lon, { sb: nextSb });
        }
      });

      void loadArea("irbid-yarmouk");
    });

    return () => {
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
      mapReadyRef.current = false;
    };
  }, [loadArea, runSimulation, updateMapSource]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    map.getCanvas().style.cursor = activeTool === "inject" ? "" : "crosshair";
    if (activeTool !== "paint") updateMapSource("brush-cursor", EMPTY_FC);
    if (markerRef.current) {
      markerRef.current.setDraggable(activeTool === "inject");
      markerRef.current.getElement().style.pointerEvents = activeTool === "inject" ? "auto" : "none";
    }
  }, [activeTool, updateMapSource]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) return;
    const setVis = (id: string, show: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", show ? "visible" : "none");
    };
    const isCyber = mapStyle === "cyber";
    const isSat = mapStyle === "satellite";
    const isTopo = mapStyle === "terrain";

    setVis("layer-satellite", isSat);
    setVis("layer-terrain-en", isTopo && lang === "en");
    setVis("layer-terrain-ar", isTopo && lang === "ar");

    setVis("layer-buildings-3d", layersVis.buildings && isCyber);
    setVis("layer-buildings-sat-fill", layersVis.buildings && !isCyber);
    setVis("layer-buildings-sat-outline", layersVis.buildings && !isCyber);

    setVis("layer-env-fill", layersVis.envZones);
    setVis("layer-env-line", layersVis.envZones);
    setVis("layer-env-points", layersVis.envZones);

    setVis("layer-streets", layersVis.streets);
    setVis("layer-services", layersVis.services);
    setVis("layer-illusions", layersVis.illusions);

    if (map.getLayer("layer-streets")) {
      if (isTopo) {
        map.setPaintProperty("layer-streets", "line-color", [
          "interpolate",
          ["linear"],
          ["coalesce", ["get", "slope_pct"], 0],
          0, "#059669",
          3, "#d97706",
          7, "#dc2626",
        ]);
        map.setPaintProperty("layer-streets", "line-opacity", 0.72);
      } else {
        map.setPaintProperty("layer-streets", "line-color", [
          "match", ["get", "highway"],
          "primary", "#f59e0b",
          "secondary", "#38bdf8",
          "tertiary", "#0ea5e9",
          "#334155",
        ]);
        map.setPaintProperty("layer-streets", "line-opacity", isSat ? 0.45 : 0.78);
      }
    }
  }, [layersVis, mapStyle, lang]);

  const handleToggleIllusions = async (checked: boolean, catOverride?: string) => {
    setLayersVis((prev) => ({ ...prev, illusions: checked }));
    if (!checked) return;
    setLoadingText(
      lang === "ar"
        ? "جارٍ مسح المباني المعزولة شبكياً (وهم القرب)..."
        : "Scanning Relate graph for Topological Illusions (1.6x+ circuity)..."
    );
    try {
      const targetCat = catOverride ?? (useCustomDna ? "pharmacy" : category);
      const data = await illusionsApi(activeSlug, targetCat, sandbox);
      setIllusionsData(data);
      updateMapSource("illusions-layer", {
        type: "FeatureCollection",
        features: data.illusions.map((ill) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [ill.lon, ill.lat] },
          properties: { circuity: ill.circuity_index },
        })),
      });
    } finally {
      setLoadingText(null);
    }
  };

  const handleSynthesizeDna = async (nameOverride?: string) => {
    const targetName = (nameOverride ?? customDna.name).trim();
    if (!targetName) return;
    setSynthesizingDna(true);
    setErrorText(null);
    try {
      let savedAi: Record<string, string> = {};
      try {
        const raw = localStorage.getItem("nabd_ai_config_v1");
        if (raw) savedAi = JSON.parse(raw);
      } catch {}
      const synthesized = await synthesizeDnaApi(targetName, savedAi);
      setCustomDna(synthesized);
      setUseCustomDna(true);
      if (clickedPoint) {
        await runSimulation(clickedPoint.lat, clickedPoint.lon, { custom: true, dnaOverride: synthesized });
      }
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Failed to synthesize facility physics");
    } finally {
      setSynthesizingDna(false);
    }
  };

  const handleOptimize = async () => {
    setLoadingText(
      lang === "ar"
        ? "جارٍ البحث عن أفضل 5 مواقع رياضياً مع استبعاد المناطق المحظورة..."
        : "Running Law 6 Spatial Optimizer across all valid junctions..."
    );
    try {
      const sites = await optimizeApi(activeSlug, category, timeOfDay, sandbox, useCustomDna ? customDna : undefined);
      setOptimalSites(sites);
      updateMapSource("optimal-sites", {
        type: "FeatureCollection",
        features: sites.map((st, idx) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [st.lon, st.lat] },
          properties: { rank: idx + 1 },
        })),
      });
      if (sites[0]) await runSimulation(sites[0].lat, sites[0].lon);
    } finally {
      setLoadingText(null);
    }
  };

  const handleSyncLive = async () => {
    const map = mapRef.current;
    if (!map) return;
    const c = map.getCenter();
    setLoadingText(
      lang === "ar"
        ? `جارٍ سحب الشوارع والمباني والتضاريس (نصف قطر ${syncRadius}م) وبناء قاعدة Relate حية...`
        : `Syncing live OSM streets, buildings & terrain (${syncRadius}m radius) into a new Relate (.rl) graph...`
    );
    setErrorText(null);
    try {
      const out = await syncLiveAreaApi(c.lat, c.lng, syncRadius);
      setCatalog(await fetchCatalog());
      await loadArea(out.slug);
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Live OSM sync failed");
    } finally {
      setLoadingText(null);
    }
  };

  const handleAiMapAction = (action: AiMapAction) => {
    if (action.type === "fly_and_inject" && action.lat != null && action.lon != null) {
      setCategory(action.category);
      setUseCustomDna(false);
      if (action.optimal_sites?.length) {
        setOptimalSites(action.optimal_sites);
        updateMapSource("optimal-sites", {
          type: "FeatureCollection",
          features: action.optimal_sites.map((st, idx) => ({
            type: "Feature",
            geometry: { type: "Point", coordinates: [st.lon, st.lat] },
            properties: { rank: idx + 1 },
          })),
        });
      }
      mapRef.current?.flyTo({ center: [action.lon, action.lat], zoom: 16.0, duration: 1000 });
      void runSimulation(action.lat, action.lon, { cat: action.category, custom: false });
      setRightOpen(true);
    } else if (action.type === "show_illusions") {
      setCategory(action.category);
      void handleToggleIllusions(true, action.category);
    }
  };

  const updateSandboxAndResim = (nextSb: SandboxState) => {
    setSandbox(nextSb);
    if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { sb: nextSb });
  };

  const sandboxCount =
    sandbox.paintedZones.length +
    sandbox.closedRoads.length +
    sandbox.demolishedBlocks.length +
    sandbox.popSurges.length;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      } else if (e.key === "Escape") {
        setPaletteOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleCommitDecision = async (
    status: "APPROVED" | "REJECTED" | "WATCHLIST",
    reason: string,
    blockOwnership: boolean
  ) => {
    const pid = simResult?.parcel_context?.parcel_id;
    if (!pid || !simResult) return;
    setDecisionBusy(true);
    setDecisionFeedback(null);
    try {
      await createAgentDecisionApi(activeSlug, {
        parcel_id: pid,
        category: simResult.injection.category,
        status,
        reason,
        actor: "studio_planner",
        metrics: {
          gain_J: simResult.composite_network_gain_J,
          p50_visits: simResult.monte_carlo_envelope.p50_base,
          viability_pct: simResult.monte_carlo_envelope.viability_probability_pct,
        },
        block_ownership: blockOwnership,
      });
      // Reload 3D layer so parcel immediately crystallizes in emerald/crimson on map
      const freshArea = await fetchAreaLayers(activeSlug);
      setAreaData(freshArea);
      setTraceRefresh((n) => n + 1);
      if (blockOwnership) {
        setDecisionFeedback(
          lang === "ar"
            ? `✓ حُفظ القرار (COMMIT) وحُجبت ملكية ${pid} — جارٍ ترشيح البديل التالي...`
            : `✓ COMMITTED & blocked ${pid} — Law 6 Optimizer rerouting to next best parcel...`
        );
        await handleOptimize();
      } else {
        setDecisionFeedback(
          lang === "ar"
            ? `✓ حُفظ القرار (${status}) دائماً داخل ${activeSlug}.rl عبر COMMIT`
            : `✓ Persisted ${status} on ${pid} inside ${activeSlug}.rl (ACID COMMIT)`
        );
        if (clickedPoint) {
          await runSimulation(clickedPoint.lat, clickedPoint.lon, { silent: true });
        }
      }
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : "Failed to persist decision");
    } finally {
      setDecisionBusy(false);
    }
  };

  const runGuidedFlight = async (flight: "irbid_acid" | "manhattan_pulse" | "agent_memory") => {
    setErrorText(null);
    if (flight === "irbid_acid") {
      setFlightBanner(
        lang === "ar"
          ? "رحلة 1/3 · مسح الوهم الطوبولوجي حول جامعة اليرموك وحقن عيادة بمعاملة ACID ROLLBACK..."
          : "Proof Flight 1/3 · Exposing 1.6x+ topological illusions & executing live ACID ROLLBACK in Relate..."
      );
      setLeftOpen(false);
      setRightOpen(true);
      setCategory("clinic");
      setUseCustomDna(false);
      setTimeOfDay("midday");
      await loadArea("irbid-yarmouk");
      await handleToggleIllusions(true, "clinic");
      await runSimulation(32.5365, 35.8555, { slug: "irbid-yarmouk", cat: "clinic", tod: "midday", custom: false });
      setRelateOpen(true);
      setTimeout(() => setFlightBanner(null), 6500);
    } else if (flight === "manhattan_pulse") {
      setFlightBanner(
        lang === "ar"
          ? "رحلة 2/3 · مانهاتن (Midtown): ذروة المكاتب ظهراً — راقب تحوّل إضاءة الأبراج إلى الليل بعد ثانيتين..."
          : "Proof Flight 2/3 · Manhattan Midtown: Midday office tower peak — transitioning to Night residential glow..."
      );
      setLeftOpen(false);
      setRightOpen(true);
      setCategory("cafe");
      setUseCustomDna(false);
      setTimeOfDay("midday");
      await loadArea("manhattan-midtown");
      mapRef.current?.flyTo({ center: [-73.9832, 40.7536], zoom: 15.8, pitch: 60, bearing: -24, duration: 1200 });
      await runSimulation(40.7536, -73.9832, { slug: "manhattan-midtown", cat: "cafe", tod: "midday", custom: false });
      setTimeout(() => {
        setTimeOfDay("night");
        setFlightBanner(
          lang === "ar"
            ? "رحلة 2/3 · الفترة الليلية: خفوت أبراج المكاتب وتوهّج الكتلة السكنية وإعادة حساب الجاذبية!"
            : "Proof Flight 2/3 · Night Shift active: Office towers dimmed, residential density illuminated & Huff gravity updated!"
        );
        void runSimulation(40.7536, -73.9832, { slug: "manhattan-midtown", cat: "cafe", tod: "night", custom: false, silent: true });
        setTimeout(() => setFlightBanner(null), 5500);
      }, 2600);
    } else if (flight === "agent_memory") {
      setFlightBanner(
        lang === "ar"
          ? "رحلة 3/3 · محسّن العقارات Law 6 اختار أفضل قسيمة — اضغط «رفض وحجب» لتشهد الحفظ بـ COMMIT والقفز للبديل!"
          : "Proof Flight 3/3 · Law 6 Optimizer selected #1 buildable (:Parcel) — press Reject & Block to test COMMIT rerouting!"
      );
      setLeftOpen(false);
      setRightOpen(true);
      await handleOptimize();
      setRelateOpen(true);
      setTimeout(() => setFlightBanner(null), 7000);
    }
  };

  const paletteActions: PaletteAction[] = [
    {
      id: "flight-irbid",
      group: "flights",
      titleEn: "Flight 1 · Irbid Topological Illusion + Live ACID ROLLBACK",
      titleAr: "رحلة 1 · إربد: وهم القرب + إثبات ROLLBACK الحي",
      descEn: "Flies to Yarmouk Univ St, exposes 1.6x+ isolated blocks, injects a Clinic & opens Relate Trace.",
      descAr: "يطير لشارع الجامعة، يكشف المباني المعزولة شبكياً، يحقن عيادة ويفتح سجل Cypher الحي.",
      badge: "ACID",
      icon: "flight",
      run: () => void runGuidedFlight("irbid_acid"),
    },
    {
      id: "flight-manhattan",
      group: "flights",
      titleEn: "Flight 2 · Manhattan Skyscrapers Volumetric Day → Night Pulse",
      titleAr: "رحلة 2 · مانهاتن: نبض ناطحات السحاب بين الظهر والليل",
      descEn: "Loads manhattan-midtown.rl (97 parks, 3.35M m² GFA) & transitions live from midday office peak to night.",
      descAr: "يحمّل مانهاتن (97 حديقة و3.35M م²) وينتقل حيّاً من ذروة المكاتب ظهراً إلى الليل.",
      badge: "3D NYC",
      icon: "flight",
      run: () => void runGuidedFlight("manhattan_pulse"),
    },
    {
      id: "flight-memory",
      group: "flights",
      titleEn: "Flight 3 · Law 6 Parcel Optimizer + Persistent Agent Memory",
      titleAr: "رحلة 3 · محسّن العقارات Law 6 + ذاكرة القرارات الدائمة",
      descEn: "Ranks real buildable (:Parcel) sites from Relate indexes — press Reject & Block to watch instant rerouting.",
      descAr: "يرشّح عقارات حقيقية مفهرَسة من Relate — اضغط «رفض وحجب» لتشاهد القفز للبديل التالي.",
      badge: "COMMIT",
      icon: "flight",
      run: () => void runGuidedFlight("agent_memory"),
    },
    {
      id: "city-irbid",
      group: "cities",
      titleEn: "Switch City · Irbid — Yarmouk & University St",
      titleAr: "تبديل المدينة · إربد — اليرموك وشارع الجامعة",
      descEn: "2,563 nodes · 1,246 3D parcels · 557m–675m real DEM slopes.",
      descAr: "2,563 عقدة · 1,246 عقار 3D · تضاريس حقيقية 557–675م.",
      badge: "2.4 MB",
      icon: "city",
      run: () => void loadArea("irbid-yarmouk"),
    },
    {
      id: "city-manhattan",
      group: "cities",
      titleEn: "Switch City · Manhattan — Midtown & Bryant Park (NYC)",
      titleAr: "تبديل المدينة · مانهاتن — ميدتاون وبراينت بارك (نيويورك)",
      descEn: "5,206 nodes · 1,297 skyscraper parcels · 97 embedded parks & landmarks.",
      descAr: "5,206 عقدة · 1,297 ناطحة سحاب · 97 حديقة ومعلماً مدمجاً.",
      badge: "6.5 MB",
      icon: "city",
      run: () => void loadArea("manhattan-midtown"),
    },
    {
      id: "eng-trace",
      group: "engine",
      titleEn: "Toggle Relate Glass-Box (Live Trace, Cypher Console & Memory)",
      titleAr: "فتح / إغلاق الصندوق الزجاجي (سجل Relate وكونسول Cypher)",
      descEn: "Inspect millisecond Cypher queries, constraints, indexes & persisted AgentDecision nodes.",
      descAr: "اعرض استعلامات Cypher الحية وزمنها بالميلي ثانية والفهارس وذاكرة الوكلاء.",
      badge: "TRACE",
      icon: "trace",
      run: () => setRelateOpen((v) => !v),
    },
    {
      id: "eng-midday",
      group: "engine",
      titleEn: "Volumetric Pulse · Midday Peak (Office & Campus Surge)",
      titleAr: "النبض الحجمي · ذروة الظهر (مكاتب وجامعات)",
      descEn: "Illuminates daytime commercial/office towers & recomputes Huff Gravity.",
      descAr: "يضيء الأبراج التجارية والمكتبية نهاراً ويعيد حساب الجاذبية.",
      icon: "day",
      run: () => {
        setTimeOfDay("midday");
        if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { tod: "midday" });
      },
    },
    {
      id: "eng-night",
      group: "engine",
      titleEn: "Volumetric Pulse · Night Shift (Residential Glow)",
      titleAr: "النبض الحجمي · الفترة الليلية (توهّج سكني)",
      descEn: "Dims office towers & illuminates night-time residential density.",
      descAr: "يخفت أبراج المكاتب ويضيء الكثافة السكنية الليلية.",
      icon: "night",
      run: () => {
        setTimeOfDay("night");
        if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { tod: "night" });
      },
    },
    {
      id: "eng-opt",
      group: "engine",
      titleEn: "Run Law 6 Spatial Parcel Optimizer",
      titleAr: "تشغيل محسّن العقارات المكاني (القانون 6)",
      descEn: "Queries indexed Relate (:Parcel) sites & ranks top 5 buildable locations.",
      descAr: "يستعلم عن العقارات القابلة للبناء من فهارس Relate ويرتّب أفضل 5 مواقع.",
      icon: "opt",
      run: () => void handleOptimize(),
    },
    {
      id: "eng-zen",
      group: "engine",
      titleEn: "Toggle 85/15 Zen Map Focus (Hide/Show Side Drawers)",
      titleAr: "وضع التركيز السينمائي 85/15 (إخفاء/إظهار القوائم)",
      descEn: "Maximize the 3D city viewport for clean spatial exploration.",
      descAr: "توسيع الخريطة ثلاثية الأبعاد بملء الشاشة.",
      icon: "zen",
      run: () => {
        const anyOpen = leftOpen || rightOpen;
        setLeftOpen(!anyOpen);
        setRightOpen(!anyOpen);
      },
    },
    {
      id: "eng-lang",
      group: "engine",
      titleEn: "Switch Language (English / العربية)",
      titleAr: "تبديل اللغة (العربية / English)",
      descEn: "Toggle full bilingual RTL/LTR interface.",
      descAr: "التبديل الفوري بين الواجهة العربية والإنجليزية.",
      icon: "lang",
      run: () => setLang((l) => (l === "en" ? "ar" : "en")),
    },
  ];

  const liveTxState = simResult?.relate_transaction?.tx_state ?? "READY";
  const liveTxMs = simResult?.relate_transaction?.elapsed_ms;
  const isNightMode = timeOfDay === "night" || timeOfDay === "evening";

  return (
    <div className="studio-root">
      <div ref={mapContainerRef} className="map-container" />

      <TopBar
        lang={lang}
        onToggleLang={() => setLang((l) => (l === "en" ? "ar" : "en"))}
        areaData={areaData}
        catalog={catalog}
        activeSlug={activeSlug}
        onSelectArea={(slug) => void loadArea(slug)}
        syncRadius={syncRadius}
        onChangeSyncRadius={setSyncRadius}
        onSyncLive={() => void handleSyncLive()}
        onFlyToLocation={(lat, lon, zoom) => {
          mapRef.current?.flyTo({ center: [lon, lat], zoom: zoom ?? 15.2, duration: 1500 });
        }}
        is3D={is3D}
        onToggle3D={() => {
          const next = !is3D;
          setIs3D(next);
          mapRef.current?.easeTo({ pitch: next ? 54 : 0, bearing: next ? -18 : 0, duration: 700 });
        }}
        mapStyle={mapStyle}
        onChangeMapStyle={setMapStyle}
        leftOpen={leftOpen}
        onToggleLeft={() => setLeftOpen((v) => !v)}
        rightOpen={rightOpen}
        onToggleRight={() => setRightOpen((v) => !v)}
        aiOpen={aiOpen}
        onToggleAi={() => setAiOpen((v) => !v)}
        loading={Boolean(loadingText)}
      />

      <ControlDrawer
        lang={lang}
        open={leftOpen}
        onClose={() => setLeftOpen(false)}
        catalog={catalog}
        category={category}
        onChangeCategory={(c) => {
          setCategory(c);
          if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { cat: c });
        }}
        useCustomDna={useCustomDna}
        onToggleCustomDna={(v) => {
          setUseCustomDna(v);
          if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { custom: v });
        }}
        customDna={customDna}
        onChangeCustomDna={setCustomDna}
        onRunCustomDna={() => clickedPoint && void runSimulation(clickedPoint.lat, clickedPoint.lon)}
        onSynthesizeDna={(n) => void handleSynthesizeDna(n)}
        synthesizingDna={synthesizingDna}
        attractionMult={attractionMult}
        onChangeAttractionMult={(v) => {
          setAttractionMult(v);
          if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { attr: v, silent: true });
        }}
        capacityMult={capacityMult}
        onChangeCapacityMult={(v) => {
          setCapacityMult(v);
          if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { cap: v, silent: true });
        }}
        timeOfDay={timeOfDay}
        onChangeTimeOfDay={(t) => {
          setTimeOfDay(t);
          if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { tod: t });
        }}
        onOptimize={() => void handleOptimize()}
        optimalSites={optimalSites}
        onSelectOptimalSite={(st) => {
          mapRef.current?.flyTo({ center: [st.lon, st.lat], zoom: 16.3, duration: 800 });
          void runSimulation(st.lat, st.lon);
        }}
        paintPreset={paintPreset}
        onChangePaintPreset={setPaintPreset}
        paintRadius={paintRadius}
        onChangePaintRadius={setPaintRadius}
        onSelectTool={setActiveTool}
        sandbox={sandbox}
        onRemoveZone={(id) =>
          updateSandboxAndResim({ ...sandbox, paintedZones: sandbox.paintedZones.filter((z) => z.id !== id) })
        }
        onRemoveClosedRoad={(id) =>
          updateSandboxAndResim({ ...sandbox, closedRoads: sandbox.closedRoads.filter((r) => r.id !== id) })
        }
        onRemovePopSurge={(id) =>
          updateSandboxAndResim({ ...sandbox, popSurges: sandbox.popSurges.filter((p) => p.id !== id) })
        }
        onRestoreDemolished={() => updateSandboxAndResim({ ...sandbox, demolishedBlocks: [] })}
        layersVis={layersVis}
        onChangeLayersVis={setLayersVis}
        onToggleIllusions={(checked) => void handleToggleIllusions(checked)}
        illusionsData={illusionsData}
        loading={Boolean(loadingText)}
      />

      <TelemetryDrawer
        lang={lang}
        open={rightOpen}
        onClose={() => setRightOpen(false)}
        simResult={simResult}
        scenario={scenario}
        onChangeScenario={setScenario}
        pinnedA={pinnedA}
        onPinCurrentAsA={() => {
          if (simResult && clickedPoint) {
            setPinnedA({
              label: lang === "ar" ? simResult.injection.label_ar : simResult.injection.label_en,
              lat: clickedPoint.lat,
              lon: clickedPoint.lon,
              result: simResult,
            });
          }
        }}
        onClearPinA={() => setPinnedA(null)}
        errorText={errorText}
        onCommitDecision={handleCommitDecision}
        decisionBusy={decisionBusy}
        decisionFeedback={decisionFeedback}
        onOpenRelateTrace={() => setRelateOpen(true)}
      />

      <AiStrategistPanel
        lang={lang}
        open={aiOpen}
        onClose={() => setAiOpen(false)}
        activeSlug={activeSlug}
        clickedPoint={clickedPoint}
        areaCenter={areaData ? { lat: areaData.meta.center_lat, lon: areaData.meta.center_lon } : null}
        category={category}
        timeOfDay={timeOfDay}
        sandbox={sandbox}
        onMapAction={handleAiMapAction}
      />

      <div className="status-toast relate-hud-bar" dir={lang === "ar" ? "rtl" : "ltr"}>
        <button
          className={`hud-pill hud-relate ${relateOpen ? "active" : ""}`}
          onClick={() => setRelateOpen((v) => !v)}
          title={lang === "ar" ? "فتح الصندوق الزجاجي لمحرك Relate" : "Open Relate Live Trace & Cypher Console"}
        >
          <span className="tx-dot" />
          <Database size={12} />
          <span className="mono">{liveTxState}</span>
          {liveTxMs != null && <span className="mono tx-ms">{liveTxMs.toFixed(2)}ms</span>}
          <Terminal size={11} />
        </button>

        <button
          className="hud-pill hud-time"
          onClick={() => {
            const nextTod = isNightMode ? "midday" : "night";
            setTimeOfDay(nextTod);
            if (clickedPoint) void runSimulation(clickedPoint.lat, clickedPoint.lon, { tod: nextTod });
          }}
          title={lang === "ar" ? "تبديل النبض الحجمي نهار / ليل" : "Toggle 3D Volumetric Day / Night Pulse"}
        >
          {isNightMode ? <Moon size={12} className="c-violet" /> : <Sun size={12} className="c-amber" />}
          <span>{isNightMode ? (lang === "ar" ? "ليل" : "Night") : lang === "ar" ? "نهار" : "Midday"}</span>
        </button>

        <button
          className="hud-pill hud-flights"
          onClick={() => setPaletteOpen(true)}
          title={lang === "ar" ? "رحلات البرهان والأوامر (Ctrl+K)" : "Guided Proof Flights & Command Palette (Ctrl+K)"}
        >
          <Sparkles size={12} />
          <span>{lang === "ar" ? "رحلات البرهان" : "Proof Flights"}</span>
          <span className="kbd-chip mono">⌘K</span>
        </button>

        <span className="hud-hint trunc">
          {loadingText ? `⚡ ${loadingText}` : TOOL_HINTS_I18N[lang][activeTool]}
        </span>
      </div>

      {flightBanner && (
        <div className="flight-banner" dir={lang === "ar" ? "rtl" : "ltr"}>
          <Sparkles size={14} className="c-emerald" />
          <span>{flightBanner}</span>
        </div>
      )}

      <RelateInspectorPanel
        lang={lang}
        open={relateOpen}
        onClose={() => setRelateOpen(false)}
        activeSlug={activeSlug}
        refreshToken={traceRefresh}
        onFlyToParcel={(lat, lon) => {
          mapRef.current?.flyTo({ center: [lon, lat], zoom: 16.4, pitch: 56, duration: 900 });
          void runSimulation(lat, lon);
          setRightOpen(true);
        }}
      />

      <CommandPalette
        lang={lang}
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        actions={paletteActions}
      />

      <ToolRail
        lang={lang}
        activeTool={activeTool}
        onSelectTool={setActiveTool}
        pinnedA={pinnedA}
        onTogglePinA={() => {
          if (pinnedA) {
            setPinnedA(null);
          } else if (simResult && clickedPoint) {
            setPinnedA({
              label: lang === "ar" ? simResult.injection.label_ar : simResult.injection.label_en,
              lat: clickedPoint.lat,
              lon: clickedPoint.lon,
              result: simResult,
            });
            setRightOpen(true);
          }
        }}
        sandboxCount={sandboxCount}
        onResetSandbox={() => updateSandboxAndResim(EMPTY_SANDBOX)}
      />
    </div>
  );
}
