"use client";

import { TerminalSquare } from "lucide-react";
import type { WorkflowLog } from "./types";

export default function ExecutionPanelPro({ logs }: { logs: WorkflowLog[] }) {
  return (
    <div className="h-[230px] rounded-[28px] border border-white/10 bg-black/55 p-4">
      <div className="flex items-center gap-2">
        <TerminalSquare className="h-5 w-5 text-cyan-200" />
        <div>
          <p className="text-[11px] uppercase tracking-[0.25em] text-cyan-100/60">Runtime Console</p>
          <h3 className="text-lg font-bold text-white">Live Execution</h3>
        </div>
      </div>

      <div className="mt-3 h-[150px] overflow-auto rounded-2xl border border-white/10 bg-black/50 p-3 font-mono text-xs leading-6">
        {logs.length === 0 ? (
          <p className="text-white/35">Workflow not started yet.</p>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className={
                log.level === "success"
                  ? "text-emerald-200"
                  : log.level === "warning"
                  ? "text-amber-200"
                  : log.level === "error"
                  ? "text-red-200"
                  : "text-white/65"
              }
            >
              <span className="text-white/25">[{log.timestamp}]</span> {log.message}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
