"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { AdminShell } from "@/components/admin/admin-shell";
import { adminApi, AdminGeneration } from "@/lib/admin-api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { inferRenderableAssetKind } from "@/lib/media";
import {
  Loader2,
  Search,
  Trash2,
  ExternalLink,
  Image as ImageIcon,
  Video as VideoIcon,
  RefreshCw,
} from "lucide-react";

export default function AdminGenerationsPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  const [q, setQ] = useState("");
  const [type, setType] = useState<"all" | "image" | "video">("all");
  const [status, setStatus] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = 12;

  const [items, setItems] = useState<AdminGeneration[]>([]);
  const [total, setTotal] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // guard
  useEffect(() => {
    if (user && !user.is_admin) router.replace("/dashboard");
  }, [user, router]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.listGenerations({
        q: q || undefined,
        type: type === "all" ? undefined : type,
        status: status === "all" ? undefined : status,
        page,
        page_size: pageSize,
      });
      setItems(res.items ?? []);
      setTotal(res.total);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Unable to load generations. Check the backend logs and your admin session.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.is_admin) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.is_admin, page]);

  // debounce filters
  useEffect(() => {
    const t = setTimeout(() => {
      if (!user?.is_admin) return;
      setPage(1);
      load();
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, type, status]);

  const pages = useMemo(() => {
    if (!total) return undefined;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total]);

  const deleteGen = async (id: number) => {
    const ok = confirm("Delete this generation? (moderation action)");
    if (!ok) return;

    setMutatingId(id);
    try {
      await adminApi.deleteGeneration(id);
      setItems((prev) => prev.filter((g) => g.id !== id));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to delete generation");
    } finally {
      setMutatingId(null);
    }
  };

  return (
    <DashboardLayout>
      <AdminShell
        title="Generations moderation"
        subtitle="Browse all user generations. Preview outputs and delete content when needed."
        right={
          <Button
            variant="secondary"
            className="rounded-full bg-white/10 text-white hover:bg-white/15"
            onClick={load}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        }
      >
        {!user?.is_admin ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-white/80">
            Checking permissions…
          </div>
        ) : (
          <div className="space-y-4">
            {/* Filters */}
            <div className="rounded-3xl border border-white/10 bg-white/5 p-4 backdrop-blur">
              <div className="flex flex-col lg:flex-row lg:items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/50" />
                  <Input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search prompt or user email…"
                    className="pl-9 bg-black/30 border-white/10 text-white placeholder:text-white/40 rounded-2xl"
                  />
                </div>

                <select
                  value={type}
                  onChange={(e) => setType(e.target.value as any)}
                  className="h-10 rounded-2xl border border-white/10 bg-black/30 px-3 text-sm text-white/80"
                >
                  <option value="all">All types</option>
                  <option value="image">Images</option>
                  <option value="video">Legacy archive</option>
                </select>

                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="h-10 rounded-2xl border border-white/10 bg-black/30 px-3 text-sm text-white/80"
                >
                  <option value="all">All status</option>
                  <option value="completed">completed</option>
                  <option value="processing">processing</option>
                  <option value="pending">pending</option>
                  <option value="failed">failed</option>
                </select>

                <div className="text-xs text-white/60">
                  {typeof total === "number" ? (
                    <span>
                      {total} items • page {page}{pages ? ` / ${pages}` : ""}
                    </span>
                  ) : (
                    <span>—</span>
                  )}
                </div>
              </div>

              {error ? (
                <div className="mt-3 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                  {error}
                </div>
              ) : null}
            </div>

            {/* Grid */}
            {loading ? (
              <div className="rounded-3xl border border-white/10 bg-white/5 p-10 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-white/70" />
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-white/70">
                No generations found.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {items.map((g) => (
                  <GenCard
                    key={g.id}
                    gen={g}
                    busy={mutatingId === g.id}
                    onDelete={() => deleteGen(g.id)}
                  />
                ))}
              </div>
            )}

            {/* Pager */}
            {pages && pages > 1 ? (
              <div className="flex items-center justify-center gap-2 pt-2">
                <Button
                  variant="secondary"
                  className="rounded-full bg-white/10 text-white hover:bg-white/15"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Prev
                </Button>
                <div className="text-xs text-white/60 px-3">
                  Page {page} / {pages}
                </div>
                <Button
                  variant="secondary"
                  className="rounded-full bg-white/10 text-white hover:bg-white/15"
                  disabled={page >= pages}
                  onClick={() => setPage((p) => Math.min(pages, p + 1))}
                >
                  Next
                </Button>
              </div>
            ) : null}
          </div>
        )}
      </AdminShell>
    </DashboardLayout>
  );
}

function GenCard({
  gen,
  busy,
  onDelete,
}: {
  gen: AdminGeneration;
  busy: boolean;
  onDelete: () => void;
}) {
  const isVideoGeneration = gen.generation_type === "video" || gen.generation_type === "img2vid";
  const isImage = !isVideoGeneration;
  const renderKind = inferRenderableAssetKind(gen.result_url, gen.generation_type);

  return (
    <div className={cn("group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur transition-all hover:-translate-y-0.5 hover:bg-white/10 hover:border-white/15", busy && "opacity-70")}>
      <div className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-fuchsia-500/10 blur-2xl opacity-60 group-hover:opacity-100 transition-opacity" />

      {/* preview */}
      <div className="relative aspect-[4/3] w-full bg-black/30 border-b border-white/10 overflow-hidden">
        {gen.result_url ? (
          isImage || renderKind === "image" ? (
            // Use <img> to avoid next/image domain issues.
            <img
              src={gen.result_url}
              alt={gen.prompt}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <video
              src={gen.result_url}
              className="h-full w-full object-cover"
              controls
            />
          )
        ) : (
          <div className="h-full w-full flex items-center justify-center text-white/50">
            {isImage ? <ImageIcon className="h-8 w-8" /> : <VideoIcon className="h-8 w-8" />}
          </div>
        )}

        <div className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full border border-white/10 bg-black/40 px-2 py-1 text-[11px] text-white/80 backdrop-blur">
          {isImage ? <ImageIcon className="h-3.5 w-3.5" /> : <VideoIcon className="h-3.5 w-3.5" />}
          {gen.generation_type}
        </div>

        <div className="absolute right-3 top-3 inline-flex items-center rounded-full border border-white/10 bg-black/40 px-2 py-1 text-[11px] text-white/80 backdrop-blur">
          {gen.status}
        </div>
      </div>

      {/* content */}
      <div className="relative p-4">
        <div className="text-sm font-medium text-white line-clamp-2">
          {gen.prompt}
        </div>

        <div className="mt-2 flex flex-wrap gap-2 text-xs text-white/55">
          {gen.user_email ? <span className="rounded-full border border-white/10 bg-black/30 px-2 py-1">{gen.user_email}</span> : null}
          {typeof gen.credits_used === "number" ? <span className="rounded-full border border-white/10 bg-black/30 px-2 py-1">{gen.credits_used} credits</span> : null}
          {gen.created_at ? <span className="rounded-full border border-white/10 bg-black/30 px-2 py-1">{new Date(gen.created_at).toLocaleString()}</span> : null}
        </div>

        <div className="mt-4 flex items-center gap-2">
          {gen.result_url ? (
            <Button
              variant="secondary"
              className="rounded-full bg-white/10 text-white hover:bg-white/15"
              onClick={() => window.open(gen.result_url!, "_blank")}
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              Open
            </Button>
          ) : null}

          <Button
            variant="destructive"
            className="rounded-full ml-auto"
            onClick={onDelete}
            disabled={busy}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {busy ? (
        <div className="absolute right-4 bottom-4">
          <Loader2 className="h-4 w-4 animate-spin text-white/70" />
        </div>
      ) : null}
    </div>
  );
}
