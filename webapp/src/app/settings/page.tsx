
"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { authApi, runtimeApi, userApi } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import { formatCredits, formatDate } from "@/lib/utils";
import { Loader2, Check, Settings, User, Lock, ShieldCheck, CreditCard, Mail, CalendarDays, BadgeCheck, AlertCircle, Server, RefreshCw, Wifi, WifiOff, Cpu, Workflow, Bot, Volume2 } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const { refreshUser, logout } = useAuthStore();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<any | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);

  const loadRuntimeStatus = async () => {
    setRuntimeLoading(true);
    try {
      const response = await runtimeApi.getStatus();
      setRuntimeStatus(response.data);
    } catch (error: any) {
      setRuntimeStatus({
        production_ready: false,
        provider: "unknown",
        comfyui: { connected: false, error: error?.response?.data?.detail || "Runtime status unavailable." },
        workflows: {},
        warnings: ["Could not load backend runtime status."],
      });
    } finally {
      setRuntimeLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setEmail(user.email || "");
    }
  }, [user]);

  useEffect(() => {
    loadRuntimeStatus();
  }, []);

  const handleUpdateProfile = async (e: FormEvent) => {
    e.preventDefault();
    setIsUpdatingProfile(true);
    setMessage(null);

    try {
      const payload: { full_name?: string; email?: string } = {};
      if (fullName.trim()) payload.full_name = fullName.trim();
      if (email.trim()) payload.email = email.trim().toLowerCase();
      await userApi.updateMe(payload);
      await refreshUser();
      setMessage({ type: "success", text: "Profile updated successfully." });
    } catch (error: any) {
      setMessage({ type: "error", text: error?.response?.data?.detail || "Failed to update profile." });
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();
    setIsUpdatingPassword(true);
    setMessage(null);

    if (newPassword !== confirmPassword) {
      setMessage({ type: "error", text: "New password and confirmation do not match." });
      setIsUpdatingPassword(false);
      return;
    }

    try {
      await authApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      logout();
      router.push("/login?password=changed");
    } catch (error: any) {
      setMessage({ type: "error", text: error?.response?.data?.detail || "Failed to change password." });
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="human-made-screen relative min-h-[calc(100vh-120px)] overflow-hidden rounded-[28px] border border-white/10 bg-black text-white shadow-[0_0_80px_rgba(217,70,239,0.08)]">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(217,70,239,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(34,211,238,0.10),transparent_24%),radial-gradient(circle_at_bottom_center,rgba(239,68,68,0.10),transparent_30%),linear-gradient(180deg,#040404_0%,#090909_100%)]" />
          <div className="absolute inset-0 opacity-[0.16]" style={{ backgroundImage: "radial-gradient(rgba(255,255,255,0.55) 0.6px, transparent 0.6px)", backgroundSize: "26px 26px" }} />
          <div className="absolute left-[8%] top-[18%] h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl animate-pulse" />
          <div className="absolute right-[12%] top-[22%] h-56 w-56 rounded-full bg-cyan-400/10 blur-3xl animate-pulse" />
        </div>

        <div className="relative z-10 mx-auto max-w-6xl p-6 md:p-8 xl:p-10">
          <div className="mb-8 grid gap-5 xl:grid-cols-[1fr_360px] xl:items-end">
            <div>
              <div className="mb-3 human-pill inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.08em] text-white/60 backdrop-blur"><span className="h-2 w-2 rounded-full bg-fuchsia-300" />Settings</div>
              <h1 className="text-4xl font-black tracking-tight md:text-5xl">Account <span className="text-fuchsia-400">Settings</span></h1>
              <p className="human-note mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">Manage identity, billing state, security and account preferences like a production SaaS profile page.</p>
            </div>
            <div className="rounded-[26px] border border-white/10 bg-white/[0.055] p-4 backdrop-blur-xl">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-fuchsia-400/20 bg-fuchsia-400/10 text-xl font-black text-white">{(user?.full_name || user?.email || "U").slice(0,1).toUpperCase()}</div>
                <div className="min-w-0"><p className="truncate text-base font-bold text-white">{user?.full_name || "Add your name"}</p><p className="truncate text-sm text-white/55">{user?.email}</p><p className="mt-1 text-xs text-white/40">Role: {user?.role || (user?.is_admin ? "ADMIN" : "USER")}</p></div>
              </div>
            </div>
          </div>

          {message && (
            <div className={`mb-6 flex items-center gap-3 rounded-2xl border px-4 py-3 backdrop-blur-xl ${message.type === "success" ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300" : "border-red-400/20 bg-red-400/10 text-red-300"}`}>
              {message.type === "success" ? <Check className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}<span className="text-sm font-medium">{message.text}</span>
            </div>
          )}

          <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <InfoCard icon={User} label="Full name" value={user?.full_name || "Not set"} />
            <InfoCard icon={Mail} label="Email" value={user?.email || "—"} />
            <InfoCard icon={CreditCard} label="Credits" value={formatCredits(user?.credits || 0)} />
            <InfoCard icon={CalendarDays} label="Member since" value={user?.created_at ? formatDate(user.created_at) : "—"} />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card className="rounded-[28px] border border-white/10 bg-white/[0.04] text-white backdrop-blur-xl">
              <CardHeader className="pb-2"><div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5"><User className="h-5 w-5 text-cyan-300" /></div><CardTitle className="text-2xl font-bold text-white">Profile information</CardTitle><CardDescription className="text-white/50">Keep your public account data clean and up to date.</CardDescription></CardHeader>
              <CardContent><form onSubmit={handleUpdateProfile} className="space-y-5"><div className="grid gap-5 md:grid-cols-2"><div className="space-y-2"><Label htmlFor="fullName" className="text-sm font-medium text-white/80">Full name</Label><Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your full name" className="h-12 rounded-2xl border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-1 focus-visible:ring-fuchsia-400" /></div><div className="space-y-2"><Label htmlFor="email" className="text-sm font-medium text-white/80">Email</Label><Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="your@email.com" className="h-12 rounded-2xl border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-1 focus-visible:ring-fuchsia-400" /></div></div><Button type="submit" disabled={isUpdatingProfile} className="h-12 rounded-2xl bg-gradient-to-r from-fuchsia-500 via-pink-500 to-violet-500 px-6 text-white shadow-[0_0_35px_rgba(217,70,239,0.25)] hover:opacity-95">{isUpdatingProfile ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Updating...</> : <><Settings className="mr-2 h-4 w-4" />Save profile</>}</Button></form></CardContent>
            </Card>

            <Card className="rounded-[28px] border border-white/10 bg-white/[0.04] text-white backdrop-blur-xl">
              <CardHeader className="pb-2"><div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5"><Lock className="h-5 w-5 text-violet-300" /></div><CardTitle className="text-2xl font-bold text-white">Security</CardTitle><CardDescription className="text-white/50">Change password and keep your account protected.</CardDescription></CardHeader>
              <CardContent><form onSubmit={handleChangePassword} className="space-y-5"><div className="space-y-4"><div className="space-y-2"><Label className="text-sm font-medium text-white/80">Current password</Label><Input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className="h-12 rounded-2xl border-white/10 bg-white/5 text-white" /></div><div className="grid gap-4 md:grid-cols-2"><div className="space-y-2"><Label className="text-sm font-medium text-white/80">New password</Label><Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="h-12 rounded-2xl border-white/10 bg-white/5 text-white" /></div><div className="space-y-2"><Label className="text-sm font-medium text-white/80">Confirm new password</Label><Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="h-12 rounded-2xl border-white/10 bg-white/5 text-white" /></div></div></div><Button type="submit" disabled={isUpdatingPassword || !currentPassword || !newPassword || !confirmPassword} className="h-12 rounded-2xl bg-white/10 px-6 text-white hover:bg-white/15">{isUpdatingPassword ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Saving...</> : <><ShieldCheck className="mr-2 h-4 w-4" />Update password</>}</Button></form></CardContent>
            </Card>
          </div>

          <Card className="mt-6 rounded-[28px] border border-white/10 bg-white/[0.04] text-white backdrop-blur-xl">
            <CardHeader className="pb-2">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5"><Server className="h-5 w-5 text-cyan-300" /></div>
                  <CardTitle className="text-2xl font-bold text-white">ComfyUI runtime</CardTitle>
                  <CardDescription className="mt-1 text-white/50">Live, non-secret verification of the backend provider, image checkpoint and required workflows.</CardDescription>
                </div>
                <Button type="button" variant="outline" onClick={loadRuntimeStatus} disabled={runtimeLoading} className="rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10">
                  {runtimeLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                  Refresh runtime
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className={`mb-4 flex items-start gap-3 rounded-2xl border p-4 ${runtimeStatus?.production_ready ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-amber-400/25 bg-amber-400/10 text-amber-100"}`}>
                {runtimeStatus?.comfyui?.connected ? <Wifi className="mt-0.5 h-5 w-5 shrink-0" /> : <WifiOff className="mt-0.5 h-5 w-5 shrink-0" />}
                <div>
                  <p className="font-semibold">{runtimeLoading ? "Checking ComfyUI..." : runtimeStatus?.production_ready ? "ComfyUI image runtime is ready" : "ComfyUI runtime needs attention"}</p>
                  <p className="mt-1 text-sm opacity-80">{runtimeStatus?.comfyui?.error || (runtimeStatus?.comfyui?.connected ? "Backend can reach ComfyUI and the image workflow assets are present." : "Press Refresh runtime after starting ComfyUI.")}</p>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <RuntimeItem icon={Server} label="Provider" value={runtimeStatus?.provider || "—"} />
                <RuntimeItem icon={Wifi} label="ComfyUI URL" value={runtimeStatus?.comfyui?.url || "—"} />
                <RuntimeItem icon={Cpu} label="Checkpoint" value={runtimeStatus?.comfyui?.image_checkpoint || "—"} />
                <RuntimeItem icon={Workflow} label="Build mode" value={runtimeStatus?.build_mode || "image_first"} />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <RuntimeItem icon={Settings} label="Strict workflow" value={runtimeStatus?.comfyui?.strict_workflow_mode ? "Enabled" : "Disabled"} />
                <RuntimeItem icon={Settings} label="Sampler" value={runtimeStatus?.comfyui?.sampler || "—"} />
                <RuntimeItem icon={Settings} label="Steps / CFG" value={runtimeStatus?.comfyui ? `${runtimeStatus.comfyui.steps} / ${runtimeStatus.comfyui.cfg}` : "—"} />
                <RuntimeItem icon={ShieldCheck} label="Checkpoint available" value={runtimeStatus?.comfyui?.checkpoint_available === false ? "Missing" : runtimeStatus?.comfyui?.checkpoint_available === true ? "Available" : "Unknown"} />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <RuntimeItem icon={Workflow} label="Text-to-image workflow" value={runtimeStatus?.workflows?.text_to_image?.present ? "Present" : "Missing"} />
                <RuntimeItem icon={Workflow} label="Image-to-image workflow" value={runtimeStatus?.workflows?.image_to_image?.present ? "Present" : "Missing"} />
                <RuntimeItem icon={Server} label="Queue mode" value={runtimeStatus?.queue?.task_always_eager ? "Direct / eager" : "Redis + Celery worker"} />
                <RuntimeItem icon={ShieldCheck} label="Runtime readiness" value={runtimeStatus?.production_ready ? "Ready" : "Needs attention"} />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <RuntimeItem icon={Bot} label="Assistant output languages" value={Array.isArray(runtimeStatus?.assistant?.output_languages) ? runtimeStatus.assistant.output_languages.join(" / ").toUpperCase() : "EN / FR"} />
                <RuntimeItem icon={Bot} label="Tunisian / Arabizi input" value={runtimeStatus?.assistant?.tunisian_arabizi_supported ? "Accepted" : "Check config"} />
                <RuntimeItem icon={Bot} label="Ollama chat" value={runtimeStatus?.assistant?.chat?.enabled ? (runtimeStatus?.assistant?.chat?.ready ? "Ready · dual local models" : "Enabled · needs attention") : "Fallback only"} />
                <RuntimeItem icon={Volume2} label="Voice mode" value={runtimeStatus?.assistant?.speech?.server_tts_enabled ? (runtimeStatus?.assistant?.speech?.piper_configured ? "Piper server TTS · EN / FR only" : "Piper needs config · EN / FR only") : "Browser TTS fallback · EN / FR only"} />
                <RuntimeItem icon={Bot} label="Fast / advanced" value={runtimeStatus?.assistant?.chat ? `${runtimeStatus.assistant.chat.fast_model || "—"} / ${runtimeStatus.assistant.chat.advanced_model || "—"}` : "—"} />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <RuntimeItem icon={Bot} label="Fast model installed" value={runtimeStatus?.assistant?.chat?.fast_model_ready ? "Ready" : "Missing"} />
                <RuntimeItem icon={Bot} label="Advanced model installed" value={runtimeStatus?.assistant?.chat?.advanced_model_ready ? "Ready" : "Missing"} />
                <RuntimeItem icon={Bot} label="Ollama server" value={runtimeStatus?.assistant?.chat?.connected ? "Connected" : "Unavailable"} />
                <RuntimeItem icon={Volume2} label="Arabic voice" value={runtimeStatus?.assistant?.speech?.arabic_voice_enabled ? "Enabled" : "Disabled"} />
              </div>

              {Array.isArray(runtimeStatus?.warnings) && runtimeStatus.warnings.length > 0 && (
                <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/5 p-4">
                  <p className="text-sm font-semibold text-amber-100">Runtime checklist</p>
                  <div className="mt-2 space-y-1 text-sm text-amber-100/75">{runtimeStatus.warnings.map((item: string) => <p key={item}>• {item}</p>)}</div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Panel icon={BadgeCheck} title="Subscription" text={`Current plan: ${user?.subscription_tier || "free"}. Status: ${user?.subscription_status || "inactive"}.`} />
            <Panel icon={CreditCard} title="Billing" text="Credit packs are paid securely through the billing page. Production mode redirects to Stripe Checkout." />
            <Panel icon={ShieldCheck} title="Account status" text={user?.is_active ? "Your account is active and ready for production workflows." : "Your account is not active."} />
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function InfoCard({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-4 backdrop-blur-xl"><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-white/10 bg-white/5"><Icon className="h-4 w-4 text-cyan-200" /></div><div className="min-w-0"><p className="text-xs uppercase tracking-[0.18em] text-white/35">{label}</p><p className="truncate text-sm font-bold text-white">{value}</p></div></div></div>;
}

function Panel({ icon: Icon, title, text }: { icon: any; title: string; text: string }) {
  return <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-5 backdrop-blur-xl"><div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5"><Icon className="h-5 w-5 text-fuchsia-200" /></div><h3 className="text-lg font-bold text-white">{title}</h3><p className="mt-2 text-sm leading-6 text-white/55">{text}</p></div>;
}

function RuntimeItem({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return <div className="rounded-2xl border border-white/10 bg-black/25 p-3"><div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-white/40"><Icon className="h-3.5 w-3.5" />{label}</div><p className="break-words text-sm font-semibold text-white/85">{value}</p></div>;
}
