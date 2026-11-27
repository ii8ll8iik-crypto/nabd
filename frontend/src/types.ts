import type { Lang } from "./i18n";
export type { Lang };

export interface GeoFeature {
  type: "Feature";
  geometry: { type: string; coordinates: unknown };
  properties: Record<string, unknown>;
}

export interface GeoFeatureCollection {
  type: "FeatureCollection";
  features: GeoFeature[];
}

export interface GeocodeResult {
  display_name: string;
  lat: number;
  lon: number;
  type: string;
}

export interface ServiceCatalogItem {
  key: string;
  label_en: string;
  label_ar: string;
  beta_decay: number;
  alpha_attraction: number;
  ideal_walk_min: number;
  daily_capacity: number;
  audience_weights: Record<string, number>;
  synergy_induces: Record<string, number>;
}

export interface CatalogResponse {
  available_areas: string[];
  presets: Record<string, { label: string; lat: number; lon: number; radius_m: number }>;
  services: Record<string, ServiceCatalogItem>;
  demo_axes: string[];
  demo_zone_presets: Record<string, Record<string, number>>;
  ai_providers?: string[];
}

export interface AreaLayersResponse {
  meta: {
    slug: string;
    label: string;
    center_lat: number;
    center_lon: number;
    radius_m: number;
    synced_at: string;
    total_est_pop: number;
  };
  stats: {
    junctions: number;
    streets: number;
    blocks: number;
    services: number;
    env_zones?: number;
    elev_min_m?: number | null;
    elev_max_m?: number | null;
    total_est_pop: number;
  };
  buildings: GeoFeatureCollection;
  streets: GeoFeatureCollection;
  services: GeoFeatureCollection;
  env_zones?: GeoFeatureCollection;
}

export interface CompetitorImpact {
  service_id: string;
  name: string;
  lat: number;
  lon: number;
  visits_before: number;
  visits_after: number;
  visits_lost: number;
  pct_change: number;
}

export interface SynergyItem {
  target_category: string;
  label_en: string;
  label_ar: string;
  multiplier: number;
  induced_daily_visits: number;
  nearby_existing_count: number;
  unmet_synergy_deficit: number;
  status: "NEW_DEFICIT" | "ABSORBED";
}

export interface ScenarioMetrics {
  visits: number;
  new_unmet_demand: number;
  service_utilization_pct: number;
  street_bpr_delay_factor: number;
  congestion_alert: boolean;
}

export interface ProximityDriver {
  type: string;
  name: string;
  title_ar: string;
  title_en?: string;
  distance_m: number;
  effect_pct: number;
}

export interface TerrainAndZoning {
  elevation_m: number | null;
  mean_approach_delta_m: number;
  slope_walk_friction_pct: number;
  terrain_verdict_ar: string;
  terrain_verdict_en?: string;
  is_restricted: boolean;
  restricted_reason: string | null;
  restricted_reason_en?: string | null;
  is_food_or_hospitality: boolean;
  env_boost_multiplier: number;
  proximity_drivers: ProximityDriver[];
}

export interface ParcelContext {
  parcel_id: string | null;
  land_use: string | null;
  site_suitability: string | null;
  ownership_status: string | null;
  levels: number | null;
  gfa_m2: number | null;
  day_pop: number | null;
  night_pop: number | null;
  dist_to_click_m: number | null;
}

export interface RelateTransactionContext {
  tx_state: string;
  elapsed_ms?: number;
  parcel?: Record<string, unknown>;
  multi_hop_context?: {
    nearby_services?: number;
    nearby_competitors?: number;
    nearby_env_zones?: string[];
  };
}

export interface SimulationResponse {
  parcel_context?: ParcelContext;
  relate_transaction?: RelateTransactionContext;
  injection: {
    lat: number;
    lon: number;
    snapped_junction: string;
    snap_m: number;
    category: string;
    label_en: string;
    label_ar: string;
    time_of_day: string;
    rhythm_multiplier: number;
    effective_capacity?: number;
    attraction_multiplier?: number;
  };
  terrain_and_zoning?: TerrainAndZoning;
  local_demographics: {
    audience_fit_multiplier: number;
    composition_pct: Record<string, number>;
  };
  hop1_gravity_and_access: {
    projected_daily_visits: number;
    new_unmet_demand_captured: number;
    cannibalized_visits: number;
    cannibalization_pct: number;
    residents_unlocked_within_ideal_walk: number;
    equity_score_before: number;
    equity_score_after: number;
    equity_gain_delta: number;
  };
  hop2_competitor_ripple: {
    existing_competitors_in_area: number;
    impacted_count: number;
    top_impacted: CompetitorImpact[];
  };
  hop3_induced_synergy: SynergyItem[];
  hop4_bpr_congestion: {
    service_utilization_pct: number;
    service_bpr_delay_factor: number;
    street_load_ratio: number;
    street_bpr_delay_factor: number;
    congestion_alert: boolean;
  };
  monte_carlo_envelope: {
    runs: number;
    p10_conservative: number;
    p50_base: number;
    p90_optimistic: number;
    viability_probability_pct: number;
  };
  scenarios?: {
    conservative: ScenarioMetrics;
    base: ScenarioMetrics;
    optimistic: ScenarioMetrics;
  };
  spatial_effects?: {
    unlocked_block_ids: string[];
    served_block_ids: string[];
    shared_block_ids?: string[];
  };
  composite_network_gain_J: number;
}

export interface IllusionItem {
  block_id: string;
  lat: number;
  lon: number;
  est_pop: number;
  euclid_m: number;
  network_m: number;
  walk_min: number;
  circuity_index: number;
  nearest_service: string;
}

export interface IllusionsResponse {
  category: string;
  illusion_count: number;
  affected_residents: number;
  mean_circuity: number;
  illusions: IllusionItem[];
}

export interface OptimalSite {
  parcel_id?: string;
  junction_id: string;
  land_use?: string;
  site_suitability?: string;
  ownership_status?: string;
  levels?: number;
  gfa_m2?: number;
  lat: number;
  lon: number;
  gain_J: number;
  audience_fit: number;
  env_boost?: number;
  elevation_m?: number | null;
  daily_visits_p50: number;
  new_unmet_demand: number;
  cannibalization_pct: number;
  residents_unlocked: number;
  viability_pct: number;
}

export interface PaintedZone {
  id: string;
  lat: number;
  lon: number;
  radius_m: number;
  preset: string;
  label: string;
  color: string;
}

export interface ClosedRoad {
  id: string;
  lat: number;
  lon: number;
}

export interface PopSurge {
  id: string;
  lat: number;
  lon: number;
  pop: number;
}

export interface SandboxState {
  paintedZones: PaintedZone[];
  closedRoads: ClosedRoad[];
  demolishedBlocks: string[];
  popSurges: PopSurge[];
}

export interface CustomDnaState {
  name: string;
  beta_decay: number;
  ideal_walk_min: number;
  daily_capacity: number;
  demand_per_1k_pop: number;
  competes_with_category: string;
  audience_weights: Record<string, number>;
  time_profile?: Record<string, number>;
  synergy_induces?: Record<string, number>;
  rationale_ar?: string;
  rationale_en?: string;
  source?: string;
}

export type MapTool = "inject" | "paint" | "close_road" | "demolish" | "add_pop";
export type ScenarioKey = "conservative" | "base" | "optimistic";
export type MapStyleMode = "cyber" | "satellite" | "terrain";

export interface LayersVisibility {
  buildings: boolean;
  streets: boolean;
  services: boolean;
  envZones: boolean;
  illusions: boolean;
}

export interface PinnedSite {
  label: string;
  lat: number;
  lon: number;
  result: SimulationResponse;
}

export interface AiMapAction {
  type: "fly_and_inject" | "show_illusions";
  lat?: number;
  lon?: number;
  category: string;
  optimal_sites?: OptimalSite[];
}

export interface ChatResponse {
  reply: string;
  engine_mode: string;
  intent: string;
  warning: string | null;
  map_action: AiMapAction | null;
}

export interface AiConfig {
  provider: string;
  apiKey: string;
  model: string;
  customBaseUrl: string;
}

export interface RelateTraceEntry {
  timestamp: string;
  tag: string;
  tx_state: string;
  elapsed_ms: number;
  row_count: number;
  cypher: string;
}

export interface RelateInfoResponse {
  slug: string;
  schema_version: string;
  store_info: {
    node_count?: number;
    rel_count?: number;
    constraints?: Array<{ name: string; label: string; properties: string[] }>;
    indexes?: Array<{ name: string; label: string; property: string }>;
    total_bytes?: number;
    codec?: string;
    format_version?: number;
  };
  build_receipt?: Record<string, unknown> | null;
  trace_count: number;
}

export interface RelateCypherResponse {
  slug: string;
  row_count: number;
  elapsed_ms: number;
  rows: Array<Record<string, unknown>>;
}

export interface AgentDecisionItem {
  id: string;
  parcel_id: string;
  category: string;
  status: "APPROVED" | "REJECTED" | "WATCHLIST" | string;
  reason: string;
  actor: string;
  created_at: string;
  lat?: number;
  lon?: number;
  land_use?: string;
  ownership_status?: string;
  metrics?: Record<string, unknown>;
}
