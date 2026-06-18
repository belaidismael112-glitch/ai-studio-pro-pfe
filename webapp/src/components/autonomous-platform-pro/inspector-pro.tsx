"use client";

import { Copy, Trash2, SlidersHorizontal } from "lucide-react";
import { inferRenderableAssetKind } from "@/lib/media";
import type { WorkflowNode } from "./types";

export default function InspectorPro({
  node,
  onChange,
  onDelete,
  onDuplicate,
}: {
  node: WorkflowNode | null;
  onChange: (node: WorkflowNode) => void;
  onDelete: (id: string) => void;
  onDuplicate: (id: string) => void;
}) {
  const previewKind = node ? inferRenderableAssetKind(node.previewUrl, node.previewType) : "image";

  return (
    <aside className="flex h-full w-[360px] shrink-0 flex-col border-l border-white/10 bg-black/35 p-4">
      <div className="flex items-center gap-2">
        <SlidersHorizontal className="h-5 w-5 text-cyan-200" />
        <div>
          <p className="text-[11px] uppercase tracking-[0.26em] text-cyan-100/60">Inspector</p>
          <h2 className="text-xl font-bold text-white">Node Settings</h2>
        </div>
      </div>

      {!node ? (
        <div className="mt-6 rounded-3xl border border-dashed border-white/14 bg-white/[0.035] p-5 text-sm leading-7 text-white/50">
          Select a node. Edit prompt, cost, model settings, description and execution behavior here.
        </div>
      ) : (
        <div className="mt-5 overflow-auto pr-1">
          <label className="block">
            <span className="text-xs uppercase tracking-[0.2em] text-white/40">Title</span>
            <input
              value={node.title}
              onChange={(e) => onChange({ ...node, title: e.target.value })}
              className="mt-1 h-12 w-full rounded-2xl border border-white/10 bg-black/45 px-4 text-white outline-none focus:border-cyan-300/40"
            />
          </label>

          <label className="mt-4 block">
            <span className="text-xs uppercase tracking-[0.2em] text-white/40">Description</span>
            <textarea
              value={node.description}
              onChange={(e) => onChange({ ...node, description: e.target.value })}
              rows={4}
              className="mt-1 w-full rounded-2xl border border-white/10 bg-black/45 px-4 py-3 text-sm leading-6 text-white outline-none focus:border-cyan-300/40"
            />
          </label>

          <div className="mt-5 rounded-3xl border border-white/10 bg-white/[0.035] p-4">
            <div className="text-xs uppercase tracking-[0.22em] text-white/40">Configuration</div>
            <div className="mt-3 space-y-3">
              {Object.entries(node.config).map(([key, value]) => (
                <label key={key} className="block">
                  <span className="text-[11px] uppercase tracking-[0.16em] text-white/35">{key}</span>
                  <input
                    value={String(value)}
                    onChange={(e) => onChange({ ...node, config: { ...node.config, [key]: e.target.value } })}
                    className="mt-1 h-11 w-full rounded-xl border border-white/10 bg-black/45 px-3 text-sm text-white outline-none focus:border-cyan-300/40"
                  />
                </label>
              ))}
            </div>
          </div>

          {node.previewUrl && (
            <div className="mt-4 rounded-3xl border border-white/10 bg-black/45 p-3">
              <div className="mb-2 text-xs uppercase tracking-[0.22em] text-white/40">Preview</div>
              {previewKind === "video" ? (
                <video src={node.previewUrl} controls className="w-full rounded-2xl" />
              ) : (
                <img src={node.previewUrl} alt="preview" className="w-full rounded-2xl" />
              )}
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              onClick={() => onDuplicate(node.id)}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.05] px-3 py-3 text-sm font-semibold text-white/80 hover:bg-white/[0.08]"
            >
              <Copy className="h-4 w-4" />
              Duplicate
            </button>
            <button
              onClick={() => onDelete(node.id)}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-red-400/20 bg-red-500/10 px-3 py-3 text-sm font-semibold text-red-100 hover:bg-red-500/15"
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
