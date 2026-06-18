"use client";

import { useState } from "react";
import Image from "next/image";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { useGenerations, useDeleteGeneration } from "@/hooks/useGenerations";
import {
  Image as ImageIcon,
  Video,
  Trash2,
  Download,
  Loader2,
  RefreshCw,
  Clock3,
  SlidersHorizontal,
  ArrowDownToLine,
} from "lucide-react";
import { formatDate, truncateText } from "@/lib/utils";
import { inferRenderableAssetKind } from "@/lib/media";

export default function HistoryPage() {
  useAuth();

  const [filter, setFilter] = useState("all");
  const { data, isLoading, refetch } = useGenerations({
    generation_type: filter === "all" ? undefined : filter,
    page_size: 50,
  });

  const deleteGeneration = useDeleteGeneration();

  const handleDelete = async (id: number) => {
    if (confirm("Are you sure you want to delete this generation?")) {
      await deleteGeneration.mutateAsync(id);
    }
  };

  const items = data?.items || [];

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        {/* Background */}
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(239,68,68,0.10),transparent_30%),linear-gradient(180deg,#040404_0%,#090909_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.16]"
            style={{
              backgroundImage:
                "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="absolute left-[8%] top-[18%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl animate-pulse" />
          <div className="absolute right-[12%] top-[22%] h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl animate-pulse" />
          <div className="absolute bottom-[8%] left-[42%] h-64 w-64 rounded-full bg-red-500/10 blur-3xl animate-pulse" />
        </div>

        <div className="relative z-10 p-6 md:p-8 xl:p-10">
          {/* Header */}
          <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <span className="h-2 w-2 rounded-full bg-fuchsia-300" />
                History
              </div>

              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Project <span className="text-fuchsia-400">History</span>
              </h1>

              <p className="human-note mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Browse your latest outputs, filter them by type, preview results,
                and manage your files from one timeline.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="min-w-[170px]">
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-white/5 text-white backdrop-blur">
                    <div className="flex items-center gap-2 text-white/80">
                      <SlidersHorizontal className="h-4 w-4 text-fuchsia-300" />
                      <SelectValue />
                    </div>
                  </SelectTrigger>
                  <SelectContent className="border-white/10 bg-[#090909] text-white">
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="image">Images</SelectItem>
                    <SelectItem value="video">Legacy archive</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                variant="outline"
                onClick={() => refetch()}
                className="h-12 rounded-2xl border-white/10 bg-white/5 px-5 text-white/80 backdrop-blur transition hover:border-white/20 hover:bg-white/10 hover:text-white"
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
          </div>

          {/* Content */}
          {isLoading ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <div className="text-center">
                <div className="relative mx-auto mb-5 flex h-16 w-16 items-center justify-center">
                  <div className="absolute inset-0 rounded-full bg-fuchsia-500/20 blur-2xl" />
                  <Loader2 className="relative h-8 w-8 animate-spin text-fuchsia-300" />
                </div>
                <p className="text-sm uppercase tracking-[0.28em] text-white/45">
                  Loading history
                </p>
              </div>
            </div>
          ) : items.length > 0 ? (
            <div className="grid gap-5">
              {items.map((gen: any, index: number) => {
                const isVideoGeneration = gen.generation_type === "video" || gen.generation_type === "img2vid";
                const isImageGeneration = !isVideoGeneration;

                return (
                <Card
                  key={gen.id}
                  className="overflow-hidden rounded-[26px] border border-white/10 bg-white/[0.04] text-white backdrop-blur-xl transition duration-300 hover:border-white/20 hover:bg-white/[0.055]"
                >
                  <CardContent className="p-5 md:p-6">
                    <div className="flex flex-col gap-5">
                      {/* Top row */}
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div className="flex items-start gap-4">
                          {/* Icon */}
                          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                            {isImageGeneration ? (
                              <ImageIcon className="h-6 w-6 text-cyan-300" />
                            ) : (
                              <Video className="h-6 w-6 text-violet-300" />
                            )}
                          </div>

                          {/* Content */}
                          <div className="min-w-0">
                            <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-white/35">
                              <span>#{index + 1}</span>
                              <span>•</span>
                              <span>{gen.generation_type}</span>
                            </div>

                            <p className="max-w-3xl text-base font-semibold text-white/95 md:text-lg">
                              {truncateText(gen.prompt, 100)}
                            </p>

                            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-white/50">
                              <StatusBadge status={gen.status} />
                              <span className="text-white/20">•</span>
                              <span>
                                {gen.width}x{gen.height}
                              </span>

                              {gen.duration && (
                                <>
                                  <span className="text-white/20">•</span>
                                  <span>{gen.duration}s</span>
                                </>
                              )}

                              <span className="text-white/20">•</span>
                              <span>{gen.credits_used} credits</span>

                              <span className="text-white/20">•</span>
                              <span className="inline-flex items-center gap-1">
                                <Clock3 className="h-3.5 w-3.5" />
                                {formatDate(gen.created_at)}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2 self-end lg:self-start">
                          {gen.result_url && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                const a = document.createElement("a");
                                a.href = gen.result_url;
                                a.download = `generation-${gen.id}`;
                                a.click();
                              }}
                              className="h-10 rounded-xl border-white/10 bg-white/5 text-white/80 hover:border-white/20 hover:bg-white/10 hover:text-white"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          )}

                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDelete(gen.id)}
                            disabled={deleteGeneration.isPending}
                            className="h-10 rounded-xl border-red-500/20 bg-red-500/5 text-red-300 hover:border-red-500/30 hover:bg-red-500/10 hover:text-red-200"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      {/* Preview */}
                      {gen.result_url && isImageGeneration && (
                        <div className="overflow-hidden rounded-[22px] border border-white/10 bg-black/20">
                          <div className="relative h-[240px] w-full sm:h-[320px] lg:h-[360px]">
                            <Image
                              src={gen.result_url}
                              alt={gen.prompt}
                              fill
                              unoptimized
                              className="object-cover transition duration-500 hover:scale-[1.02]"
                            />
                          </div>
                        </div>
                      )}

                      {gen.result_url && isVideoGeneration && (
                        <div className="overflow-hidden rounded-[22px] border border-white/10 bg-black/20 p-4">
                          {inferRenderableAssetKind(gen.result_url, gen.generation_type) === "video" ? (
                            <video
                              src={gen.result_url}
                              controls
                              className="max-h-[360px] w-full rounded-2xl bg-black object-contain"
                              preload="metadata"
                            />
                          ) : (
                            <img
                              src={gen.result_url}
                              alt={gen.prompt}
                              className="max-h-[360px] w-full rounded-2xl bg-black object-contain"
                            />
                          )}
                          <div className="mt-3 flex items-center gap-3 text-white/70">
                            <ArrowDownToLine className="h-5 w-5 text-violet-300" />
                            <a
                              href={gen.result_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-sm underline underline-offset-4 hover:text-white"
                            >
                              Open archived media
                            </a>
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
                );
              })}
            </div>
          ) : (
            <Card className="rounded-[28px] border border-white/10 bg-white/[0.04] text-white backdrop-blur-xl">
              <CardContent className="flex min-h-[380px] flex-col items-center justify-center p-12 text-center">
                <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-full border border-white/10 bg-white/5">
                  <Clock3 className="h-9 w-9 text-fuchsia-300" />
                </div>

                <h2 className="text-2xl font-bold">No generations yet</h2>
                <p className="mt-3 max-w-md text-sm leading-6 text-white/50">
                  Your history is empty for now. Start generating images
                  and videos to build your archive.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </DashboardLayout>
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