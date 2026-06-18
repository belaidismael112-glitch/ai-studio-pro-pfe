"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { AdminNav } from "@/components/admin/admin-nav";

type AdminShellProps = {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

/**
 * A shared wrapper used by all admin pages.
 * Adds a neon/glass background + subtle motion, but stays lightweight (no extra deps).
 */
export function AdminShell({ title, subtitle, right, children, className }: AdminShellProps) {
  return (
    <div className={cn("human-admin-shell relative overflow-hidden rounded-3xl border border-white/10 bg-black/60 p-6 md:p-8", className)}>
      {/* Background */}
      <div className="pointer-events-none absolute inset-0">
        {/* soft grid */}
        <div className="absolute inset-0 opacity-[0.12] [background-size:24px_24px] [background-image:radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.35)_1px,transparent_0)]" />
        {/* glow orbs */}
        <div className="absolute -top-44 -left-44 h-[520px] w-[520px] rounded-full bg-fuchsia-500/20 blur-3xl animate-[pulse_10s_ease-in-out_infinite]" />
        <div className="absolute -bottom-52 -right-52 h-[620px] w-[620px] rounded-full bg-cyan-500/20 blur-3xl animate-[pulse_12s_ease-in-out_infinite]" />
        <div className="absolute top-1/2 left-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-500/10 blur-3xl animate-[pulse_14s_ease-in-out_infinite]" />
        {/* vignette */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/10 to-black/60" />
      </div>

      <div className="relative">
        {/* Header */}
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 backdrop-blur">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_20px_rgba(52,211,153,0.65)]" />
              Admin mode
            </div>

            <h1 className="mt-3 text-2xl md:text-3xl font-bold tracking-tight">
              <span className="bg-gradient-to-r from-white via-white to-white/60 bg-clip-text text-transparent">
                {title}
              </span>
            </h1>

            {subtitle ? (
              <p className="mt-2 text-sm text-white/65 max-w-2xl">
                {subtitle}
              </p>
            ) : null}
          </div>

          {right ? <div className="flex items-center gap-2">{right}</div> : null}
        </div>

        {/* Nav */}
        <div className="mt-6">
          <AdminNav />
        </div>

        {/* Content */}
        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}
