import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Database,
  Navigation,
  Play,
  RefreshCw,
  ShieldAlert,
  Terminal,
  X,
} from "lucide-react";
import {
  fetchAgentDecisions,
  fetchRelateInfo,
  fetchRelateTraces,
  runRelateCypherApi,
} from "../api";
import type {
  AgentDecisionItem,
  Lang,
  RelateCypherResponse,
  RelateInfoResponse,
  RelateTraceEntry,
} from "../types";

interface Props {
  lang: Lang;
  open: boolean;
  onClose: () => void;
  activeSlug: string;
  refreshToken: number;
  leftOpen?: boolean;
  rightOpen?: boolean;
  onFlyToParcel: (lat: number, lon: number) => void;
}

const CYPHER_PRESETS = [
  {
    id: "health",
    en: "01 · 3D Volumetric Pulse",
    ar: "01 · النبض الحجمي 3D",
    query: `MATCH (m:Meta)
WITH m
MATCH (p:Parcel)
RETURN m.slug AS city,
       count(p) AS parcels,
       round(sum(p.gfa_m2)) AS total_gfa_m2,
       sum(p.day_pop) AS day_pop,
       sum(p.night_pop) AS night_pop`,
  },
  {
    id: "storefronts",
    en: "02 · Top Buildable Parcels",
    ar: "02 · أفضل العقارات القابلة للبناء",
    query: `MATCH (p:Parcel)-[:FRONTS_ON]->(j:Junction)
WHERE coalesce(p.env_restricted, false) = false
  AND coalesce(p.ownership_status, '') <> 'BLOCKED_OWNERSHIP'
  AND p.site_suitability IN ['storefront_lease', 'mixed_ground_floor', 'vacant_buildable']
RETURN p.id AS parcel_id, p.land_use AS land_use, p.site_suitability AS suitability,
       p.levels AS floors, round(p.gfa_m2) AS gfa_m2, j.elev_m AS elev_m
ORDER BY p.gfa_m2 DESC
LIMIT 10`,
  },
  {
    id: "multihop",
    en: "03 · 2-Hop Connected Context",
    ar: "03 · السياق المتصل متعدّد القفزات",
    query: `MATCH (p:Parcel)-[:FRONTS_ON]->(j:Junction)
WITH p, j ORDER BY p.gfa_m2 DESC LIMIT 5
OPTIONAL MATCH (j)-[:STREET*1..2]-(nj:Junction)<-[:LOCATED_ON]-(s:Service)
WITH p, j, count(DISTINCT s) AS nearby_services
OPTIONAL MATCH (j)-[:NEAR_ZONE]->(z:EnvZone)
RETURN p.id AS parcel_id, p.land_use AS land_use, j.elev_m AS elev_m,
       nearby_services, collect(DISTINCT z.name)[0..4] AS env_zones`,
  },
  {
    id: "memory",
    en: "04 · Agent Decision Memory",
    ar: "04 · ذاكرة قرارات الوكلاء",
    query: `MATCH (d:AgentDecision)-[:EVALUATES]->(p:Parcel)
RETURN d.id AS id, d.status AS status, d.category AS category,
       d.actor AS actor, d.reason AS reason, p.id AS parcel_id,
       p.ownership_status AS ownership
ORDER BY d.created_at DESC
LIMIT 20`,
  },
];

export function RelateInspectorPanel({
  lang,
  open,
  onClose,
  activeSlug,
  refreshToken,
  leftOpen = false,
  rightOpen = false,
  onFlyToParcel,
}: Props) {
  const isAr = lang === "ar";
  const [tab, setTab] = useState<"trace" | "cypher" | "memory">("trace");
  const [info, setInfo] = useState<RelateInfoResponse | null>(null);
  const [traces, setTraces] = useState<RelateTraceEntry[]>([]);
  const [decisions, setDecisions] = useState<AgentDecisionItem[]>([]);
  const [loading, setLoading] = useState(false);

  const [cypherText, setCypherText] = useState(CYPHER_PRESETS[1].query);
  const [cypherRes, setCypherRes] = useState<RelateCypherResponse | null>(null);
  const [cypherErr, setCypherErr] = useState<string | null>(null);
  const [runningCypher, setRunningCypher] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [i, t, d] = await Promise.all([
        fetchRelateInfo(activeSlug),
        fetchRelateTraces(activeSlug, 35),
        fetchAgentDecisions(activeSlug, 40),
      ]);
      setInfo(i);
      setTraces(t.traces);
      setDecisions(d.decisions);
    } catch {
      // ignore transient network errors while switching cities
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    void loadAll();
  }, [open, activeSlug, refreshToken]);

  const handleRunCypher = async (queryOverride?: string) => {
    const q = (queryOverride ?? cypherText).trim();
    if (!q) return;
    setRunningCypher(true);
    setCypherErr(null);
    try {
      const out = await runRelateCypherApi(activeSlug, q, 50);
      setCypherRes(out);
      const t = await fetchRelateTraces(activeSlug, 35);
      setTraces(t.traces);
    } catch (err) {
      setCypherErr(err instanceof Error ? err.message : "Cypher error");
      setCypherRes(null);
    } finally {
      setRunningCypher(false);
    }
  };

  if (!open) return null;

  const cols = cypherRes?.rows?.length ? Object.keys(cypherRes.rows[0]) : [];
  const storeBytesKb = info?.store_info?.total_bytes
    ? `${(info.store_info.total_bytes / 1024).toFixed(0)} KB`
    : "—";

  return (
    <section className={`glassbox-shell ${leftOpen ? "has-left" : ""} ${rightOpen ? "has-right" : ""}`} dir={isAr ? "rtl" : "ltr"}>
      <div className="cyber-panel glassbox-card">
        <div className="glassbox-header">
          <div className="glassbox-title-group">
            <span className="tx-dot" />
            <Database size={15} className="c-cyan" />
            <strong>{isAr ? "الصندوق الزجاجي لمحرك Relate الحي" : "Relate Live Glass-Box Inspector"}</strong>
            <span className="gb-pill mono">{activeSlug}.rl</span>
            {info?.store_info && (
              <span className="gb-stats mono tabular">
                {info.store_info.node_count?.toLocaleString()} nodes · {info.store_info.rel_count?.toLocaleString()} rels ·{" "}
                {info.store_info.constraints?.length ?? 0} constraints · {info.store_info.indexes?.length ?? 0} indexes · {storeBytesKb}
              </span>
            )}
          </div>

          <div className="glassbox-actions">
            <div className="gb-tabs">
              <button className={`gb-tab ${tab === "trace" ? "active" : ""}`} onClick={() => setTab("trace")}>
                <Terminal size={12} /> {isAr ? `السجل الحي (${traces.length})` : `Live Trace (${traces.length})`}
              </button>
              <button className={`gb-tab ${tab === "cypher" ? "active" : ""}`} onClick={() => setTab("cypher")}>
                <Play size={12} /> {isAr ? "كونسول Cypher" : "Cypher Console"}
              </button>
              <button className={`gb-tab ${tab === "memory" ? "active" : ""}`} onClick={() => setTab("memory")}>
                <CheckCircle2 size={12} /> {isAr ? `ذاكرة الوكلاء (${decisions.length})` : `Agent Memory (${decisions.length})`}
              </button>
            </div>
            <button className="icon-close" onClick={() => void loadAll()} title={isAr ? "تحديث" : "Refresh"}>
              <RefreshCw size={13} className={loading ? "spin-icon" : ""} />
            </button>
            <button className="icon-close" onClick={onClose} title={isAr ? "إغلاق" : "Close"}>
              <X size={15} />
            </button>
          </div>
        </div>

        <div className="glassbox-body">
          {tab === "trace" && (
            <div className="trace-list">
              {traces.length === 0 ? (
                <p className="muted-note">{isAr ? "لا توجد استعلامات مسجّلة بعد." : "No traces recorded yet."}</p>
              ) : (
                traces.map((tr, idx) => (
                  <div key={`${tr.timestamp}-${idx}`} className="trace-row">
                    <div className="trace-meta">
                      <span
                        className={`tx-badge mono ${
                          tr.tx_state === "COMMITTED"
                            ? "tx-commit"
                            : tr.tx_state === "ROLLED_BACK"
                            ? "tx-rollback"
                            : "tx-read"
                        }`}
                      >
                        {tr.tx_state}
                      </span>
                      <span className="trace-tag mono">{tr.tag}</span>
                      <span className="trace-timing mono tabular">{Number(tr.elapsed_ms).toFixed(2)} ms</span>
                      <span className="trace-rows mono tabular">{tr.row_count} rows</span>
                    </div>
                    <code className="trace-cypher">{tr.statement || tr.cypher || "—"}</code>
                  </div>
                ))
              )}
            </div>
          )}

          {tab === "cypher" && (
            <div className="cypher-workspace">
              <div className="cypher-presets">
                {CYPHER_PRESETS.map((pr) => (
                  <button
                    key={pr.id}
                    className="preset-chip"
                    onClick={() => {
                      setCypherText(pr.query);
                      void handleRunCypher(pr.query);
                    }}
                  >
                    {isAr ? pr.ar : pr.en}
                  </button>
                ))}
              </div>
              <div className="cypher-editor-row">
                <textarea
                  className="cypher-textarea mono"
                  rows={4}
                  value={cypherText}
                  onChange={(e) => setCypherText(e.target.value)}
                  spellCheck={false}
                />
                <button
                  className="cypher-run-btn"
                  disabled={runningCypher}
                  onClick={() => void handleRunCypher()}
                >
                  <Play size={13} /> {runningCypher ? "..." : isAr ? "تشغيل" : "Run Read-Only"}
                </button>
              </div>
              {cypherErr && (
                <div className="alert-strip" style={{ marginTop: 6 }}>
                  <ShieldAlert size={13} style={{ verticalAlign: "middle" }} /> {cypherErr}
                </div>
              )}
              {cypherRes && (
                <div className="cypher-results">
                  <div className="cypher-res-meta mono tabular">
                    {cypherRes.row_count} rows · {cypherRes.elapsed_ms.toFixed(2)} ms (live Relate read-only)
                  </div>
                  {cypherRes.rows.length > 0 ? (
                    <div className="cypher-table-wrap">
                      <table className="cypher-table mono tabular">
                        <thead>
                          <tr>
                            {cols.map((c) => (
                              <th key={c}>{c}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {cypherRes.rows.map((row, rIdx) => (
                            <tr key={rIdx}>
                              {cols.map((c) => {
                                const v = row[c];
                                const txt = Array.isArray(v)
                                  ? v.join(", ")
                                  : v === null || v === undefined
                                  ? "—"
                                  : typeof v === "object"
                                  ? JSON.stringify(v)
                                  : String(v);
                                return <td key={c}>{txt}</td>;
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="muted-note">{isAr ? "استعلام سليم — 0 صفوف مطابقة." : "Query succeeded — 0 matching rows."}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === "memory" && (
            <div className="memory-list">
              {decisions.length === 0 ? (
                <p className="muted-note">
                  {isAr
                    ? "لا توجد قرارات محفوظة في ملف .rl بعد. اختر أي عقار من الخريطة واضغط «اعتماد» أو «رفض وحجب» لتشهد الحفظ الدائم بـ COMMIT."
                    : "No persisted (:AgentDecision) nodes in this .rl file yet. Click any parcel and press Approve or Reject & Block to COMMIT durable agent memory."}
                </p>
              ) : (
                decisions.map((d) => (
                  <div key={d.id} className="memory-row">
                    <div className="memory-left">
                      <span
                        className={`tx-badge mono ${
                          d.status === "APPROVED"
                            ? "tx-commit"
                            : d.status === "REJECTED"
                            ? "tx-reject"
                            : "tx-watch"
                        }`}
                      >
                        {d.status}
                      </span>
                      <strong className="mono">{d.parcel_id}</strong>
                      <span className="gb-pill">{d.category}</span>
                      {d.ownership_status === "BLOCKED_OWNERSHIP" && (
                        <span className="tx-badge tx-reject mono">BLOCKED_OWNERSHIP</span>
                      )}
                      <span className="memory-reason">{d.reason}</span>
                    </div>
                    <div className="memory-right">
                      <span className="mono muted-xs">{d.actor}</span>
                      {d.lat != null && d.lon != null && (
                        <button
                          className="tx-trace-btn"
                          onClick={() => onFlyToParcel(d.lat as number, d.lon as number)}
                        >
                          <Navigation size={11} /> {isAr ? "انتقال" : "Fly"}
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
