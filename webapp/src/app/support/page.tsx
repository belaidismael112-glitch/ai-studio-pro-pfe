"use client";

import { useEffect, useMemo, useState } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { supportApi } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import type { SupportTicket } from "@/types";
import { AlertTriangle, CheckCircle2, Loader2, Mail, MessageSquareText, Phone, RefreshCw, Send, UserRound } from "lucide-react";

const SUPPORT_ADMIN_NAME = process.env.NEXT_PUBLIC_SUPPORT_ADMIN_NAME || "Support Team";
const SUPPORT_ADMIN_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_ADMIN_EMAIL || "support@example.com";

function statusClass(status: string) {
  const s = (status || "").toLowerCase();
  if (s === "resolved" || s === "closed") return "border-emerald-400/25 bg-emerald-500/10 text-emerald-50";
  if (s === "in_progress") return "border-cyan-400/25 bg-cyan-500/10 text-cyan-50";
  return "border-amber-400/25 bg-amber-500/10 text-amber-50";
}

export default function SupportPage() {
  useAuth();

  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openCount = useMemo(
    () => tickets.filter((t) => ["open", "in_progress"].includes((t.status || "").toLowerCase())).length,
    [tickets]
  );

  async function loadTickets() {
    setLoading(true);
    setError(null);
    try {
      const res = await supportApi.getTickets({ page: 1, page_size: 50 });
      setTickets(res.data?.items || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load reclamations.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTickets();
  }, []);

  async function submitTicket(e: React.FormEvent) {
    e.preventDefault();
    const cleanSubject = subject.trim();
    const cleanMessage = message.trim();

    if (!cleanSubject || !cleanMessage) {
      setError("Subject and message are required.");
      return;
    }

    setSending(true);
    setFeedback(null);
    setError(null);
    try {
      const res = await supportApi.createTicket({ subject: cleanSubject, message: cleanMessage });
      setTickets((current) => [res.data, ...current]);
      setSubject("");
      setMessage("");
      setFeedback("Reclamation sent to admin successfully.");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Failed to send reclamation.");
    } finally {
      setSending(false);
    }
  }

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),linear-gradient(180deg,#040404_0%,#090909_100%)]" />
          <div
            className="absolute inset-0 opacity-[0.14]"
            style={{
              backgroundImage: "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)",
              backgroundSize: "26px 26px",
            }}
          />
          <div className="absolute left-[10%] top-[18%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute right-[12%] top-[22%] h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl" />
        </div>

        <div className="relative z-10 p-6 md:p-8 xl:p-10">
          <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="mb-3 human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur">
                <MessageSquareText className="h-4 w-4 text-cyan-300" />
                Reclamations
              </div>
              <h1 className="text-4xl font-black tracking-tight md:text-5xl">
                Support <span className="text-fuchsia-400">Center</span>
              </h1>
              <p className="human-note mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Send a reclamation to the admin team and track the status from your account.
              </p>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 px-5 py-4 backdrop-blur-xl">
              <div className="text-xs uppercase tracking-[0.22em] text-white/40">Open / in progress</div>
              <div className="mt-2 text-3xl font-black text-white">{openCount}</div>
            </div>
          </div>

          <div className="mb-6 grid gap-4 rounded-[26px] border border-cyan-300/15 bg-cyan-300/[0.06] p-5 backdrop-blur-xl md:grid-cols-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10">
                <UserRound className="h-5 w-5 text-cyan-200" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-white/40">Support admin</div>
                <div className="mt-1 font-semibold text-white">{SUPPORT_ADMIN_NAME}</div>
              </div>
            </div>
            <a href={`mailto:${SUPPORT_ADMIN_EMAIL}`} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/20 p-3 transition hover:bg-white/10">
              <Mail className="h-5 w-5 text-fuchsia-300" />
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-white/40">Email</div>
                <div className="mt-1 text-sm font-semibold text-white">{SUPPORT_ADMIN_EMAIL}</div>
              </div>
            </a>
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-black/20 p-3">
              <Phone className="h-5 w-5 text-emerald-300" />
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-white/40">Urgent phone</div>
                <div className="mt-1 text-sm font-semibold text-white/70">Not configured yet</div>
              </div>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <form onSubmit={submitTicket} className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-fuchsia-500/10">
                  <Send className="h-5 w-5 text-fuchsia-300" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Create reclamation</h2>
                  <p className="text-sm text-white/50">This ticket appears instantly in admin.</p>
                </div>
              </div>

              <div className="space-y-5">
                <div className="space-y-2">
                  <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Subject</Label>
                  <Input
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="Example: credits problem, image generation issue..."
                    className="h-12 rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30 focus-visible:ring-fuchsia-400/30"
                    disabled={sending}
                    maxLength={200}
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-[12px] uppercase tracking-[0.22em] text-white/65">Message</Label>
                  <Textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Explain the problem clearly..."
                    className="min-h-[170px] rounded-2xl border-white/10 bg-black/35 text-white placeholder:text-white/30 focus-visible:ring-fuchsia-400/30"
                    disabled={sending}
                    maxLength={8000}
                  />
                </div>

                {feedback ? (
                  <div className="flex gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-sm text-emerald-50">
                    <CheckCircle2 className="h-5 w-5 shrink-0" /> {feedback}
                  </div>
                ) : null}

                {error ? (
                  <div className="flex gap-3 rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-100">
                    <AlertTriangle className="h-5 w-5 shrink-0" /> {error}
                  </div>
                ) : null}

                <Button
                  type="submit"
                  disabled={sending || !subject.trim() || !message.trim()}
                  className="h-12 w-full rounded-2xl bg-fuchsia-600 text-white shadow-[0_0_36px_rgba(217,70,239,0.28)] transition hover:bg-fuchsia-500"
                >
                  {sending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Send to admin
                </Button>
              </div>
            </form>

            <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl md:p-6">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">My tickets</h2>
                  <p className="text-sm text-white/50">Follow admin status and notes.</p>
                </div>
                <Button variant="outline" onClick={loadTickets} className="rounded-2xl border-white/10 bg-white/5 text-white/80 hover:bg-white/10">
                  <RefreshCw className="mr-2 h-4 w-4" /> Refresh
                </Button>
              </div>

              {loading ? (
                <div className="flex min-h-[260px] items-center justify-center">
                  <Loader2 className="h-7 w-7 animate-spin text-fuchsia-300" />
                </div>
              ) : tickets.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-white/10 bg-black/25 p-10 text-center text-white/55">
                  No reclamations yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {tickets.map((ticket) => (
                    <div key={ticket.id} className="rounded-3xl border border-white/10 bg-black/30 p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="font-semibold text-white">{ticket.subject}</div>
                          <div className="mt-1 text-xs text-white/45">#{ticket.id} • {ticket.created_at ? formatDate(ticket.created_at) : "now"}</div>
                        </div>
                        <span className={cn("inline-flex w-fit rounded-full border px-3 py-1 text-xs font-semibold", statusClass(ticket.status))}>
                          {ticket.status}
                        </span>
                      </div>
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-white/65">{ticket.message}</p>
                      {ticket.admin_notes ? (
                        <div className="mt-4 rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-4 text-sm leading-6 text-cyan-50">
                          <div className="mb-1 text-xs uppercase tracking-[0.22em] text-cyan-100/55">Admin reply</div>
                          {ticket.admin_notes}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
