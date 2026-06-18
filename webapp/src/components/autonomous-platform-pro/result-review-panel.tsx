"use client";

import { Bot, CheckCircle2, RefreshCcw, X } from "lucide-react";
import { inferRenderableAssetKind } from "@/lib/media";

type Props = {
  open: boolean;
  title: string;
  kind: "image" | "video";
  url: string;
  busy?: boolean;
  onKeep: () => void;
  onRegenerate: () => void;
  onClose: () => void;
};

export default function ResultReviewPanel({
  open,
  title,
  kind,
  url,
  busy,
  onKeep,
  onRegenerate,
  onClose,
}: Props) {
  if (!open || !url) return null;

  const renderKind = inferRenderableAssetKind(url, kind);

  return (
    <div className="border-b border-white/10 bg-white/[0.03] px-5 py-5 backdrop-blur-xl">
      <div className="grid gap-4 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="overflow-hidden rounded-[28px] border border-white/10 bg-black/60 shadow-[0_25px_80px_rgba(0,0,0,0.35)]">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-bold text-white">
              <Bot className="h-4 w-4 text-cyan-300" />
              Latest {kind === "image" ? "Image" : "Video"} Result
            </div>
            <button
              onClick={onClose}
              className="rounded-xl p-2 text-white/55 hover:bg-white/10 hover:text-white"
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="bg-black p-4">
            {renderKind === "video" ? (
              <video src={url} controls className="max-h-[460px] w-full rounded-2xl bg-black object-contain" />
            ) : (
              <img src={url} alt={title} className="max-h-[460px] w-full rounded-2xl bg-black object-contain" />
            )}
          </div>
        </div>

        <div className="rounded-[28px] border border-cyan-300/15 bg-gradient-to-b from-cyan-300/10 to-fuchsia-400/10 p-5 shadow-[0_25px_80px_rgba(0,0,0,0.25)]">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-[11px] font-bold uppercase tracking-[0.22em] text-cyan-100">
            <Bot className="h-4 w-4" />
            Review Panel
          </div>

          <h3 className="mt-4 text-2xl font-black text-white">Review the generated result</h3>
          <p className="mt-3 text-sm leading-6 text-white/70">
            A new {kind} was generated. You can keep this result and continue the workflow,
            or request another version.
          </p>

          <div className="mt-5 rounded-2xl border border-white/10 bg-black/30 p-4 text-sm leading-6 text-white/80">
            <p className="font-semibold text-white">Review question</p>
            <p className="mt-2">Do you want to keep this {kind}, or do you want another version?</p>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={onKeep}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-2xl bg-emerald-500 px-5 py-3 text-sm font-black text-white hover:brightness-110 disabled:opacity-60"
            >
              <CheckCircle2 className="h-4 w-4" />
              Keep Result
            </button>
            <button
              onClick={onRegenerate}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/10 px-5 py-3 text-sm font-black text-white hover:bg-white/15 disabled:opacity-60"
            >
              <RefreshCcw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
              Regenerate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
