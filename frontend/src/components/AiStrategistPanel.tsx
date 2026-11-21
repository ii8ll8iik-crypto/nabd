import { useEffect, useRef, useState } from "react";
import { Bot, Send, Settings2, Sparkles, X } from "lucide-react";
import { chatStrategistApi } from "../api";
import type { AiConfig, AiMapAction, Lang, SandboxState } from "../types";

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: string;
  warning?: string | null;
}

interface Props {
  lang: Lang;
  open: boolean;
  onClose: () => void;
  activeSlug: string;
  clickedPoint: { lat: number; lon: number } | null;
  areaCenter: { lat: number; lon: number } | null;
  category: string;
  timeOfDay: string;
  sandbox: SandboxState;
  onMapAction: (action: AiMapAction) => void;
}

const STORAGE_KEY = "nabd_ai_config_v1";

const PROVIDERS = [
  { id: "local", en: "Built-in Grounded Engine (Free · No API Key)", ar: "الوضع المحلي الذكي (مجاني بلا مفتاح)", placeholderModel: "built-in" },
  { id: "gemini", en: "Google Gemini", ar: "Google Gemini", placeholderModel: "gemini-2.5-flash" },
  { id: "openai", en: "OpenAI (GPT-4o / o3)", ar: "OpenAI (GPT-4o / o3)", placeholderModel: "gpt-4o-mini" },
  { id: "anthropic", en: "Anthropic Claude", ar: "Anthropic Claude", placeholderModel: "claude-3-5-sonnet-latest" },
  { id: "deepseek", en: "DeepSeek", ar: "DeepSeek", placeholderModel: "deepseek-chat" },
  { id: "groq", en: "Groq (Ultra-Fast Llama 3.3)", ar: "Groq (Llama 3.3 فائق السرعة)", placeholderModel: "llama-3.3-70b-versatile" },
  { id: "openrouter", en: "OpenRouter (All Models · 1 Key)", ar: "OpenRouter (كل النماذج بمفتاح واحد)", placeholderModel: "google/gemini-2.5-flash" },
  { id: "custom", en: "Custom (Ollama / xAI / Mistral / Local)", ar: "مخصّص (Ollama / xAI / Mistral / محلي)", placeholderModel: "llama3.2" },
];

const QUICK_PROMPTS_I18N: Record<Lang, string[]> = {
  en: [
    "Where is the best spot to open a cafe?",
    "Analyze current site with terrain & parks",
    "Compare barber vs beauty salon here",
    "Expose topological illusions for pharmacies",
  ],
  ar: [
    "وين أفضل موقع أفتح فيه مقهى أو مطعم؟",
    "حلّل الموقع الحالي مع التضاريس والحدائق",
    "قارن حلاق رجالي مقابل صالون نسائي هنا",
    "اكشف وهم القرب للصيدليات بالمنطقة",
  ],
};

function loadSavedConfig(): AiConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore
  }
  return { provider: "local", apiKey: "", model: "", customBaseUrl: "" };
}

function renderFormattedLine(line: string, idx: number) {
  const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <div key={idx} className="ai-line">
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="ai-code">{part.slice(1, -1)}</code>;
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

export function AiStrategistPanel({
  lang,
  open,
  onClose,
  activeSlug,
  clickedPoint,
  areaCenter,
  category,
  timeOfDay,
  sandbox,
  onMapAction,
}: Props) {
  const isAr = lang === "ar";
  const [config, setConfig] = useState<AiConfig>(loadSavedConfig);
  const [showSettings, setShowSettings] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);

  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
      // ignore
    }
  }, [config]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const welcomeMsg: ChatMsg = {
    id: "welcome",
    role: "assistant",
    mode: "local",
    content: isAr
      ? "أهلاً بك في **مستشار نبض الاستراتيجي**. كل إجابة مبنية مباشرة على القوانين السبعة والتضاريس وقاعدة `Relate` بصفر هلوسة.\nيمكنك العمل فوراً بالوضع المحلي المجاني أو الضغط على أيقونة الإعدادات لربط أي مفتاح API."
      : "Welcome to **Nabd AI Strategist**. Every number is computed live from the 7 Laws, real terrain slopes, and `Relate` with zero hallucination.\nWorks out-of-the-box locally for free, or click the settings icon to connect Gemini, OpenAI, Claude, DeepSeek, Groq, OpenRouter, or Ollama.",
  };

  const displayMessages = messages.length ? messages : [welcomeMsg];

  const handleSend = async (textOverride?: string) => {
    const q = (textOverride ?? input).trim();
    if (!q || sending) return;
    const pt = clickedPoint ?? areaCenter ?? { lat: 32.5365, lon: 35.8555 };

    const userMsg: ChatMsg = { id: `u_${Date.now()}`, role: "user", content: q };
    const nextHistory = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, userMsg]);
    if (!textOverride) setInput("");
    setSending(true);

    try {
      const res = await chatStrategistApi(activeSlug, {
        message: q,
        lat: pt.lat,
        lon: pt.lon,
        category,
        time_of_day: timeOfDay,
        sandbox,
        aiConfig: config,
        history: nextHistory.slice(-8),
        lang,
      });

      setMessages((prev) => [
        ...prev,
        {
          id: `a_${Date.now()}`,
          role: "assistant",
          content: res.reply,
          mode: res.engine_mode,
          warning: res.warning,
        },
      ]);

      if (res.map_action) onMapAction(res.map_action);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e_${Date.now()}`,
          role: "assistant",
          content: `${isAr ? "تعذّر التواصل مع المستشار:" : "Strategist request failed:"} ${
            err instanceof Error ? err.message : "Error"
          }`,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const activeProviderMeta = PROVIDERS.find((p) => p.id === config.provider) ?? PROVIDERS[0];

  return (
    <section className={`ai-float-shell ${open ? "open" : "closed"}`} dir={isAr ? "rtl" : "ltr"}>
      <div className="cyber-panel ai-card">
        <div className="ai-header">
          <div className="ai-title">
            <div className="ai-orb">
              <Bot size={16} />
            </div>
            <div>
              <strong>{isAr ? "مستشار نبض الاستراتيجي" : "Nabd AI Strategist"}</strong>
              <span className="ai-mode-badge">
                {config.provider === "local"
                  ? isAr ? "هجين · محلي مجاني" : "Hybrid · Free Local Engine"
                  : `${isAr ? "متصل" : "Connected"} · ${config.provider.toUpperCase()}`}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", gap: 6 }}>
            <button
              className={`icon-close ${showSettings ? "active-violet" : ""}`}
              onClick={() => setShowSettings((v) => !v)}
              title={isAr ? "إعدادات نماذج ومفاتيح API" : "AI Provider & API Key Settings"}
            >
              <Settings2 size={14} />
            </button>
            <button className="icon-close" onClick={onClose} title={isAr ? "إغلاق" : "Close"}>
              <X size={15} />
            </button>
          </div>
        </div>

        {showSettings && (
          <div className="ai-settings">
            <div className="block-title" style={{ marginBottom: 6 }}>
              <span>{isAr ? "ربط أي نموذج ذكاء اصطناعي (Hybrid AI)" : "Universal AI Provider Router"}</span>
            </div>
            <select
              value={config.provider}
              onChange={(e) => setConfig({ ...config, provider: e.target.value })}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {isAr ? p.ar : p.en}
                </option>
              ))}
            </select>

            {config.provider !== "local" && (
              <div className="stack-sm" style={{ marginTop: 8 }}>
                <input
                  type="password"
                  value={config.apiKey}
                  onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                  placeholder={isAr ? "أدخل API Key (يُحفظ في متصفحك فقط)" : "Enter API Key (stored locally in browser only)"}
                  dir="ltr"
                />
                <input
                  type="text"
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                  placeholder={`${isAr ? "اسم النموذج (افتراضي:" : "Model override (default:"} ${activeProviderMeta.placeholderModel})`}
                  dir="ltr"
                />
                {config.provider === "custom" && (
                  <input
                    type="text"
                    value={config.customBaseUrl}
                    onChange={(e) => setConfig({ ...config, customBaseUrl: e.target.value })}
                    placeholder="Endpoint URL (e.g. http://localhost:11434/v1/chat/completions)"
                    dir="ltr"
                  />
                )}
              </div>
            )}
          </div>
        )}

        <div className="ai-messages" ref={scrollRef}>
          {displayMessages.map((m) => (
            <div key={m.id} className={`ai-bubble ${m.role}`}>
              {m.warning && <div className="ai-warn">{m.warning}</div>}
              {m.content.split("\n").map((ln, idx) => renderFormattedLine(ln, idx))}
              {m.mode && (
                <div className="ai-meta mono" dir="ltr">
                  {m.mode}
                </div>
              )}
            </div>
          ))}
          {sending && (
            <div className="ai-bubble assistant">
              <Sparkles size={13} style={{ verticalAlign: "middle" }} />{" "}
              {isAr ? "جارٍ تشغيل القوانين السبعة وتحليل التضاريس..." : "Running 7-Law physics & terrain analysis..."}
            </div>
          )}
        </div>

        <div className="ai-quick-row">
          {QUICK_PROMPTS_I18N[lang].map((qp) => (
            <button key={qp} className="ai-chip" onClick={() => void handleSend(qp)} disabled={sending}>
              {qp}
            </button>
          ))}
        </div>

        <form
          className="ai-input-row"
          onSubmit={(e) => {
            e.preventDefault();
            void handleSend();
          }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              isAr
                ? "اسأل عن أفضل موقع، مقارنة مشاريع، أو تحليل التضاريس..."
                : "Ask for optimal sites, A/B comparisons, terrain or illusions..."
            }
            disabled={sending}
          />
          <button type="submit" className="cyber-btn btn-neon" disabled={sending || !input.trim()}>
            <Send size={14} />
          </button>
        </form>
      </div>
    </section>
  );
}
