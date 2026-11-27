import { useEffect, useMemo, useState } from "react";
import {
  Compass,
  Database,
  Globe,
  Maximize2,
  Moon,
  Search,
  Sparkles,
  Sun,
  Target,
  X,
} from "lucide-react";
import type { Lang } from "../types";

export interface PaletteAction {
  id: string;
  group: "flights" | "cities" | "engine";
  titleEn: string;
  titleAr: string;
  descEn: string;
  descAr: string;
  badge?: string;
  icon: "flight" | "city" | "day" | "night" | "trace" | "opt" | "zen" | "lang";
  run: () => void;
}

interface Props {
  lang: Lang;
  open: boolean;
  onClose: () => void;
  actions: PaletteAction[];
}

export function CommandPalette({ lang, open, onClose, actions }: Props) {
  const isAr = lang === "ar";
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (open) setQuery("");
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter(
      (a) =>
        a.titleEn.toLowerCase().includes(q) ||
        a.titleAr.toLowerCase().includes(q) ||
        a.descEn.toLowerCase().includes(q) ||
        a.descAr.toLowerCase().includes(q)
    );
  }, [actions, query]);

  if (!open) return null;

  const renderIcon = (kind: PaletteAction["icon"]) => {
    switch (kind) {
      case "flight":
        return <Sparkles size={15} className="c-cyan" />;
      case "city":
        return <Compass size={15} className="c-emerald" />;
      case "day":
        return <Sun size={15} className="c-amber" />;
      case "night":
        return <Moon size={15} className="c-violet" />;
      case "trace":
        return <Database size={15} className="c-cyan" />;
      case "opt":
        return <Target size={15} className="c-emerald" />;
      case "zen":
        return <Maximize2 size={15} className="c-amber" />;
      case "lang":
        return <Globe size={15} className="c-cyan" />;
    }
  };

  const groups: Array<{ key: PaletteAction["group"]; en: string; ar: string }> = [
    { key: "flights", en: "Guided Live Proof Flights (Real Relate Engine)", ar: "رحلات البرهان الحية (محرك Relate الفعلي)" },
    { key: "cities", en: "Indexed City Bundles (.rl)", ar: "حزم المدن المفهرَسة (.rl)" },
    { key: "engine", en: "Engine & Studio Controls", ar: "أوامر المحرك والاستوديو" },
  ];

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div
        className="cyber-panel palette-modal"
        dir={isAr ? "rtl" : "ltr"}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="palette-search-row">
          <Search size={15} className="c-cyan" />
          <input
            autoFocus
            className="palette-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              isAr
                ? "ابحث عن رحلة برهان، مدينة (.rl)، أو أمر في المحرك..."
                : "Jump to a live Proof Flight, .rl city bundle, or Relate command..."
            }
          />
          <span className="kbd-chip mono">ESC</span>
          <button className="icon-close" onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        <div className="palette-list">
          {groups.map((g) => {
            const items = filtered.filter((a) => a.group === g.key);
            if (items.length === 0) return null;
            return (
              <div key={g.key} className="palette-group">
                <div className="palette-group-title">{isAr ? g.ar : g.en}</div>
                {items.map((item) => (
                  <button
                    key={item.id}
                    className="palette-item"
                    onClick={() => {
                      onClose();
                      item.run();
                    }}
                  >
                    <div className="palette-item-icon">{renderIcon(item.icon)}</div>
                    <div className="palette-item-copy">
                      <div className="palette-item-title">{isAr ? item.titleAr : item.titleEn}</div>
                      <div className="palette-item-desc">{isAr ? item.descAr : item.descEn}</div>
                    </div>
                    {item.badge && <span className="gb-pill mono">{item.badge}</span>}
                  </button>
                ))}
              </div>
            );
          })}
          {filtered.length === 0 && (
            <p className="muted-note" style={{ padding: "12px" }}>
              {isAr ? "لا توجد أوامر مطابقة." : "No matching commands."}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
