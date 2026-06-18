"use client";

import { AlertCircle, Clock3, Loader2, Maximize2 } from "lucide-react";
import { inferRenderableAssetKind } from "@/lib/media";
import { NODE_META } from "./registry";
import { formatMs } from "./workflow-utils";
import type { WorkflowNode } from "./types";

type Props = {
  node: WorkflowNode;
  selected: boolean;
  connectingFrom: string | null;
  onSelect: () => void;
  onOpenPreview?: (node: WorkflowNode) => void;
  onNodePointerDown: (event: React.PointerEvent) => void;
  onOutputPointerDown: (event: React.PointerEvent) => void;
  onInputPointerUp: (event: React.PointerEvent) => void;
  onNodePointerUp?: (event: React.PointerEvent) => void;
};

export default function WorkflowNodeCard({
  node,
  selected,
  connectingFrom,
  onSelect,
  onOpenPreview,
  onNodePointerDown,
  onOutputPointerDown,
  onInputPointerUp,
  onNodePointerUp,
}: Props) {
  const meta = NODE_META[node.kind];
  const Icon = meta.icon;
  const canReceiveConnection = !!connectingFrom && connectingFrom !== node.id;
  const previewKind = inferRenderableAssetKind(node.previewUrl, node.previewType);

  return (
    <div
      onPointerDown={onNodePointerDown}
      onPointerUp={onNodePointerUp}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      className={`absolute select-none rounded-[22px] border p-3 shadow-[0_18px_70px_rgba(0,0,0,0.45)] backdrop-blur-xl transition ${
        selected
          ? "border-cyan-300/60 bg-white/[0.10] ring-4 ring-cyan-300/10"
          : canReceiveConnection
          ? "border-cyan-300/45 bg-cyan-300/[0.06]"
          : "border-white/10 bg-black/75 hover:border-white/20"
      }`}
      style={{ left: node.x, top: node.y, width: node.width, touchAction: "none" }}
    >
      <button
        type="button"
        onPointerDown={(e) => e.stopPropagation()}
        onPointerUp={(e) => {
          e.stopPropagation();
          onInputPointerUp(e);
        }}
        className={`absolute -left-3 top-[86px] z-20 h-6 w-6 -translate-y-1/2 rounded-full border bg-black transition ${
          canReceiveConnection
            ? "scale-125 border-cyan-200 shadow-[0_0_26px_rgba(34,211,238,0.85)]"
            : "border-cyan-200/50 shadow-[0_0_20px_rgba(34,211,238,0.45)]"
        }`}
        title="Input"
      />

      <button
        type="button"
        onPointerDown={(e) => {
          e.stopPropagation();
          onOutputPointerDown(e);
        }}
        className="absolute -right-3 top-[86px] z-20 h-6 w-6 -translate-y-1/2 rounded-full border border-fuchsia-200/50 bg-black shadow-[0_0_20px_rgba(217,70,239,0.45)] transition hover:scale-125 hover:border-fuchsia-100"
        title="Output"
      />

      <div className="flex items-start gap-3">
        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${meta.color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-bold text-white">{node.title}</div>
          <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-white/35">{meta.role}</div>
        </div>
      </div>

      <p className="mt-3 line-clamp-2 text-[11px] leading-5 text-white/45">{node.description}</p>

      {node.status === "running" && !node.previewUrl && (
        <div className="mt-3 flex items-center gap-2 rounded-2xl border border-cyan-300/15 bg-cyan-300/10 p-3 text-[11px] text-cyan-100">
          <Loader2 className="h-4 w-4 animate-spin" />
          Running...
        </div>
      )}

      {node.previewUrl && (
        <div className="mt-3 overflow-hidden rounded-2xl border border-white/10 bg-black">
          <div className="flex items-center justify-end border-b border-white/10 bg-white/[0.03] px-2 py-2">
            <button
              type="button"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                onOpenPreview?.(node);
              }}
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/10 px-2.5 py-1.5 text-[11px] font-semibold text-white/80 hover:bg-white/15"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              Open
            </button>
          </div>
          {previewKind === "video" ? (
            <video src={node.previewUrl} controls className="h-36 w-full object-cover" />
          ) : (
            <img src={node.previewUrl} alt={node.title} className="h-36 w-full object-cover" />
          )}
        </div>
      )}

      {node.outputText && !node.previewUrl && (
        <div className="mt-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-[11px] leading-5 text-white/55">
          {node.outputText}
        </div>
      )}

      {node.error && (
        <div className="mt-3 flex gap-2 rounded-2xl border border-red-400/20 bg-red-500/10 p-3 text-[11px] leading-5 text-red-100">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="line-clamp-3">{node.error}</span>
        </div>
      )}

      <div className="mt-3">
        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className={`h-full rounded-full transition-all ${
              node.status === "error"
                ? "bg-red-400"
                : node.status === "success"
                ? "bg-emerald-400"
                : "bg-gradient-to-r from-cyan-400 to-fuchsia-400"
            }`}
            style={{ width: `${Math.max(0, Math.min(100, node.progress))}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px]">
          <span
            className={`rounded-full px-2 py-1 uppercase tracking-[0.14em] ${
              node.status === "running"
                ? "bg-cyan-400/15 text-cyan-100"
                : node.status === "success"
                ? "bg-emerald-400/15 text-emerald-100"
                : node.status === "error"
                ? "bg-red-400/15 text-red-100"
                : "bg-white/10 text-white/45"
            }`}
          >
            {node.status}
          </span>
          <span className="inline-flex items-center gap-1 text-white/35">
            <Clock3 className="h-3 w-3" />
            {formatMs(node.elapsedMs)}
          </span>
        </div>
      </div>
    </div>
  );
}
