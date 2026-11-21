import type {
  AiConfig,
  AreaLayersResponse,
  CatalogResponse,
  CustomDnaState,
  ChatResponse,
  GeocodeResult,
  IllusionsResponse,
  Lang,
  OptimalSite,
  SandboxState,
  SimulationResponse,
} from "./types";

export const API_BASE = "http://127.0.0.1:8001";

export function buildOverridesPayload(sandbox: SandboxState) {
  const hasAny =
    sandbox.paintedZones.length > 0 ||
    sandbox.closedRoads.length > 0 ||
    sandbox.demolishedBlocks.length > 0 ||
    sandbox.popSurges.length > 0;
  if (!hasAny) return null;
  return {
    closed_points: sandbox.closedRoads.map((r) => ({ lat: r.lat, lon: r.lon })),
    demolished_blocks: sandbox.demolishedBlocks,
    extra_population: sandbox.popSurges.map((p) => ({ lat: p.lat, lon: p.lon, pop: p.pop })),
    demographic_zones: sandbox.paintedZones.map((z) => ({
      lat: z.lat,
      lon: z.lon,
      radius_m: z.radius_m,
      preset: z.preset,
      strength: 0.9,
    })),
  };
}

export async function fetchCatalog(): Promise<CatalogResponse> {
  const r = await fetch(`${API_BASE}/api/catalog`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchAreaLayers(slug: string): Promise<AreaLayersResponse> {
  const r = await fetch(`${API_BASE}/api/area/${slug}/layers`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function syncLiveAreaApi(lat: number, lon: number, radiusM = 750) {
  const r = await fetch(`${API_BASE}/api/area/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lat,
      lon,
      radius_m: radiusM,
      label: `Live (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ status: string; slug: string }>;
}

export async function geocodeApi(q: string, lang: Lang): Promise<GeocodeResult[]> {
  const params = new URLSearchParams({ q, lang });
  const r = await fetch(`${API_BASE}/api/geocode?${params.toString()}`);
  if (!r.ok) throw new Error(await r.text());
  const d = await r.json();
  return d.results ?? [];
}

export async function simulateApi(
  slug: string,
  body: Record<string, unknown>
): Promise<SimulationResponse> {
  const r = await fetch(`${API_BASE}/api/area/${slug}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function illusionsApi(
  slug: string,
  category: string,
  sandbox: SandboxState
): Promise<IllusionsResponse> {
  const r = await fetch(`${API_BASE}/api/area/${slug}/illusions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      category,
      circuity_threshold: 1.6,
      overrides: buildOverridesPayload(sandbox),
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function optimizeApi(
  slug: string,
  category: string,
  timeOfDay: string,
  sandbox: SandboxState,
  customDna?: CustomDnaState
): Promise<OptimalSite[]> {
  const payload: Record<string, unknown> = {
    category,
    time_of_day: timeOfDay,
    top_k: 5,
    overrides: buildOverridesPayload(sandbox),
  };
  if (customDna) {
    payload.custom_dna = { ...customDna, alpha_attraction: 1.0 };
  }
  const r = await fetch(`${API_BASE}/api/area/${slug}/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(await r.text());
  const d = await r.json();
  return d.top_locations ?? [];
}

export async function synthesizeDnaApi(
  name: string,
  aiConfig?: Partial<AiConfig>
): Promise<CustomDnaState> {
  const r = await fetch(`${API_BASE}/api/dna/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      provider: aiConfig?.provider || "local",
      api_key: aiConfig?.apiKey || "",
      model: aiConfig?.model || null,
      custom_base_url: aiConfig?.customBaseUrl || null,
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function chatStrategistApi(
  slug: string,
  payload: {
    message: string;
    lat: number;
    lon: number;
    category: string;
    time_of_day: string;
    sandbox: SandboxState;
    aiConfig: AiConfig;
    history: { role: string; content: string }[];
    lang: Lang;
  }
): Promise<ChatResponse> {
  const r = await fetch(`${API_BASE}/api/area/${slug}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: payload.message,
      lat: payload.lat,
      lon: payload.lon,
      category: payload.category,
      time_of_day: payload.time_of_day,
      overrides: buildOverridesPayload(payload.sandbox),
      provider: payload.aiConfig.provider,
      api_key: payload.aiConfig.apiKey,
      model: payload.aiConfig.model || null,
      custom_base_url: payload.aiConfig.customBaseUrl || null,
      history: payload.history,
      lang: payload.lang,
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
