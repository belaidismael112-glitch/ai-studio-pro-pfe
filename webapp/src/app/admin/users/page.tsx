"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { AdminShell } from "@/components/admin/admin-shell";
import { adminApi, AdminUser } from "@/lib/admin-api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  Loader2,
  Search,
  ShieldCheck,
  ShieldOff,
  UserX,
  Coins,
  RefreshCw,
  CheckCircle2,
  XCircle,
} from "lucide-react";

export default function AdminUsersPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState<number | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // guard
  useEffect(() => {
    if (user && !user.is_admin) router.replace("/dashboard");
  }, [user, router]);

  const load = async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const res = await adminApi.listUsers({ q: q || undefined, page, page_size: pageSize });
      setItems(res.items ?? []);
      setTotal(res.total);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Unable to load users. Check the backend logs and your admin session.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.is_admin) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.is_admin, page]);

  // debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      if (user?.is_admin) {
        setPage(1);
        load();
      }
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const pages = useMemo(() => {
    if (!total) return undefined;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total]);

  const patchUser = async (id: number, body: { is_admin?: boolean; is_active?: boolean; credits?: number }) => {
    setMutatingId(id);
    setNotice(null);
    try {
      const updated = await adminApi.patchUser(id, body);
      setItems((prev) => prev.map((u) => (u.id === id ? { ...u, ...updated } : u)));
      setNotice("Saved ✅");
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to update user");
    } finally {
      setMutatingId(null);
    }
  };

  const deleteUser = async (id: number) => {
    const ok = confirm("Delete this user? This action cannot be undone.");
    if (!ok) return;

    setMutatingId(id);
    setNotice(null);
    try {
      await adminApi.deleteUser(id);
      setItems((prev) => prev.filter((u) => u.id !== id));
      setNotice("User deleted ✅");
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to delete user");
    } finally {
      setMutatingId(null);
    }
  };

  const editCredits = async (u: AdminUser) => {
    const current = u.credits ?? 0;
    const raw = prompt(`Set credits for ${u.email}`, String(current));
    if (raw === null) return;
    const next = Number(raw);
    if (!Number.isFinite(next) || next < 0) {
      alert("Invalid credits value");
      return;
    }
    await patchUser(u.id, { credits: next });
  };

  return (
    <DashboardLayout>
      <AdminShell
        title="Users management"
        subtitle="Search, promote admins, change credits, disable accounts, and delete users."
        right={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              className="rounded-full bg-white/10 text-white hover:bg-white/15"
              onClick={load}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        }
      >
        {!user?.is_admin ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-white/80">
            Checking permissions…
          </div>
        ) : (
          <div className="space-y-4">
            {/* Top controls */}
            <div className="rounded-3xl border border-white/10 bg-white/5 p-4 backdrop-blur">
              <div className="flex flex-col md:flex-row md:items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/50" />
                  <Input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Search by email, name…"
                    className="pl-9 bg-black/30 border-white/10 text-white placeholder:text-white/40 rounded-2xl"
                  />
                </div>

                <div className="text-xs text-white/60">
                  {typeof total === "number" ? (
                    <span>
                      {total} users • page {page}{pages ? ` / ${pages}` : ""}
                    </span>
                  ) : (
                    <span>—</span>
                  )}
                </div>
              </div>

              {(error || notice) && (
                <div className="mt-3 flex flex-col gap-2">
                  {error ? (
                    <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                      {error}
                    </div>
                  ) : null}
                  {notice ? (
                    <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-50 flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4" />
                      {notice}
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {/* List */}
            {loading ? (
              <div className="rounded-3xl border border-white/10 bg-white/5 p-10 flex items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-white/70" />
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-white/70">
                No users found.
              </div>
            ) : (
              <div className="grid gap-3">
                {items.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    busy={mutatingId === u.id}
                    onToggleAdmin={() => patchUser(u.id, { is_admin: !u.is_admin })}
                    onToggleActive={() => patchUser(u.id, { is_active: !(u.is_active ?? true) })}
                    onEditCredits={() => editCredits(u)}
                    onDelete={() => deleteUser(u.id)}
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

function UserRow({
  user,
  busy,
  onToggleAdmin,
  onToggleActive,
  onEditCredits,
  onDelete,
}: {
  user: AdminUser;
  busy: boolean;
  onToggleAdmin: () => void;
  onToggleActive: () => void;
  onEditCredits: () => void;
  onDelete: () => void;
}) {
  const active = user.is_active ?? true;

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-4 md:p-5 backdrop-blur transition-all",
        "hover:bg-white/10 hover:border-white/15",
        busy && "opacity-70"
      )}
    >
      <div className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-cyan-500/10 blur-2xl opacity-60 group-hover:opacity-100 transition-opacity" />

      <div className="relative flex flex-col md:flex-row md:items-center gap-4">
        {/* left */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <div className="font-semibold text-white truncate">{user.email}</div>

            {user.is_admin ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-fuchsia-400/30 bg-fuchsia-500/10 px-2 py-0.5 text-[11px] text-fuchsia-100">
                <ShieldCheck className="h-3.5 w-3.5" />
                Admin
              </span>
            ) : null}

            {!active ? (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-100">
                <XCircle className="h-3.5 w-3.5" />
                Disabled
              </span>
            ) : null}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-white/60">
            <span className="inline-flex items-center gap-1">
              <Coins className="h-3.5 w-3.5" />
              credits: <span className="text-white/80 font-medium">{user.credits ?? 0}</span>
            </span>

            {user.full_name ? <span>• {user.full_name}</span> : null}
            {user.created_at ? <span>• created {new Date(user.created_at).toLocaleDateString()}</span> : null}
          </div>
        </div>

        {/* actions */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            className="rounded-full bg-white/10 text-white hover:bg-white/15"
            onClick={onEditCredits}
            disabled={busy}
          >
            <Coins className="h-4 w-4 mr-2" />
            Credits
          </Button>

          <Button
            variant="secondary"
            className={cn(
              "rounded-full bg-white/10 text-white hover:bg-white/15",
              user.is_admin && "border border-fuchsia-400/30"
            )}
            onClick={onToggleAdmin}
            disabled={busy}
          >
            {user.is_admin ? (
              <>
                <ShieldOff className="h-4 w-4 mr-2" />
                Remove admin
              </>
            ) : (
              <>
                <ShieldCheck className="h-4 w-4 mr-2" />
                Make admin
              </>
            )}
          </Button>

          <Button
            variant="secondary"
            className={cn("rounded-full bg-white/10 text-white hover:bg-white/15", !active && "border border-amber-400/30")}
            onClick={onToggleActive}
            disabled={busy}
          >
            {!active ? (
              <>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Enable
              </>
            ) : (
              <>
                <UserX className="h-4 w-4 mr-2" />
                Disable
              </>
            )}
          </Button>

          <Button
            variant="destructive"
            className="rounded-full"
            onClick={onDelete}
            disabled={busy}
          >
            <UserX className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {busy ? (
        <div className="absolute right-4 top-4">
          <Loader2 className="h-4 w-4 animate-spin text-white/70" />
        </div>
      ) : null}
    </div>
  );
}
