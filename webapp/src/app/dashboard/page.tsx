"use client";

import { useEffect, type ElementType } from "react";
import Link from "next/link";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/useAuth";
import { useGenerations } from "@/hooks/useGenerations";
import { useCreditBalance } from "@/hooks/useCredits";
import {
  Image as ImageIcon,
  History,
  CreditCard,
  Loader2,
  ArrowUpRight,
  Clock3,
  Activity,
  UserRound,
} from "lucide-react";
import { formatCredits } from "@/lib/utils";

export default function DashboardPage() {
  const { user, isLoading: authLoading } = useAuth();
  const { data: generations, isLoading: genLoading, refetch } = useGenerations({
    page_size: 5,
  });
  const { data: balance, isLoading: balanceLoading } = useCreditBalance();

  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, 5000);

    return () => clearInterval(interval);
  }, [refetch]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center text-white">
        <div className="relative flex flex-col items-center gap-4">
          <div className="absolute h-32 w-32 rounded-full bg-fuchsia-500/20 blur-3xl" />
          <Loader2 className="relative h-10 w-10 animate-spin text-fuchsia-400" />
          <p className="relative text-sm uppercase tracking-[0.3em] text-white/50">
            Loading dashboard
          </p>
        </div>
      </div>
    );
  }

  const items = generations?.items || [];
  const totalGenerations = generations?.total || 0;
  const imageCount = items.filter((g: any) => g.generation_type === "image" || g.generation_type === "img2img").length;
  const referenceCount = items.filter((g: any) => g.generation_type === "img2img").length;
  const creditsValue = balanceLoading ? "..." : formatCredits(balance?.credits || 0);
  const displayName = user?.full_name || user?.email?.split("@")[0] || "creator";

  return (
    <DashboardLayout>
      <div className="dashboard-screen human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        {/* Background */}
        <div className="dashboard-background absolute inset-0">
          <div className="dashboard-background-gradient absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(239,68,68,0.10),transparent_30%),linear-gradient(180deg,#040404_0%,#090909_100%)]" />
          <div
            className="dashboard-background-grid absolute inset-0 opacity-[0.16]"
            style={{
              backgroundImage:
                "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="dashboard-orb dashboard-orb-1 absolute left-[10%] top-[16%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl animate-pulse" />
          <div className="dashboard-orb dashboard-orb-2 absolute right-[10%] top-[28%] h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl animate-pulse" />
          <div className="dashboard-orb dashboard-orb-3 absolute bottom-[10%] left-[35%] h-64 w-64 rounded-full bg-red-500/10 blur-3xl animate-pulse" />
        </div>

        <div className="relative z-10 p-6 md:p-8 xl:p-10">
          {/* Header */}
          <div className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-fuchsia-300" />
                Overview
              </div>

              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Welcome back, <span className="text-fuchsia-300">{displayName}</span>
              </h1>

              <p className="human-note mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                {user?.email} • {user?.subscription_tier || "free"} plan • {formatCredits(balance?.credits || user?.credits || 0)} available credits
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:flex">
              <Link
                href="/generate/image"
                className="dashboard-cta dashboard-cta-primary inline-flex items-center justify-center gap-2 rounded-full border border-fuchsia-500/30 bg-fuchsia-500/15 px-5 py-3 text-sm font-medium text-fuchsia-200 backdrop-blur transition hover:bg-fuchsia-500/20"
              >
                <ImageIcon className="h-4 w-4" />
                New image
              </Link>

              <Link
                href="/generate/image-to-image"
                className="dashboard-cta dashboard-cta-secondary inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-white/75 backdrop-blur transition hover:border-white/20 hover:bg-white/10 hover:text-white"
              >
                <ImageIcon className="h-4 w-4" />
                Image-to-image
              </Link>
            </div>
          </div>

          {/* Stats */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              icon={Activity}
              title="Total Generations"
              value={genLoading ? "..." : totalGenerations.toString()}
              color="text-fuchsia-300"
              glow="from-fuchsia-500/20 to-transparent"
              subtitle="All content created"
            />
            <StatCard
              icon={ImageIcon}
              title="Images"
              value={genLoading ? "..." : imageCount.toString()}
              color="text-cyan-300"
              glow="from-cyan-500/20 to-transparent"
              subtitle="Visual generations"
            />
            <StatCard
              icon={ImageIcon}
              title="Image-to-Image"
              value={genLoading ? "..." : referenceCount.toString()}
              color="text-violet-300"
              glow="from-violet-500/20 to-transparent"
              subtitle="Reference-based generations"
            />
            <StatCard
              icon={CreditCard}
              title="Credits"
              value={creditsValue}
              color="text-emerald-300"
              glow="from-emerald-500/20 to-transparent"
              subtitle="Available balance"
            />
          </div>

          {/* Main content */}
          <div className="mt-8 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            {/* Left */}
            <div className="space-y-6">
              {/* Quick actions */}
              <section className="dashboard-panel rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="mb-5 flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">Quick Actions</h2>
                    <p className="text-sm text-white/50">
                      Launch your most used flows
                    </p>
                  </div>

                  <div className="hidden h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5 md:flex">
                    <Activity className="h-5 w-5 text-fuchsia-300" />
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <ActionCard
                    icon={ImageIcon}
                    title="Generate Image"
                    description="Create visuals from text prompts"
                    href="/generate/image"
                    color="from-cyan-500/20 to-fuchsia-500/10"
                  />
                  <ActionCard
                    icon={ImageIcon}
                    title="Image-to-Image"
                    description="Transform references into polished visuals"
                    href="/generate/image-to-image"
                    color="from-violet-500/20 to-cyan-500/10"
                  />
                  <ActionCard
                    icon={History}
                    title="View History"
                    description="Explore your latest outputs and results"
                    href="/history"
                    color="from-fuchsia-500/20 to-red-500/10"
                  />
                </div>
              </section>

              {/* Recent Activity */}
              <section className="dashboard-panel rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
                <div className="mb-5 flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">Recent Activity</h2>
                    <p className="text-sm text-white/50">
                      Your latest generations in real time
                    </p>
                  </div>

                  <Link
                    href="/history"
                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/65 transition hover:border-white/20 hover:bg-white/10 hover:text-white"
                  >
                    View all
                    <ArrowUpRight className="h-4 w-4" />
                  </Link>
                </div>

                <div className="rounded-[22px] border border-white/10 bg-black/25 overflow-hidden">
                  {genLoading ? (
                    <div className="flex min-h-[220px] items-center justify-center">
                      <div className="text-center">
                        <Loader2 className="mx-auto h-8 w-8 animate-spin text-fuchsia-300" />
                        <p className="mt-3 text-sm text-white/45">
                          Loading recent activity...
                        </p>
                      </div>
                    </div>
                  ) : items.length > 0 ? (
                    <div className="divide-y divide-white/10">
                      {items.slice(0, 5).map((gen: any, index: number) => (
                        <div
                          key={gen.id}
                          className="group flex flex-col gap-4 p-4 transition hover:bg-white/[0.03] md:flex-row md:items-center md:justify-between"
                        >
                          <div className="flex items-start gap-4">
                            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                              {gen.generation_type === "image" || gen.generation_type === "img2img" ? (
                                <ImageIcon className="h-5 w-5 text-cyan-300" />
                              ) : (
                                <ImageIcon className="h-5 w-5 text-violet-300" />
                              )}
                            </div>

                            <div className="min-w-0">
                              <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-white/35">
                                <span>#{index + 1}</span>
                                <span>•</span>
                                <span>{gen.generation_type}</span>
                              </div>

                              <p className="max-w-xl truncate text-sm font-medium text-white/90 md:text-base">
                                {gen.prompt}
                              </p>

                              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-white/45">
                                <span className="inline-flex items-center gap-1">
                                  <CreditCard className="h-3.5 w-3.5" />
                                  {gen.credits_used} credits
                                </span>
                                <span className="inline-flex items-center gap-1">
                                  <Clock3 className="h-3.5 w-3.5" />
                                  {gen.status}
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center justify-end">
                            <StatusBadge status={gen.status} />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex min-h-[220px] items-center justify-center p-8 text-center">
                      <div>
                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-white/5">
                          <History className="h-7 w-7 text-fuchsia-300" />
                        </div>
                        <p className="text-lg font-medium text-white/75">
                          No generations yet
                        </p>
                        <p className="mt-2 text-sm text-white/45">
                          Start creating your first visual or reference-based image.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </div>

            {/* Right */}
            <div className="space-y-6">
              {/* Spotlight */}
              <section className="dashboard-panel dashboard-spotlight relative overflow-hidden rounded-[26px] border border-white/10 bg-white/[0.04] p-6 backdrop-blur-xl">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(217,70,239,0.18),transparent_30%),radial-gradient(circle_at_80%_30%,rgba(34,211,238,0.12),transparent_28%),radial-gradient(circle_at_60%_90%,rgba(239,68,68,0.12),transparent_28%)]" />
                <div className="relative z-10">
                  <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.24em] text-white/50">
                    <span className="h-2 w-2 rounded-full bg-fuchsia-300" />
                    Workspace
                  </div>

                  <h3 className="text-2xl font-black leading-tight">
                    Build your visual workflow
                  </h3>

                  <p className="mt-3 text-sm leading-6 text-white/60">
                    Generate visuals, monitor credits, and review your outputs in
                    one clean control panel.
                  </p>

                  <div className="mt-6 flex flex-wrap gap-3">
                    <Link
                      href="/generate/image"
                      className="inline-flex items-center gap-2 rounded-full bg-fuchsia-600 px-5 py-3 text-sm font-medium text-white shadow-[0_0_34px_rgba(217,70,239,0.25)] transition hover:bg-fuchsia-500"
                    >
                      Start creating
                      <ArrowUpRight className="h-4 w-4" />
                    </Link>

                    <Link
                      href="/history"
                      className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-white/75 transition hover:border-white/20 hover:bg-white/10 hover:text-white"
                    >
                      Open history
                    </Link>
                  </div>
                </div>
              </section>

              {/* Mini insights */}
              <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
                <MiniPanel
                  title="Account"
                  value={user?.email?.split("@")[0] || "User"}
                  icon={UserRound}
                  color="text-fuchsia-300"
                />
                <MiniPanel
                  title="Live Credits"
                  value={creditsValue}
                  icon={CreditCard}
                  color="text-emerald-300"
                />
              </section>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function StatCard({
  icon: Icon,
  title,
  value,
  color,
  glow,
  subtitle,
}: {
  icon: ElementType;
  title: string;
  value: string;
  color: string;
  glow: string;
  subtitle: string;
}) {
  return (
    <div className="dashboard-card dashboard-stat-card group relative overflow-hidden rounded-[24px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:border-white/20">
      <div className={`absolute inset-0 bg-gradient-to-br ${glow} opacity-60`} />
      <div className="relative z-10 flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-white/45">
            {title}
          </p>
          <p className="mt-3 text-3xl font-black tracking-tight text-white">
            {value}
          </p>
          <p className="mt-2 text-sm text-white/50">{subtitle}</p>
        </div>

        <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 shadow-inner">
          <Icon className={`h-6 w-6 ${color}`} />
        </div>
      </div>
    </div>
  );
}

function ActionCard({
  icon: Icon,
  title,
  description,
  href,
  color,
}: {
  icon: ElementType;
  title: string;
  description: string;
  href: string;
  color: string;
}) {
  return (
    <Link href={href} className="group block h-full">
      <div className="dashboard-card dashboard-action-card relative h-full overflow-hidden rounded-[24px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl transition duration-300 hover:-translate-y-1 hover:border-white/20">
        <div className={`absolute inset-0 bg-gradient-to-br ${color} opacity-50`} />
        <div className="relative z-10">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-black/20">
            <Icon className="h-6 w-6 text-white" />
          </div>

          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-white/55">{description}</p>

          <div className="mt-5 inline-flex items-center gap-2 text-sm text-white/70 transition group-hover:text-white">
            Open
            <ArrowUpRight className="h-4 w-4" />
          </div>
        </div>
      </div>
    </Link>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
    pending: "border-amber-400/20 bg-amber-400/10 text-amber-300",
    processing: "border-cyan-400/20 bg-cyan-400/10 text-cyan-300",
    failed: "border-red-400/20 bg-red-400/10 text-red-300",
  };

  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium capitalize ${
        styles[status] || "border-white/10 bg-white/5 text-white/70"
      }`}
    >
      {status}
    </span>
  );
}

function MiniPanel({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string;
  value: string;
  icon: ElementType;
  color: string;
}) {
  return (
    <div className="dashboard-card dashboard-mini-panel rounded-[24px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-white/45">
            {title}
          </p>
          <p className="mt-3 break-all text-lg font-semibold text-white/90">
            {value}
          </p>
        </div>

        <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
          <Icon className={`h-5 w-5 ${color}`} />
        </div>
      </div>
    </div>
  );
}