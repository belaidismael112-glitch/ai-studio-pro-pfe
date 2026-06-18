"use client";

import { useMemo, useState } from "react";
import {
  Clapperboard,
  Copy,
  ImageIcon,
  Loader2,
  Send,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  createDirectorPlan,
  DirectorLang,
  DirectorPlan,
  DirectorSuggestion,
  DirectorTarget,
} from "@/lib/creative-director";

export type { DirectorPlan, DirectorSuggestion };

type DirectorModeModalProps = {
  open: boolean;
  apiBase: string;
  lang: DirectorLang;
  initialIdea?: string;
  onClose: () => void;
  onUseSuggestion: (suggestion: DirectorSuggestion, plan: DirectorPlan) => void;
  onSendPromptToInput: (prompt: string) => void;
};

function getVisiblePageContext(): string {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return "";
  }

  const path = window.location.pathname;

  const title =
    document.querySelector("h1")?.textContent?.trim() ||
    document.title ||
    "Studio Pro";

  const mainText =
    document.querySelector("main")?.textContent ||
    document.body?.textContent ||
    "";

  const cleanedText = mainText
    .replace(/\s+/g, " ")
    .replace(/Assistant[\s\S]*$/i, "")
    .trim()
    .slice(0, 1800);

  return [
    `Current page: ${path}`,
    `Page title: ${title}`,
    `Visible page content: ${cleanedText}`,
  ].join("\n");
}

function label(lang: DirectorLang, key: string): string {
  const dict: Record<string, Record<string, string>> = {
    title: {
      en: "Director Mode + Prompt Doctor",
      fr: "Director Mode + Prompt Doctor",
      auto: "Director Mode + Prompt Doctor",
    },
    subtitle: {
      en: "Turn a simple idea into a professional image or image-to-image production plan.",
      fr: "Transforme une idée simple en plan professionnel image ou image-vers-image.",
      auto: "Turn a simple idea into a professional image or image-to-image production plan.",
    },
    placeholder: {
      en: "Example: A clean ad for Tunisian coffee...",
      fr: "Exemple : une publicité cinématique pour un café tunisien...",
      auto: "Example: A clean ad for Tunisian coffee...",
    },
    analyze: {
      en: "Create plan",
      fr: "Créer le plan",
      auto: "Create plan",
    },
    close: {
      en: "Close",
      fr: "Fermer",
      auto: "Close",
    },
    copy: {
      en: "Copy prompt",
      fr: "Copier prompt",
      auto: "Copy prompt",
    },
    sendInput: {
      en: "Send to input",
      fr: "Envoyer au champ",
      auto: "Send to input",
    },
    use: {
      en: "Use",
      fr: "Utiliser",
      auto: "Use",
    },
    target: {
      en: "Target",
      fr: "Cible",
      auto: "Target",
    },
    image: {
      en: "Image",
      fr: "Image",
      auto: "Image",
    },
      };

  return dict[key]?.[lang] || dict[key]?.auto || key;
}

export function DirectorModeModal({
  open,
  apiBase,
  lang,
  initialIdea = "",
  onClose,
  onUseSuggestion,
  onSendPromptToInput,
}: DirectorModeModalProps) {
  const [idea, setIdea] = useState(initialIdea);
  const [target, setTarget] = useState<DirectorTarget>("image");
  const [plan, setPlan] = useState<DirectorPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRtl = false;

  if (!open) return null;

  const runDirector = async () => {
    const clean = idea.trim();

    if (!clean || loading) return;

    setLoading(true);
    setError(null);
    setPlan(null);

    try {
      const result = await createDirectorPlan({
        apiBase,
        idea: clean,
        lang,
        target,
        pageContext: getVisiblePageContext(),
      });

      setPlan(result);
    } catch (err: any) {
      setError(err?.message || "Director Mode failed");
    } finally {
      setLoading(false);
    }
  };

  const copyPrompt = async () => {
    if (!plan?.improved_prompt) return;

    await navigator.clipboard?.writeText(plan.improved_prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-xl">
      <div
        dir={isRtl ? "rtl" : "ltr"}
        className="relative max-h-[92vh] w-full max-w-3xl overflow-hidden rounded-[30px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.28)]"
      >
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.25),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(34,211,238,0.18),transparent_35%),linear-gradient(180deg,#090909_0%,#050505_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.12]"
            style={{
              backgroundImage:
                "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "22px 22px",
            }}
          />
        </div>

        <div className="relative z-10">
          <div className="flex items-start justify-between border-b border-white/10 p-5">
            <div className="flex gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-fuchsia-500 to-cyan-400 shadow-[0_0_25px_rgba(217,70,239,0.35)]">
                <Clapperboard className="h-6 w-6 text-white" />
              </div>

              <div>
                <h2 className="text-lg font-bold">{label(lang, "title")}</h2>
                <p className="mt-1 max-w-xl text-sm text-white/60">
                  {label(lang, "subtitle")}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/70 transition hover:bg-white/10 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-[calc(92vh-90px)] overflow-y-auto p-5">
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-white/80">
                  <Copy className="h-4 w-4 text-fuchsia-300" />
                  {label(lang, "target")}
                </div>

                <div className="grid grid-cols-1 gap-2 rounded-2xl border border-white/10 bg-black/35 p-1">
                  {(["image"] as DirectorTarget[]).map(
                    (item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => setTarget(item)}
                        className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                          target === item
                            ? "bg-fuchsia-600 text-white shadow-[0_0_20px_rgba(217,70,239,0.25)]"
                            : "text-white/55 hover:bg-white/10 hover:text-white"
                        }`}
                      >
                        {label(lang, item)}
                      </button>
                    )
                  )}
                </div>
              </div>

              <Textarea
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
                placeholder={label(lang, "placeholder")}
                className="min-h-[120px] resize-none border-white/10 bg-black/50 text-white placeholder:text-white/35 focus-visible:ring-fuchsia-400/40"
              />

              {error && (
                <div className="mt-3 rounded-2xl border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-200">
                  {error}
                </div>
              )}

              <div className="mt-4 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={onClose}
                  className="border-white/10 bg-white/5 text-white hover:bg-white/10"
                >
                  {label(lang, "close")}
                </Button>

                <Button
                  type="button"
                  onClick={runDirector}
                  disabled={loading || !idea.trim()}
                  className="bg-fuchsia-600 text-white shadow-[0_0_24px_rgba(217,70,239,0.3)] hover:bg-fuchsia-500"
                >
                  {loading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  {label(lang, "analyze")}
                </Button>
              </div>
            </div>

            {plan && (
              <div className="mt-5 space-y-4">
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Copy className="h-4 w-4 text-fuchsia-300" />
                    <h3 className="font-bold">{plan.title}</h3>
                  </div>

                  <p className="text-sm leading-6 text-white/75">
                    {plan.summary}
                  </p>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <InfoBlock title="Scene" value={plan.scene} />
                    <InfoBlock title="Style" value={plan.style} />
                    <InfoBlock title="Lighting" value={plan.lighting} />
                    <InfoBlock title="Camera" value={plan.camera} />
                    <InfoBlock title="Mood" value={plan.mood} />
                    <InfoBlock title="Caption" value={plan.caption} />
                  </div>
                </div>

                <div className="rounded-3xl border border-white/10 bg-black/45 p-4">
                  <h3 className="mb-2 font-bold">Prompt Doctor</h3>
                  <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-sm leading-6 text-white/75">
                    {plan.improved_prompt}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={copyPrompt}
                      className="bg-white/10 text-white hover:bg-white/15"
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      {copied ? "Copied" : label(lang, "copy")}
                    </Button>

                    <Button
                      type="button"
                      size="sm"
                      onClick={() => onSendPromptToInput(plan.improved_prompt)}
                      className="bg-cyan-600 text-white hover:bg-cyan-500"
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      {label(lang, "sendInput")}
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  {plan.suggestions.map((suggestion) => (
                    <button
                      key={`${suggestion.action}-${suggestion.title}`}
                      type="button"
                      onClick={() => onUseSuggestion(suggestion, plan)}
                      className="rounded-3xl border border-fuchsia-400/25 bg-fuchsia-500/10 p-4 text-left transition hover:border-fuchsia-300/50 hover:bg-fuchsia-500/15"
                    >
                      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-fuchsia-100">
                        {suggestion.action === "generate_image" ? (
                          <ImageIcon className="h-4 w-4" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                        {suggestion.title}
                      </div>
                      <p className="line-clamp-5 text-xs leading-5 text-white/60">
                        {suggestion.description || suggestion.prompt}
                      </p>
                      <div className="mt-3 text-xs font-semibold text-cyan-200">
                        {label(lang, "use")} →
                      </div>
                    </button>
                  ))}
                </div>

                {plan.error && (
                  <div className="rounded-2xl border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-100">
                    {plan.error}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/35 p-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white/35">
        {title}
      </div>
      <div className="text-sm leading-5 text-white/75">{value}</div>
    </div>
  );
}
