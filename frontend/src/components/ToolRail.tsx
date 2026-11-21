import {
  Ban,
  Building2,
  GitCompare,
  Paintbrush,
  RotateCcw,
  Target,
  Users,
} from "lucide-react";
import type { Lang, MapTool, PinnedSite } from "../types";

interface Props {
  lang: Lang;
  activeTool: MapTool;
  onSelectTool: (t: MapTool) => void;
  pinnedA: PinnedSite | null;
  onTogglePinA: () => void;
  sandboxCount: number;
  onResetSandbox: () => void;
}

export function ToolRail({
  lang,
  activeTool,
  onSelectTool,
  pinnedA,
  onTogglePinA,
  sandboxCount,
  onResetSandbox,
}: Props) {
  const isAr = lang === "ar";
  const tools: { id: MapTool; en: string; ar: string; icon: JSX.Element; accent: string }[] = [
    { id: "inject", en: "Inject & Drag", ar: "زرع وسحب", icon: <Target size={15} />, accent: "cyan" },
    { id: "paint", en: "Reality Brush", ar: "فرشاة السكان", icon: <Paintbrush size={15} />, accent: "violet" },
    { id: "close_road", en: "Close Road", ar: "إغلاق طريق", icon: <Ban size={15} />, accent: "rose" },
    { id: "demolish", en: "Demolish", ar: "هدم مبنى", icon: <Building2 size={15} />, accent: "amber" },
    { id: "add_pop", en: "+1,500 Pop", ar: "+1500 ساكن", icon: <Users size={15} />, accent: "emerald" },
  ];

  return (
    <nav className="cyber-panel tool-rail" dir={isAr ? "rtl" : "ltr"}>
      {tools.map((t) => (
        <button
          key={t.id}
          className={`rail-btn ${activeTool === t.id ? `active-${t.accent}` : ""}`}
          onClick={() => onSelectTool(t.id)}
        >
          {t.icon}
          <span>{isAr ? t.ar : t.en}</span>
        </button>
      ))}

      <div className="rail-divider" />

      <button
        className={`rail-btn ${pinnedA ? "active-emerald" : ""}`}
        onClick={onTogglePinA}
      >
        <GitCompare size={15} />
        <span>
          {pinnedA
            ? isAr ? "موقع A مثبّت ✓" : "Site A Pinned ✓"
            : isAr ? "تثبيت للمقارنة" : "Pin A/B"}
        </span>
      </button>

      {sandboxCount > 0 && (
        <button
          className="rail-btn active-rose"
          onClick={onResetSandbox}
        >
          <RotateCcw size={14} />
          <span>{isAr ? `إعادة ضبط (${sandboxCount})` : `Reset (${sandboxCount})`}</span>
        </button>
      )}
    </nav>
  );
}
