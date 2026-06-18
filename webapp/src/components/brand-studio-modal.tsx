"use client";

import { useMemo, useState } from "react";
import {
  Briefcase,
  Copy,
  ImageIcon,
  Loader2,
  Send,
  Megaphone,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  BrandLang,
  BrandPack,
  BrandSuggestion,
  BrandTarget,
  brandPackToText,
  createBrandPack,
} from "@/lib/brand-studio-client";

export type { BrandPack, BrandSuggestion };

type BrandStudioModalProps = {
  open: boolean;
  apiBase: string;
  lang: BrandLang;
  onClose: () => void;
  onUseSuggestion: (suggestion: BrandSuggestion, pack: BrandPack) => void;
  onSendPromptToInput: (prompt: string) => void;
};

function label(lang: BrandLang, key: string): string {
  const dict: Record<string, Record<string, string>> = {
    title: {
      en: "Launch Pack — Brand Studio",
      fr: "Launch Pack — Brand Studio",
      auto: "Launch Pack — Brand Studio",
    },
    subtitle: {
      en: "Create a complete marketing pack from one brand idea.",
      fr: "Crée un pack marketing complet à partir d’une idée de marque.",
      auto: "Create a complete marketing pack from one brand idea.",
    },
    brandName: {
      en: "Brand name",
      fr: "Nom de marque",
      auto: "Brand name",
    },
    businessType: {
      en: "Business type",
      fr: "Type d’activité",
      auto: "Business type",
    },
    audience: {
      en: "Target audience",
      fr: "Public cible",
      auto: "Target audience",
    },
    idea: {
      en: "Extra idea",
      fr: "Idée supplémentaire",
      auto: "Extra idea",
    },
    brandPlaceholder: {
      en: "Example: Café Jasmin",
      fr: "Exemple : Café Jasmin",
      auto: "Example: Café Jasmin",
    },
    typePlaceholder: {
      en: "Example: Tunisian coffee shop",
      fr: "Exemple : café tunisien",
      auto: "Example: Tunisian coffee shop",
    },
    audiencePlaceholder: {
      en: "Example: students, workers, coffee lovers",
      fr: "Exemple : étudiants, travailleurs, amateurs de café",
      auto: "Example: students, workers, coffee lovers",
    },
    ideaPlaceholder: {
      en: "Example: clean warm local identity with clean ads...",
      fr: "Exemple : identité locale clean avec pubs propres...",
      auto: "Example: clean warm local identity with clean ads...",
    },
    create: {
      en: "Create launch pack",
      fr: "Créer le pack",
      auto: "Create launch pack",
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
    close: {
      en: "Close",
      fr: "Fermer",
      auto: "Close",
    },
    copy: {
      en: "Copy pack",
      fr: "Copier pack",
      auto: "Copy pack",
    },
    sendInput: {
      en: "Send ad prompt to input",
      fr: "Envoyer prompt au champ",
      auto: "Send ad prompt to input",
    },
    use: {
      en: "Use",
      fr: "Utiliser",
      auto: "Use",
    },
  };

  return dict[key]?.[lang] || dict[key]?.auto || key;
}

export function BrandStudioModal({
  open,
  apiBase,
  lang,
  onClose,
  onUseSuggestion,
  onSendPromptToInput,
}: BrandStudioModalProps) {
  const [brandName, setBrandName] = useState("");
  const [businessType, setBusinessType] = useState("");
  const [audience, setAudience] = useState("");
  const [idea, setIdea] = useState("");
  const [target, setTarget] = useState<BrandTarget>("image");
  const [pack, setPack] = useState<BrandPack | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRtl = false;

  if (!open) return null;

  const runBrandStudio = async () => {
    if (!brandName.trim() || loading) return;

    setLoading(true);
    setError(null);
    setPack(null);

    try {
      const result = await createBrandPack({
        apiBase,
        brandName: brandName.trim(),
        businessType: businessType.trim(),
        audience: audience.trim(),
        idea: idea.trim(),
        lang,
        target,
      });

      setPack(result);
    } catch (err: any) {
      setError(err?.message || "Brand Studio failed");
    } finally {
      setLoading(false);
    }
  };

  const copyPack = async () => {
    if (!pack) return;

    await navigator.clipboard?.writeText(brandPackToText(pack));
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-xl">
      <div
        dir={isRtl ? "rtl" : "ltr"}
        className="relative max-h-[92vh] w-full max-w-4xl overflow-hidden rounded-[30px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(34,211,238,0.22)]"
      >
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.22),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(217,70,239,0.20),transparent_35%),linear-gradient(180deg,#090909_0%,#050505_100%)]" />
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
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-fuchsia-500 shadow-[0_0_25px_rgba(34,211,238,0.35)]">
                <Briefcase className="h-6 w-6 text-white" />
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
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-white/80">
                  <Megaphone className="h-4 w-4 text-cyan-300" />
                  {label(lang, "target")}
                </div>

                <div className="grid grid-cols-1 gap-2 rounded-2xl border border-white/10 bg-black/35 p-1">
                  {(["image"] as BrandTarget[]).map(
                    (item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => setTarget(item)}
                        className={`rounded-xl px-3 py-2 text-xs font-semibold transition ${
                          target === item
                            ? "bg-cyan-600 text-white shadow-[0_0_20px_rgba(34,211,238,0.25)]"
                            : "text-white/55 hover:bg-white/10 hover:text-white"
                        }`}
                      >
                        {label(lang, item)}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <Field
                  title={label(lang, "brandName")}
                  value={brandName}
                  onChange={setBrandName}
                  placeholder={label(lang, "brandPlaceholder")}
                />
                <Field
                  title={label(lang, "businessType")}
                  value={businessType}
                  onChange={setBusinessType}
                  placeholder={label(lang, "typePlaceholder")}
                />
                <Field
                  title={label(lang, "audience")}
                  value={audience}
                  onChange={setAudience}
                  placeholder={label(lang, "audiencePlaceholder")}
                />
              </div>

              <div className="mt-3">
                <div className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/45">
                  {label(lang, "idea")}
                </div>
                <Textarea
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                  placeholder={label(lang, "ideaPlaceholder")}
                  className="min-h-[96px] resize-none border-white/10 bg-black/50 text-white placeholder:text-white/35 focus-visible:ring-cyan-400/40"
                />
              </div>

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
                  onClick={runBrandStudio}
                  disabled={loading || !brandName.trim()}
                  className="bg-cyan-600 text-white shadow-[0_0_24px_rgba(34,211,238,0.3)] hover:bg-cyan-500"
                >
                  {loading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  {label(lang, "create")}
                </Button>
              </div>
            </div>

            {pack && (
              <div className="mt-5 space-y-4">
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Briefcase className="h-4 w-4 text-cyan-300" />
                    <h3 className="font-bold">{pack.brand_name}</h3>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <InfoBlock title="Slogan" value={pack.slogan} />
                    <InfoBlock title="Brand voice" value={pack.brand_voice} />
                    <InfoBlock title="Description" value={pack.description} />
                    <InfoBlock title="CTA" value={pack.cta} />
                  </div>

                  <div className="mt-3 rounded-2xl border border-white/10 bg-black/35 p-3">
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-white/35">
                      Colors
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {pack.colors.map((color) => (
                        <span
                          key={color}
                          className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70"
                        >
                          {color}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <ListBlock title="Captions" items={pack.captions} />
                  <ListBlock title="Launch plan" items={pack.launch_plan} />
                </div>

                <div className="rounded-3xl border border-white/10 bg-black/45 p-4">
                  <h3 className="mb-2 font-bold">Ad prompts</h3>

                  <div className="space-y-3">
                    <PromptBlock title="Image prompt" value={pack.image_prompt} />
                    <PromptBlock
                      title="Negative prompt"
                      value={pack.negative_prompt}
                    />
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={copyPack}
                      className="bg-white/10 text-white hover:bg-white/15"
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      {copied ? "Copied" : label(lang, "copy")}
                    </Button>

                    <Button
                      type="button"
                      size="sm"
                      onClick={() => onSendPromptToInput(pack.image_prompt)}
                      className="bg-cyan-600 text-white hover:bg-cyan-500"
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" />
                      {label(lang, "sendInput")}
                    </Button>
                  </div>
                </div>

                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-white/35">
                    Hashtags
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {pack.hashtags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  {pack.suggestions.map((suggestion) => (
                    <button
                      key={`${suggestion.action}-${suggestion.title}`}
                      type="button"
                      onClick={() => onUseSuggestion(suggestion, pack)}
                      className="rounded-3xl border border-cyan-400/25 bg-cyan-500/10 p-4 text-left transition hover:border-cyan-300/50 hover:bg-cyan-500/15"
                    >
                      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-cyan-100">
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
                      <div className="mt-3 text-xs font-semibold text-fuchsia-200">
                        {label(lang, "use")} →
                      </div>
                    </button>
                  ))}
                </div>

                {pack.error && (
                  <div className="rounded-2xl border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-100">
                    {pack.error}
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

function Field({
  title,
  value,
  onChange,
  placeholder,
}: {
  title: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/45">
        {title}
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-11 w-full rounded-2xl border border-white/10 bg-black/50 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-400/50"
      />
    </label>
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

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <h3 className="mb-3 font-bold">{title}</h3>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div
            key={`${title}-${index}`}
            className="rounded-2xl border border-white/10 bg-black/35 p-3 text-sm leading-5 text-white/75"
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function PromptBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white/35">
        {title}
      </div>
      <div className="text-xs leading-5 text-white/70">{value}</div>
    </div>
  );
}
