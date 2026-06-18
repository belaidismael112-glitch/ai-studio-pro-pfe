"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { AdminShell } from "@/components/admin/admin-shell";
import { adminApi, AdminTicket } from "@/lib/admin-api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  Loader2,
  Search,
  RefreshCw,
  CheckCircle2,
  Trash2,
  MessageSquareText,
} from "lucide-react";

export default function AdminComplaintsPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const [items, setItems] = useState<AdminTicket[]>([]);
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
      const res = await adminApi.listTickets({
        q: q || undefined,
        status: status === "all" ? undefined : status,
        page,
        page_size: pageSize,
      });
      setItems(res.items ?? []);
      setTotal(res.total);
    } catch (e: any) {
      setError(
        e?.response?.data?.detail ??
          "Failed to load admin reclamations."
      );
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
  }, [q, status]);

  const pages = useMemo(() => {
    if (!total) return undefined;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total]);

  const updateTicket = async (id: number, body: { status?: string; admin_notes?: string }) => {
    setMutatingId(id);
    try {
      const updated = await adminApi.patchTicket(id, body);
      setItems((prev) => prev.map((t) => (t.id === id ? { ...t, ...updated } : t)));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to update ticket");
    } finally {
      setMutatingId(null);
    }
  };

  const remove = async (id: number) => {
    const ok = confirm("Delete this ticket?");
    if (!ok) return;

    setMutatingId(id);
    try {
      await adminApi.deleteTicket(id);
      setItems((prev) => prev.filter((t) => t.id !== id));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to delete ticket");
    } finally {
      setMutatingId(null);
    }
  };

  return (
    <DashboardLayout>
      <AdminShell
        title="Reclamations"
        subtitle="Support tickets & user requests. Mark as resolved, keep your platform clean."
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
                    placeholder="Search subject, message, user email…"
                    className="pl-9 bg-black/30 border-white/10 text-white placeholder:text-white/40 rounded-2xl"
                  />
                </div>

                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="h-10 rounded-2xl border border-white/10 bg-black/30 px-3 text-sm text-white/80"
                >
                  <option value="all">All status</option>
                  <option value="open">open</option>
                  <option value="in_progress">in_progress</option>
                  <option value="resolved">resolved</option>
                  <option value="closed">closed</option>
                </select>

                <div className="text-xs text-white/60">
                  {typeof total === "number" ? (
                    <span>
                      {total} tickets • page {page}{pages ? ` / ${pages}` : ""}
                    </span>
                  ) : (
                    <span>—</span>
                  )}
                </div>
              </div>

              {error ? (
                <div className="mt-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-50">
                  {error}
                </div>
              ) : null}
            </div>

            {/* List */}
            {loading ? (
              <div className="rounded-3xl border border-white/10 bg-white/5 p-10 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-white/70" />
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-white/70">
                No tickets.
              </div>
            ) : (
              <div className="grid gap-3">
                {items.map((t) => (
                  <TicketRow
                    key={t.id}
                    ticket={t}
                    busy={mutatingId === t.id}
                    onUpdate={(body) => updateTicket(t.id, body)}
                    onDelete={() => remove(t.id)}
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

function statusColor(status: string) {
  const s = (status || "").toLowerCase();
  if (s === "resolved" || s === "closed") return "border-emerald-400/25 bg-emerald-500/10 text-emerald-50";
  if (s === "in_progress") return "border-cyan-400/25 bg-cyan-500/10 text-cyan-50";
  if (s === "open") return "border-amber-400/25 bg-amber-500/10 text-amber-50";
  return "border-white/10 bg-white/5 text-white/70";
}

function TicketRow({
  ticket,
  busy,
  onUpdate,
  onDelete,
}: {
  ticket: AdminTicket;
  busy: boolean;
  onUpdate: (body: { status?: string; admin_notes?: string }) => void;
  onDelete: () => void;
}) {
  const [adminNotes, setAdminNotes] = useState(ticket.admin_notes || "");
  const resolved = ["resolved", "closed"].includes((ticket.status || "").toLowerCase());

  return (
    <div className={cn("group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-4 md:p-5 backdrop-blur transition-all hover:bg-white/10 hover:border-white/15", busy && "opacity-70")}>
      <div className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-amber-500/10 blur-2xl opacity-60 group-hover:opacity-100 transition-opacity" />

      <div className="relative flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <MessageSquareText className="h-4 w-4 text-white/70" />
              <div className="font-semibold text-white truncate">{ticket.subject}</div>
            </div>

            <div className="mt-1 text-xs text-white/55 flex flex-wrap gap-2">
              {ticket.user_email ? <span>{ticket.user_email}</span> : null}
              {ticket.user_name ? <span>• {ticket.user_name}</span> : null}
              {ticket.created_at ? <span>• {new Date(ticket.created_at).toLocaleString()}</span> : null}
            </div>
          </div>

          <span className={cn("shrink-0 inline-flex items-center rounded-full border px-2 py-1 text-[11px] backdrop-blur", statusColor(ticket.status))}>
            {ticket.status}
          </span>
        </div>

        <p className="text-sm text-white/70 whitespace-pre-wrap">
          {ticket.message}
        </p>

        <div className="rounded-2xl border border-white/10 bg-black/25 p-3">
          <label className="block text-[11px] uppercase tracking-[0.18em] text-white/40">Admin reply / notes</label>
          <textarea
            value={adminNotes}
            onChange={(e) => setAdminNotes(e.target.value)}
            rows={3}
            className="mt-2 w-full rounded-2xl border border-white/10 bg-black/35 px-3 py-2 text-sm leading-6 text-white outline-none focus:border-cyan-300/40"
            placeholder="Write a reply or internal note..."
            disabled={busy}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={ticket.status}
            onChange={(e) => onUpdate({ status: e.target.value })}
            disabled={busy}
            className="h-10 rounded-full border border-white/10 bg-black/40 px-3 text-sm text-white/80"
          >
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="resolved">resolved</option>
            <option value="closed">closed</option>
          </select>

          <Button
            variant="secondary"
            className="rounded-full bg-white/10 text-white hover:bg-white/15"
            onClick={() => onUpdate({ admin_notes: adminNotes, status: resolved ? ticket.status : "in_progress" })}
            disabled={busy}
          >
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Save reply
          </Button>

          <Button
            variant="secondary"
            className="rounded-full bg-emerald-500/15 text-emerald-50 hover:bg-emerald-500/20"
            onClick={() => onUpdate({ admin_notes: adminNotes, status: "resolved" })}
            disabled={busy || resolved}
          >
            <CheckCircle2 className="h-4 w-4 mr-2" />
            {resolved ? "Resolved" : "Resolve"}
          </Button>

          <Button
            variant="destructive"
            className="rounded-full ml-auto"
            onClick={onDelete}
            disabled={busy}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>

          {busy ? <Loader2 className="h-4 w-4 animate-spin text-white/70" /> : null}
        </div>
      </div>
    </div>
  );
}
