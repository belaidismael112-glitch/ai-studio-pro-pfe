"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { NODE_META, NODE_ORDER } from "./registry";
import type { NodeKind } from "./types";

export default function NodePalette({ onAdd }: { onAdd: (kind: NodeKind) => void }) {
  const [q, setQ] = useState("");

  const filtered = useMemo(
    () =>
      NODE_ORDER.filter((kind) => {
        const meta = NODE_META[kind];
        return `${meta.label} ${meta.role} ${meta.description}`.toLowerCase().includes(q.toLowerCase());
      }),
    [q]
  );

  return (
    <aside className="flex h-full w-[300px] shrink-0 flex-col border-r border-white/10 bg-black/35 p-4">
      <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-100/65">Node Library</p>
      <h2 className="mt-2 text-2xl font-bold text-white">Blocks</h2>
      <p className="mt-2 text-sm leading-6 text-white/50">
        Click to add blocks. Connect nodes using the circular handles.
      </p>

      <div className="relative mt-4">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search nodes..."
          className="h-11 w-full rounded-2xl border border-white/10 bg-white/[0.04] pl-10 pr-3 text-sm text-white outline-none focus:border-cyan-300/40"
        />
      </div>

      <div className="mt-4 space-y-2 overflow-auto pr-1">
        {filtered.map((kind) => {
          const meta = NODE_META[kind];
          const Icon = meta.icon;

          return (
            <button
              key={kind}
              onClick={() => onAdd(kind)}
              className="group w-full rounded-2xl border border-white/10 bg-white/[0.035] p-3 text-left transition hover:border-cyan-300/30 hover:bg-white/[0.07]"
            >
              <div className="flex gap-3">
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${meta.color}`}>
                  <Icon className="h-5 w-5 text-white" />
                </div>
                <div className="min-w-0">
                  <div className="font-semibold text-white">{meta.label}</div>
                  <div className="mt-1 line-clamp-2 text-xs leading-5 text-white/42">
                    {meta.description}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
