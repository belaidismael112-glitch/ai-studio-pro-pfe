"use client";

import { useEffect, useMemo, useState, type ElementType } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { api } from "@/lib/api";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock3,
  GitCompare,
  Loader2,
  ShieldAlert,
  Zap,
} from "lucide-react";

type CatalogItem = {
  id: string;
  name: string;
  type: string;
  strengths: string[];
  weaknesses: string[];
  recommended_for: string[];
};

type Stats = {
  total: number;
  avg_time: number;
  success_rate: number;
  completed: number;
  failed: number;
};

export default function ComparePage() {
  const [days, setDays] = useState(30);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [stats, setStats] = useState<Record<string, Stats>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get(`/models/compare?days=${days}`);
        if (!mounted) return;
        setCatalog(res.data?.catalog ?? []);
        setStats(res.data?.stats ?? {});
      } catch (e: any) {
        if (!mounted) return;
        setError(e?.response?.data?.detail ?? "Failed to load model comparison");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [days]);

  const rows = useMemo(() => {
    return catalog.map((m) => {
      const s = stats[m.id] || stats[m.name] || stats["unknown"];
      return { model: m, stats: s };
    });
  }, [catalog, stats]);

  const totals = useMemo(() => {
    const values = rows.map((r) => r.stats).filter(Boolean);
    const generations = values.reduce((sum, s) => sum + (s?.total ?? 0), 0);
    const failed = values.reduce((sum, s) => sum + (s?.failed ?? 0), 0);
    const avgSuccess = values.length
      ? values.reduce((sum, s) => sum + (s?.success_rate ?? 0), 0) / values.length
      : 0;
    return { generations, failed, avgSuccess };
  }, [rows]);

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.15),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(59,130,246,0.11),transparent_32%),linear-gradient(180deg,#040404_0%,#090909_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.16]"
            style={{
              backgroundImage:
                "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="absolute left-[9%] top-[16%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute right-[10%] top-[24%] h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="absolute bottom-[9%] left-[40%] h-64 w-64 rounded-full bg-violet-500/10 blur-3xl" />
        </div>

        <div className="relative z-10 p-6 md:p-8 xl:p-10">
          <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <GitCompare className="h-3.5 w-3.5 text-fuchsia-300" />
                Comparison
              </div>

              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Model <span className="text-fuchsia-400">Comparison</span>
              </h1>

              <p className="human-note mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Compare model strengths, usage quality, speed, and failure rates
                in one clean dashboard view.
              </p>
            </div>

            <div className="rounded-[22px] border border-white/10 bg-white/[0.045] p-3 backdrop-blur-xl">
              <div className="mb-2 text-[10px] uppercase tracking-[0.24em] text-white/40">
                Usage window
              </div>
              <select
                className="h-12 min-w-[180px] rounded-2xl border border-white/10 bg-black/45 px-4 text-sm text-white outline-none ring-0 transition focus:border-fuchsia-300/40"
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value, 10))}
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </div>
          </div>

          <div className="mb-6 grid gap-4 md:grid-cols-3">
            <InsightCard icon={BarChart3} label="Tracked models" value={rows.length} tone="text-fuchsia-300" />
            <InsightCard icon={BarChart3} label="Generations" value={totals.generations} tone="text-cyan-300" />
            <InsightCard icon={ShieldAlert} label="Failed jobs" value={totals.failed} tone="text-red-300" />
          </div>

          {loading ? (
            <div className="flex min-h-[420px] items-center justify-center rounded-[26px] border border-white/10 bg-white/[0.04] backdrop-blur-xl">
              <div className="text-center">
                <Loader2 className="mx-auto h-8 w-8 animate-spin text-fuchsia-300" />
                <p className="mt-3 text-sm uppercase tracking-[0.28em] text-white/45">
                  Loading comparison
                </p>
              </div>
            </div>
          ) : error ? (
            <div className="rounded-[26px] border border-red-500/25 bg-red-500/10 p-5 text-red-100 backdrop-blur-xl">
              {error}
            </div>
          ) : rows.length === 0 ? (
            <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-10 text-center backdrop-blur-xl">
              <BarChart3 className="mx-auto h-9 w-9 text-fuchsia-300" />
              <h2 className="mt-4 text-xl font-semibold text-white">No models yet</h2>
              <p className="mt-2 text-sm text-white/50">
                No comparison pipelines were returned by the backend. Check the model comparison API and database connection.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {rows.map(({ model, stats: modelStats }, index) => {
                const successPct = ((modelStats?.success_rate ?? 0) * 100).toFixed(1);
                return (
                  <div
                    key={model.id}
                    className="group relative overflow-hidden rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:border-white/20 hover:bg-white/[0.055]"
                  >
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_12%,rgba(217,70,239,0.16),transparent_28%),radial-gradient(circle_at_84%_18%,rgba(34,211,238,0.10),transparent_26%)] opacity-80" />
                    <div className="relative z-10">
                      <div className="mb-5 flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-black/30 text-fuchsia-200 shadow-[0_0_28px_rgba(217,70,239,0.12)]">
                            <Zap className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="text-[11px] uppercase tracking-[0.24em] text-white/35">
                              #{index + 1} • {model.type}
                            </div>
                            <h2 className="mt-1 text-xl font-bold text-white">{model.name}</h2>
                            <p className="mt-1 break-all text-xs text-white/40">id: {model.id}</p>
                          </div>
                        </div>
                        <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-200">
                          {successPct}% ok
                        </div>
                      </div>

                      <div className="mb-5 grid grid-cols-2 gap-3">
                        <Metric icon={Activity} label="Generations" value={modelStats?.total ?? 0} />
                        <Metric icon={CheckCircle2} label="Success rate" value={`${successPct}%`} />
                        <Metric icon={Clock3} label="Avg time" value={`${(modelStats?.avg_time ?? 0).toFixed(2)} s`} />
                        <Metric icon={ShieldAlert} label="Failed" value={modelStats?.failed ?? 0} />
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <ModelList title="Strengths" items={model.strengths} tone="border-cyan-400/15 bg-cyan-400/5" />
                        <ModelList title="Weaknesses" items={model.weaknesses} tone="border-red-400/15 bg-red-400/5" />
                      </div>

                      <div className="mt-4 rounded-[20px] border border-white/10 bg-black/25 p-4">
                        <div className="mb-3 text-[11px] uppercase tracking-[0.22em] text-white/45">
                          Recommended for
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {model.recommended_for.map((x) => (
                            <span
                              key={x}
                              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70"
                            >
                              {x}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function InsightCard({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: ElementType;
  label: string;
  value: string | number;
  tone: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-[24px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(217,70,239,0.11),transparent_32%)]" />
      <div className="relative flex items-center justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-white/40">{label}</p>
          <p className="mt-2 text-3xl font-black text-white">{value}</p>
        </div>
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
          <Icon className={`h-5 w-5 ${tone}`} />
        </div>
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: ElementType; label: string; value: any }) {
  return (
    <div className="rounded-[18px] border border-white/10 bg-black/25 p-4">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-white/40">
        <Icon className="h-3.5 w-3.5 text-fuchsia-300" />
        {label}
      </div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
    </div>
  );
}

function ModelList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div className={`rounded-[20px] border p-4 ${tone}`}>
      <div className="mb-3 text-[11px] uppercase tracking-[0.22em] text-white/45">{title}</div>
      <ul className="space-y-2 text-sm text-white/65">
        {items.map((x) => (
          <li key={x} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-white/45" />
            <span>{x}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
