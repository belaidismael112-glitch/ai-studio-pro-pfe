"use client";

import { useEffect, useMemo, useState, type ElementType } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { AdminShell } from "@/components/admin/admin-shell";
import { adminApi, AdminOverview, SeriesPoint, TopModel } from "@/lib/admin-api";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";
import {
  Loader2,
  Users,
  Layers,
  Euro,
  MessageSquareText,
  ArrowUpRight,
  RefreshCw,
  Shield,
  UserCheck,
  Coins,
  AlertTriangle,
  Image as ImageIcon,
} from "lucide-react";

export default function AdminOverviewPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [gpd, setGpd] = useState<SeriesPoint[]>([]);
  const [topModels, setTopModels] = useState<TopModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // guard
  useEffect(() => {
    if (user && !user.is_admin) router.replace("/dashboard");
  }, [user, router]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [o, g, m] = await Promise.all([
        adminApi.overview(),
        adminApi.generationsPerDay(30),
        adminApi.topModels(30),
      ]);
      setOverview(o);
      setGpd(Array.isArray(g) ? g : []);
      setTopModels(Array.isArray(m) ? m : []);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load admin analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.is_admin) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.is_admin]);

  const max = useMemo(() => Math.max(1, ...gpd.map((p) => p.count)), [gpd]);

  return (
    <DashboardLayout>
      <AdminShell
        title="Admin Control Room"
        subtitle="KPI + usage insights + moderation tools. Built for speed, clarity, and control."
        right={
          <button
            onClick={load}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 hover:bg-white/10 hover:text-white transition"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        }
      >
        {!user?.is_admin ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-white/80">
            Checking permissions…
          </div>
        ) : loading ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-white/70" />
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-red-100">
            {error}
          </div>
        ) : (
          <div className="space-y-6">
            {/* KPI cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              <KpiCard
                icon={Users}
                title="Total users"
                value={overview?.total_users ?? 0}
                accent="from-cyan-400/20 to-cyan-400/0"
              />
              <KpiCard
                icon={Layers}
                title="Total generations"
                value={overview?.total_generations ?? 0}
                accent="from-fuchsia-400/20 to-fuchsia-400/0"
              />
              <KpiCard
                icon={Euro}
                title="Total revenue"
                value={(overview?.total_revenue ?? 0).toFixed(2) + " €"}
                accent="from-emerald-400/20 to-emerald-400/0"
              />
              <KpiCard
                icon={MessageSquareText}
                title="Open tickets"
                value={overview?.open_tickets ?? "—"}
                accent="from-amber-400/20 to-amber-400/0"
              />
              <KpiCard
                icon={UserCheck}
                title="Active users"
                value={overview?.active_users ?? "—"}
                accent="from-emerald-400/20 to-emerald-400/0"
              />
              <KpiCard
                icon={Coins}
                title="Credits in system"
                value={overview?.total_credits ?? "—"}
                accent="from-cyan-400/20 to-cyan-400/0"
              />
              <KpiCard
                icon={ImageIcon}
                title="Image & ref jobs"
                value={overview?.image_generations ?? "—"}
                accent="from-violet-400/20 to-violet-400/0"
              />
              <KpiCard
                icon={Shield}
                title="Build mode"
                value="Image-first"
                accent="from-fuchsia-400/20 to-fuchsia-400/0"
              />
              <KpiCard
                icon={AlertTriangle}
                title="Failed jobs"
                value={overview?.failed_generations ?? "—"}
                accent="from-red-400/20 to-red-400/0"
              />
            </div>

            {/* Quick actions */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <QuickLink
                title="Manage users"
                description="Promote admins, update credits, disable accounts."
                href="/admin/users"
              />
              <QuickLink
                title="Moderate generations"
                description="Review outputs & delete abusive content."
                href="/admin/generations"
              />
              <QuickLink
                title="Reclamations"
                description="Handle support tickets and requests."
                href="/admin/complaints"
              />
            </div>

            {/* Analytics */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-white">Generations per day</h2>
                  <span className="text-xs text-white/50">last 30 days</span>
                </div>

                <div className="mt-4 space-y-2">
                  {gpd.length === 0 ? (
                    <div className="text-white/60 text-sm">No data yet.</div>
                  ) : (
                    gpd.map((p) => (
                      <div key={p.day} className="flex items-center gap-3">
                        <div className="w-24 text-xs text-white/55">
                          {new Date(p.day).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                        </div>

                        <div className="flex-1 h-3 rounded-full bg-white/10 overflow-hidden">
                          <div
                            className="h-3 rounded-full bg-gradient-to-r from-fuchsia-400/80 to-cyan-400/80"
                            style={{ width: `${Math.round((p.count / max) * 100)}%` }}
                          />
                        </div>

                        <div className="w-10 text-right text-xs text-white/80">{p.count}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-white">Top models</h2>
                  <span className="text-xs text-white/50">last 30 days</span>
                </div>

                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-white/55">
                        <th className="py-2 pr-2 font-medium">Model</th>
                        <th className="py-2 pr-2 font-medium">Count</th>
                        <th className="py-2 pr-2 font-medium">Avg time (s)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topModels.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="py-4 text-white/55">
                            No data yet.
                          </td>
                        </tr>
                      ) : (
                        topModels.map((m) => (
                          <tr key={m.model} className="border-t border-white/10">
                            <td className="py-2 pr-2 text-white/85">{m.model}</td>
                            <td className="py-2 pr-2 text-white/85">{m.count}</td>
                            <td className="py-2 pr-2 text-white/85">{m.avg_time?.toFixed?.(2) ?? m.avg_time}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 rounded-2xl border border-white/10 bg-black/30 p-4 text-white/60 text-sm">
                  <div className="flex items-start gap-3">
                    <Shield className="h-5 w-5 text-white/60 mt-0.5" />
                    <p>
                      Production checklist: monitor failed jobs, open tickets, active users, payments, and credit balances before launch.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </AdminShell>
    </DashboardLayout>
  );
}

function KpiCard({
  icon: Icon,
  title,
  value,
  accent,
}: {
  icon: ElementType;
  title: string;
  value: any;
  accent: string;
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur transition-all",
        "hover:-translate-y-0.5 hover:bg-white/10 hover:border-white/15"
      )}
    >
      <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br", accent)} />
      <div className="relative flex items-center justify-between">
        <div>
          <div className="text-xs text-white/55">{title}</div>
          <div className="mt-1 text-2xl font-bold text-white">{value}</div>
        </div>

        <div className="h-11 w-11 rounded-2xl border border-white/10 bg-black/30 flex items-center justify-center shadow-[0_10px_30px_-18px_rgba(236,72,153,0.7)] transition-transform group-hover:scale-[1.03]">
          <Icon className="h-5 w-5 text-white/80" />
        </div>
      </div>
    </div>
  );
}

function QuickLink({
  title,
  description,
  href,
}: {
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-5 backdrop-blur transition-all hover:-translate-y-0.5 hover:bg-white/10 hover:border-white/15"
    >
      <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-fuchsia-500/10 blur-2xl transition-opacity group-hover:opacity-100 opacity-60" />
      <div className="relative">
        <div className="flex items-center justify-between">
          <div className="text-white font-semibold">{title}</div>
          <ArrowUpRight className="h-4 w-4 text-white/60 group-hover:text-white transition" />
        </div>
        <p className="mt-2 text-sm text-white/60">{description}</p>
      </div>
    </Link>
  );
}
