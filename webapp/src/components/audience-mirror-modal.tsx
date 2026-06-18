"use client";

import { useMemo, useState } from "react";
import { BarChart3, Copy, ImageIcon, Loader2, Send, Users, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  AudienceLang,
  AudienceReview,
  AudienceSet,
  AudienceSuggestion,
  ContentType,
  audienceReviewToText,
  createAudienceReview,
} from "@/lib/audience-mirror-client";

export type { AudienceReview, AudienceSuggestion };

type Props = {
  open: boolean;
  apiBase: string;
  lang: AudienceLang;
  initialContent?: string;
  initialTitle?: string;
  onClose: () => void;
  onUseSuggestion: (suggestion: AudienceSuggestion, review: AudienceReview) => void;
  onSendPromptToInput: (prompt: string) => void;
};

function label(lang: AudienceLang, key: string): string {
  const dict: Record<string, Record<string, string>> = {
    title: { en: "Audience Mirror", fr: "Audience Mirror", auto: "Audience Mirror" },
    subtitle: {
      en: "Rule-based preview guidance before publishing. This is not measured user research.",
      fr: "Aperçu indicatif basé sur des règles avant publication. Ce n’est pas une étude utilisateurs mesurée.",
      auto: "Rule-based preview guidance before publishing. This is not measured user research.",
    },
    review: { en: "Run audience mirror", fr: "Lancer le test audience", auto: "Run audience mirror" },
    content: { en: "Content / prompt / brand pack", fr: "Contenu / prompt / brand pack", auto: "Content / prompt / brand pack" },
    close: { en: "Close", fr: "Fermer", auto: "Close" },
    copy: { en: "Copy review", fr: "Copier analyse", auto: "Copy review" },
    sendInput: { en: "Send improved prompt", fr: "Envoyer prompt amélioré", auto: "Send improved prompt" },
    use: { en: "Use", fr: "Utiliser", auto: "Use" },
  };
  return dict[key]?.[lang] || dict[key]?.auto || key;
}

export function AudienceMirrorModal({ open, apiBase, lang, initialContent = "", initialTitle = "", onClose, onUseSuggestion, onSendPromptToInput }: Props) {
  const [contentTitle, setContentTitle] = useState(initialTitle);
  const [brandName, setBrandName] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [contentType, setContentType] = useState<ContentType>("prompt");
  const [audienceSet, setAudienceSet] = useState<AudienceSet>("general");
  const [content, setContent] = useState(initialContent);
  const [review, setReview] = useState<AudienceReview | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isRtl = false;

  if (!open) return null;

  const run = async () => {
    if (!content.trim() || loading) return;
    setLoading(true);
    setError(null);
    setReview(null);
    try {
      setReview(await createAudienceReview({
        apiBase,
        contentTitle: contentTitle.trim() || "Project content",
        contentType,
        content: content.trim(),
        brandName: brandName.trim(),
        targetAudience: targetAudience.trim(),
        audienceSet,
        lang,
      }));
    } catch (e: any) {
      setError(e?.message || "Audience Mirror failed");
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!review) return;
    await navigator.clipboard?.writeText(audienceReviewToText(review));
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-xl">
      <div dir={isRtl ? "rtl" : "ltr"} className="relative max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-[30px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.24)]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.22),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(34,211,238,0.20),transparent_35%),linear-gradient(180deg,#090909_0%,#050505_100%)]" />
        <div className="relative z-10">
          <div className="flex items-start justify-between border-b border-white/10 p-5">
            <div className="flex gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-fuchsia-500 to-cyan-400"><Users className="h-6 w-6" /></div>
              <div><h2 className="text-lg font-bold">{label(lang, "title")}</h2><p className="mt-1 text-sm text-white/60">{label(lang, "subtitle")}</p></div>
            </div>
            <button type="button" onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-white/5"><X className="h-4 w-4" /></button>
          </div>

          <div className="max-h-[calc(92vh-90px)] overflow-y-auto p-5">
            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
              <div className="grid gap-3 md:grid-cols-3">
                <Field title="Title" value={contentTitle} onChange={setContentTitle} placeholder="Coffee ad" />
                <Field title="Brand" value={brandName} onChange={setBrandName} placeholder="Café Jasmin" />
                <Field title="Audience" value={targetAudience} onChange={setTargetAudience} placeholder="students, workers" />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <Select title="Content type" value={contentType} onChange={(v) => setContentType(v as ContentType)} opts={["prompt", "image", "brand_pack", "other"]} />
                <Select title="Audience set" value={audienceSet} onChange={(v) => setAudienceSet(v as AudienceSet)} opts={["general", "students", "workers", "premium", "social"]} />
              </div>
              <div className="mt-3">
                <div className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/45">{label(lang, "content")}</div>
                <Textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Paste your prompt, brand pack, result description, or campaign idea..." className="min-h-[120px] resize-none border-white/10 bg-black/50 text-white placeholder:text-white/35" />
              </div>
              {error && <div className="mt-3 rounded-2xl border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} className="border-white/10 bg-white/5 text-white">{label(lang, "close")}</Button>
                <Button onClick={run} disabled={loading || !content.trim()} className="bg-fuchsia-600 text-white">{loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}{label(lang, "review")}</Button>
              </div>
            </div>

            {review && <div className="mt-5 space-y-4">
              <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                <div className="mb-3 flex items-center gap-2"><BarChart3 className="h-4 w-4 text-fuchsia-300" /><h3 className="font-bold">{review.content_title}</h3></div>
                <div className="mb-3 rounded-2xl border border-yellow-400/20 bg-yellow-400/10 p-3 text-xs leading-5 text-yellow-100">Indicative rule-based guidance — not a measured audience study.</div>
                <p className="text-sm leading-6 text-white/75">{review.executive_summary}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(review.scores).map(([k, v]) => <Score key={k} title={k.replaceAll("_", " ")} value={Number(v)} />)}</div>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">{review.personas.map((p) => <div key={p.persona} className="rounded-3xl border border-white/10 bg-black/45 p-4"><div className="mb-2 flex items-center justify-between"><h4 className="font-bold">{p.persona}</h4><span className="rounded-full border border-cyan-400/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">{p.click_probability}% indicative signal</span></div><Info title="First impression" value={p.first_impression} /><Info title="Understood" value={p.understood} /><Info title="Liked" value={p.liked} /><Info title="Confused" value={p.confused} /><Info title="Improve" value={p.improvement} /></div>)}</div>

              <div className="grid gap-4 md:grid-cols-3"><List title="Strengths" items={review.strengths} /><List title="Weaknesses" items={review.weaknesses} /><List title="Recommendations" items={review.recommendations} /></div>

              <div className="rounded-3xl border border-white/10 bg-black/45 p-4"><h3 className="mb-2 font-bold">Improved prompt</h3><div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-xs leading-5 text-white/70">{review.improved_prompt}</div><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" onClick={copy} className="bg-white/10 text-white"><Copy className="mr-2 h-3.5 w-3.5" />{copied ? "Copied" : label(lang, "copy")}</Button><Button size="sm" onClick={() => onSendPromptToInput(review.improved_prompt)} className="bg-fuchsia-600 text-white"><Send className="mr-2 h-3.5 w-3.5" />{label(lang, "sendInput")}</Button></div></div>

              <div className="grid gap-3 md:grid-cols-4">{review.suggestions.map((s) => <button key={`${s.action}-${s.title}`} onClick={() => onUseSuggestion(s, review)} className="rounded-3xl border border-fuchsia-400/25 bg-fuchsia-500/10 p-4 text-left hover:bg-fuchsia-500/15"><div className="mb-3 flex items-center gap-2 text-sm font-bold text-fuchsia-100">{s.action === "generate_image" ? <ImageIcon className="h-4 w-4" /> : s.action === "fix_prompt" ? <Copy className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{s.title}</div><p className="line-clamp-5 text-xs leading-5 text-white/60">{s.description || s.prompt}</p><div className="mt-3 text-xs font-semibold text-cyan-200">{label(lang, "use")} →</div></button>)}</div>
              {review.error && <div className="rounded-2xl border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-100">{review.error}</div>}
            </div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ title, value, onChange, placeholder }: { title: string; value: string; onChange: (v: string) => void; placeholder: string }) {
  return <label><div className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/45">{title}</div><input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="h-11 w-full rounded-2xl border border-white/10 bg-black/50 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-fuchsia-400/50" /></label>;
}
function Select({ title, value, onChange, opts }: { title: string; value: string; onChange: (v: string) => void; opts: string[] }) {
  return <label><div className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-white/45">{title}</div><select value={value} onChange={(e) => onChange(e.target.value)} className="h-11 w-full rounded-2xl border border-white/10 bg-black/50 px-3 text-sm text-white outline-none">{opts.map((o) => <option key={o} value={o}>{o}</option>)}</select></label>;
}
function Score({ title, value }: { title: string; value: number }) {
  return <div className="rounded-2xl border border-white/10 bg-black/35 p-3"><div className="mb-2 flex items-center justify-between"><div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/35">{title}</div><div className="text-sm font-bold text-white">{value}</div></div><div className="h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-fuchsia-500 to-cyan-400" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div></div>;
}
function Info({ title, value }: { title: string; value: string }) {
  return <div className="mt-2 rounded-2xl border border-white/10 bg-white/[0.04] p-3"><div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/35">{title}</div><div className="text-xs leading-5 text-white/70">{value}</div></div>;
}
function List({ title, items }: { title: string; items: string[] }) {
  return <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4"><h3 className="mb-3 font-bold">{title}</h3><div className="space-y-2">{items.map((x, i) => <div key={i} className="rounded-2xl border border-white/10 bg-black/35 p-3 text-sm leading-5 text-white/75">{x}</div>)}</div></div>;
}
