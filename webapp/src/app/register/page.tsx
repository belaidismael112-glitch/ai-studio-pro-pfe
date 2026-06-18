"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle, Eye, EyeOff, Loader2, LockKeyhole, Mail, ShieldCheck, UserRound } from "lucide-react";
import Lenis from "lenis";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardTitle } from "@/components/ui/card";
import { RegisterSequenceBackdrop } from "@/components/RegisterSequenceBackdrop";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { IntroGateOverlay } from "@/components/IntroGateOverlay";

import { useAuthStore } from "@/store/authStore";
import { useGuestOnly } from "@/hooks/useAuth";

function normalizeApiError(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((item) => normalizeApiError(item)).filter(Boolean).join("\n");
  if (typeof value === "object") {
    const obj = value as Record<string, any>;
    if (typeof obj.msg === "string") {
      const loc = Array.isArray(obj.loc) ? obj.loc.join(".") : "";
      return loc ? `${loc}: ${obj.msg}` : obj.msg;
    }
    if (typeof obj.detail === "string") return obj.detail;
    if (Array.isArray(obj.detail)) return normalizeApiError(obj.detail);
    if (typeof obj.message === "string") return obj.message;
    try {
      return JSON.stringify(obj);
    } catch {
      return "Something went wrong.";
    }
  }
  return String(value);
}

function getRegisterErrorMessage(error: any): string {
  const data = error?.response?.data;
  const message =
    normalizeApiError(data?.detail) ||
    normalizeApiError(data?.message) ||
    normalizeApiError(data) ||
    normalizeApiError(error?.message);
  return message || "Registration failed.";
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function passwordStrength(password: string) {
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (!password) return { pct: 0, label: "Password strength", className: "bg-white/15" };
  if (score <= 1) return { pct: 28, label: "Weak", className: "bg-red-400" };
  if (score === 2) return { pct: 55, label: "Medium", className: "bg-amber-400" };
  if (score === 3) return { pct: 78, label: "Strong", className: "bg-cyan-300" };
  return { pct: 100, label: "Very strong", className: "bg-emerald-300" };
}

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuthStore();
  const { isLoading: isChecking } = useGuestOnly();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const strength = passwordStrength(password);

  useEffect(() => {
    const lenis = new Lenis({ duration: 1.0, smoothWheel: true, wheelMultiplier: 0.9 });
    let raf = 0;
    const loop = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, []);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const cleanName = fullName.trim();
    const cleanEmail = email.trim();
    const cleanPassword = password.trim();
    const cleanConfirmPassword = confirmPassword.trim();

    setError("");

    if (!cleanEmail) return setError("Please enter your email.");
    if (!isValidEmail(cleanEmail)) return setError("Please enter a valid email address.");
    if (!cleanPassword) return setError("Please enter your password.");
    if (cleanPassword.length < 8) return setError("Password must be at least 8 characters.");
    if (!cleanConfirmPassword) return setError("Please confirm your password.");
    if (cleanPassword !== cleanConfirmPassword) return setError("Passwords do not match.");

    setIsLoading(true);

    try {
      await register({ email: cleanEmail, password: cleanPassword, full_name: cleanName });
      setSuccess(true);
      window.setTimeout(() => router.push("/dashboard"), 1200);
    } catch (err: any) {
      setError(getRegisterErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  if (isChecking) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#020812] text-white">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-100/80" />
      </div>
    );
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#020812] text-white selection:bg-cyan-300/25">
      <RegisterSequenceBackdrop />
      <IntroGateOverlay sequence="register" label="Sign Up" />

      <header className="fixed left-0 right-0 top-0 z-50 px-5 py-5 sm:px-7">
        <div className="mx-auto flex max-w-7xl items-center justify-between rounded-full border border-white/10 bg-[#06101d]/62 px-4 py-3 shadow-[0_24px_100px_rgba(0,0,0,0.36)] backdrop-blur-2xl sm:px-6">
          <Link href="/" className="group inline-flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.32em] text-white/72 transition hover:text-white">
            <ArrowLeft className="h-4 w-4 opacity-70 transition group-hover:-translate-x-0.5 group-hover:opacity-100" />
            Back
          </Link>

          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full border border-cyan-200/10 bg-white/[0.035] px-4 py-2 text-[10px] font-black uppercase tracking-[0.3em] text-cyan-100/72 backdrop-blur-xl sm:inline-flex">
              <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_20px_rgba(103,232,249,0.9)]" />
              AI Studio Pro
            </div>
            <ThemeToggle compact />
          </div>
        </div>
      </header>

      <section className="relative z-10 flex min-h-screen items-center px-5 pb-10 pt-28 sm:px-8">
        <div className="mx-auto grid w-full max-w-7xl items-center gap-10 lg:grid-cols-[490px_minmax(0,1fr)]">
          <MotionReveal>
            <Card className="relative overflow-hidden rounded-[34px] border border-white/14 bg-[#06111f]/66 text-white shadow-[0_38px_150px_rgba(0,0,0,0.62)] backdrop-blur-2xl">
              <div className="absolute inset-px rounded-[33px] bg-[radial-gradient(circle_at_18%_0%,rgba(45,212,191,0.18),transparent_35%),radial-gradient(circle_at_100%_100%,rgba(103,232,249,0.10),transparent_38%),linear-gradient(145deg,rgba(255,255,255,0.105),transparent_52%)]" />
              <div className="absolute inset-0 opacity-[0.045] [background-image:linear-gradient(rgba(255,255,255,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.14)_1px,transparent_1px)] [background-size:42px_42px]" />

              <div className="relative z-10 px-7 py-8 sm:px-9 sm:py-10">
                <div className="mb-8">
                  <div className="mb-4 inline-flex rounded-full border border-white/10 bg-white/[0.045] px-4 py-2 text-[10px] font-black uppercase tracking-[0.3em] text-cyan-100/70">
                    Create account
                  </div>
                  <CardTitle className="text-4xl font-black tracking-[-0.055em] text-white sm:text-5xl">
                    Start your studio.
                  </CardTitle>
                  <p className="mt-3 text-sm leading-6 text-white/60">
                    Register to access image generation, image-to-image tools, smart assistant workflows, and credits.
                  </p>
                </div>

                <form onSubmit={handleSubmit}>
                  <CardContent className="space-y-4 p-0">
                    {error && (
                      <div className="whitespace-pre-line rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm leading-6 text-red-100">
                        {String(error)}
                      </div>
                    )}

                    {success && (
                      <div className="flex items-center gap-3 rounded-2xl border border-emerald-300/25 bg-emerald-300/10 px-4 py-3 text-sm leading-6 text-emerald-100">
                        <CheckCircle className="h-5 w-5 text-emerald-200" />
                        Account created. Redirecting...
                      </div>
                    )}

                    <FieldShell active={Boolean(fullName)}>
                      <UserRound className="pointer-events-none absolute left-5 top-1/2 z-10 h-5 w-5 -translate-y-1/2 text-white/42 transition group-focus-within:text-cyan-200" />
                      <Label htmlFor="fullName" className="sr-only">Full name</Label>
                      <Input
                        id="fullName"
                        name="fullName"
                        type="text"
                        placeholder="Full name"
                        value={fullName}
                        onChange={(event) => setFullName(event.target.value)}
                        autoComplete="name"
                        className="h-16 rounded-2xl border border-white/12 bg-black/42 pl-14 pr-5 text-base text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.07)] placeholder:text-white/36 focus-visible:border-cyan-300/55 focus-visible:bg-black/50 focus-visible:ring-cyan-300/20"
                      />
                    </FieldShell>

                    <FieldShell active={Boolean(email)}>
                      <Mail className="pointer-events-none absolute left-5 top-1/2 z-10 h-5 w-5 -translate-y-1/2 text-white/42 transition group-focus-within:text-cyan-200" />
                      <Label htmlFor="email" className="sr-only">Email</Label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        placeholder="you@example.com"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        required
                        autoComplete="email"
                        className="h-16 rounded-2xl border border-white/12 bg-black/42 pl-14 pr-5 text-base text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.07)] placeholder:text-white/36 focus-visible:border-cyan-300/55 focus-visible:bg-black/50 focus-visible:ring-cyan-300/20"
                      />
                    </FieldShell>

                    <FieldShell active={Boolean(password)}>
                      <LockKeyhole className="pointer-events-none absolute left-5 top-1/2 z-10 h-5 w-5 -translate-y-1/2 text-white/42 transition group-focus-within:text-cyan-200" />
                      <Label htmlFor="password" className="sr-only">Password</Label>
                      <Input
                        id="password"
                        name="password"
                        type={showPassword ? "text" : "password"}
                        placeholder="Password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                        autoComplete="new-password"
                        className="h-16 rounded-2xl border border-white/12 bg-black/42 pl-14 pr-14 text-base text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.07)] placeholder:text-white/36 focus-visible:border-cyan-300/55 focus-visible:bg-black/50 focus-visible:ring-cyan-300/20"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((value) => !value)}
                        className="absolute right-5 top-1/2 z-20 -translate-y-1/2 text-white/36 transition hover:text-white"
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                      </button>
                    </FieldShell>

                    <div className="space-y-2">
                      <FieldShell active={Boolean(confirmPassword)}>
                        <LockKeyhole className="pointer-events-none absolute left-5 top-1/2 z-10 h-5 w-5 -translate-y-1/2 text-white/42 transition group-focus-within:text-cyan-200" />
                        <Label htmlFor="confirmPassword" className="sr-only">Confirm password</Label>
                        <Input
                          id="confirmPassword"
                          name="confirmPassword"
                          type={showConfirmPassword ? "text" : "password"}
                          placeholder="Confirm password"
                          value={confirmPassword}
                          onChange={(event) => setConfirmPassword(event.target.value)}
                          required
                          autoComplete="new-password"
                          className="h-16 rounded-2xl border border-white/12 bg-black/42 pl-14 pr-14 text-base text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.07)] placeholder:text-white/36 focus-visible:border-cyan-300/55 focus-visible:bg-black/50 focus-visible:ring-cyan-300/20"
                        />
                        <button
                          type="button"
                          onClick={() => setShowConfirmPassword((value) => !value)}
                          className="absolute right-5 top-1/2 z-20 -translate-y-1/2 text-white/36 transition hover:text-white"
                          aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                        >
                          {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                      </FieldShell>

                      <div className="rounded-2xl border border-white/10 bg-black/26 px-4 py-3">
                        <div className="mb-2 flex items-center justify-between text-[10px] font-black uppercase tracking-[0.24em] text-white/45">
                          <span>{strength.label}</span>
                          <span>{strength.pct}%</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                          <div className={`h-full rounded-full ${strength.className} transition-all duration-300`} style={{ width: `${strength.pct}%` }} />
                        </div>
                      </div>
                    </div>
                  </CardContent>

                  <CardFooter className="mt-7 flex flex-col gap-5 p-0">
                    <MagneticWrap>
                      <Button
                        type="submit"
                        disabled={isLoading || success}
                        className="relative h-16 w-full overflow-hidden rounded-2xl border border-white/10 bg-white text-base font-black uppercase tracking-[0.24em] text-[#020812] shadow-[0_22px_75px_rgba(103,232,249,0.24)] transition hover:-translate-y-0.5 hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        <span className="relative z-10 inline-flex items-center justify-center">
                          {isLoading ? (
                            <>
                              <Loader2 className="mr-3 h-5 w-5 animate-spin" />
                              Creating account
                            </>
                          ) : success ? (
                            <>Created</>
                          ) : (
                            <>Sign Up <span className="ml-4 text-xl leading-none">→</span></>
                          )}
                        </span>
                        <span className="absolute -left-1/2 top-0 h-full w-1/2 rotate-12 bg-white/70 blur-md animate-[shine_2.4s_ease-in-out_infinite]" />
                      </Button>
                    </MagneticWrap>

                    <div className="flex items-center justify-center gap-2 text-[11px] font-black uppercase tracking-[0.28em] text-white/44">
                      <ShieldCheck className="h-4 w-4 text-emerald-300/80" />
                      Secure registration
                    </div>

                    <p className="text-center text-sm text-white/55">
                      Already have an account?{" "}
                      <Link href="/login" className="font-semibold text-cyan-100 transition hover:text-white hover:underline">
                        Sign in
                      </Link>
                    </p>
                  </CardFooter>
                </form>
              </div>
            </Card>
          </MotionReveal>

          <div className="hidden lg:block" aria-hidden="true" />
        </div>
      </section>

      <style jsx global>{`
        html,
        body {
          overflow-x: hidden;
          background: #020812;
        }

        input:-webkit-autofill,
        input:-webkit-autofill:hover,
        input:-webkit-autofill:focus {
          -webkit-text-fill-color: white;
          -webkit-box-shadow: 0 0 0px 1000px rgba(0, 0, 0, 0.75) inset;
          transition: background-color 9999s ease-in-out 0s;
        }

        @keyframes shine {
          0% { transform: translateX(-120%) rotate(12deg); opacity: 0; }
          20% { opacity: 0.65; }
          50% { opacity: 0.25; }
          100% { transform: translateX(240%) rotate(12deg); opacity: 0; }
        }

        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(18px); filter: blur(10px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
      `}</style>
    </main>
  );
}

function MotionReveal({ children }: { children: React.ReactNode }) {
  return <div className="animate-[fadeUp_720ms_ease-out] [animation-fill-mode:both]">{children}</div>;
}

function FieldShell({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <div className="group relative">
      {children}
      <div
        className={`pointer-events-none absolute inset-0 rounded-2xl transition duration-300 ${
          active ? "opacity-100 [box-shadow:0_0_32px_rgba(103,232,249,0.11)]" : "opacity-0 group-focus-within:opacity-100 [box-shadow:0_0_30px_rgba(103,232,249,0.12)]"
        }`}
      />
    </div>
  );
}

function MagneticWrap({ children }: { children: React.ReactNode }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  return (
    <div
      ref={wrapRef}
      className="inline-block w-full"
      onMouseMove={(event) => {
        const rect = wrapRef.current?.getBoundingClientRect();
        if (!rect) return;
        const x = event.clientX - rect.left - rect.width / 2;
        const y = event.clientY - rect.top - rect.height / 2;
        setPosition({ x: x * 0.035, y: y * 0.05 });
      }}
      onMouseLeave={() => setPosition({ x: 0, y: 0 })}
      style={{ transform: `translate3d(${position.x}px, ${position.y}px, 0)` }}
    >
      {children}
    </div>
  );
}
