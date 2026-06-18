"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Eye, EyeOff, Loader2, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";
import Lenis from "lenis";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardFooter, CardTitle } from "@/components/ui/card";
import { LoginSequenceBackdrop } from "@/components/LoginSequenceBackdrop";
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
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.detail === "string") return obj.detail;
    if (Array.isArray(obj.detail)) return normalizeApiError(obj.detail);
    try {
      return JSON.stringify(obj);
    } catch {
      return "Something went wrong.";
    }
  }
  return String(value);
}

function getLoginErrorMessage(error: any): string {
  const data = error?.response?.data;
  const message =
    normalizeApiError(data?.detail) ||
    normalizeApiError(data?.message) ||
    normalizeApiError(data) ||
    normalizeApiError(error?.message);
  return message || "Invalid email or password.";
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const { isLoading: isChecking } = useGuestOnly();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

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
    const cleanEmail = email.trim();
    const cleanPassword = password.trim();
    setError("");

    if (!cleanEmail) return setError("Please enter your email.");
    if (!isValidEmail(cleanEmail)) return setError("Please enter a valid email address.");
    if (!cleanPassword) return setError("Please enter your password.");

    setIsLoading(true);
    try {
      await login({ email: cleanEmail, password: cleanPassword });
      router.push("/dashboard");
    } catch (err: any) {
      setError(getLoginErrorMessage(err));
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
      <LoginSequenceBackdrop />
      <IntroGateOverlay sequence="login" label="Sign In" />

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
        <div className="mx-auto grid w-full max-w-7xl items-center gap-10 lg:grid-cols-[470px_minmax(0,1fr)]">
          <MotionReveal>
            <Card className="relative overflow-hidden rounded-[34px] border border-white/14 bg-[#06111f]/66 text-white shadow-[0_38px_150px_rgba(0,0,0,0.62)] backdrop-blur-2xl">
              <div className="absolute inset-px rounded-[33px] bg-[radial-gradient(circle_at_18%_0%,rgba(103,232,249,0.18),transparent_35%),radial-gradient(circle_at_100%_100%,rgba(45,212,191,0.10),transparent_38%),linear-gradient(145deg,rgba(255,255,255,0.105),transparent_52%)]" />
              <div className="absolute inset-0 opacity-[0.045] [background-image:linear-gradient(rgba(255,255,255,0.18)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.14)_1px,transparent_1px)] [background-size:42px_42px]" />

              <div className="relative z-10 px-7 py-8 sm:px-9 sm:py-10">
                <div className="mb-8">
                  <div className="mb-4 inline-flex rounded-full border border-white/10 bg-white/[0.045] px-4 py-2 text-[10px] font-black uppercase tracking-[0.3em] text-cyan-100/70">
                    Secure access
                  </div>
                  <CardTitle className="text-4xl font-black tracking-[-0.055em] text-white sm:text-5xl">
                    Welcome back.
                  </CardTitle>
                  <p className="mt-3 text-sm leading-6 text-white/60">
                    Sign in to continue to your AI Studio Pro workspace.
                  </p>
                </div>

                <form onSubmit={handleSubmit}>
                  <CardContent className="space-y-5 p-0">
                    {error && (
                      <div className="whitespace-pre-line rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm leading-6 text-red-100">
                        {String(error)}
                      </div>
                    )}

                    <FieldShell active={Boolean(email)}>
                      <UserRound className="pointer-events-none absolute left-5 top-1/2 z-10 h-5 w-5 -translate-y-1/2 text-white/42 transition group-focus-within:text-cyan-200" />
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
                        placeholder="••••••••••••"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                        autoComplete="current-password"
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
                  </CardContent>

                  <CardFooter className="mt-8 flex flex-col gap-6 p-0">
                    <MagneticWrap>
                      <Button
                        type="submit"
                        disabled={isLoading}
                        className="relative h-16 w-full overflow-hidden rounded-2xl border border-white/10 bg-white text-base font-black uppercase tracking-[0.24em] text-[#020812] shadow-[0_22px_75px_rgba(103,232,249,0.24)] transition hover:-translate-y-0.5 hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-70"
                      >
                        <span className="relative z-10 inline-flex items-center justify-center">
                          {isLoading ? (
                            <>
                              <Loader2 className="mr-3 h-5 w-5 animate-spin" />
                              Signing in
                            </>
                          ) : (
                            <>Sign In <span className="ml-4 text-xl leading-none">→</span></>
                          )}
                        </span>
                        <span className="absolute -left-1/2 top-0 h-full w-1/2 rotate-12 bg-white/70 blur-md animate-[shine_2.4s_ease-in-out_infinite]" />
                      </Button>
                    </MagneticWrap>

                    <div className="flex items-center justify-center gap-2 text-[11px] font-black uppercase tracking-[0.28em] text-white/44">
                      <ShieldCheck className="h-4 w-4 text-emerald-300/80" />
                      Protected workspace
                    </div>

                    <p className="text-center text-sm text-white/56">
                      Don&apos;t have an account?{" "}
                      <Link href="/register" className="font-semibold text-cyan-100 transition hover:text-white hover:underline">
                        Sign up
                      </Link>
                    </p>
                  </CardFooter>
                </form>
              </div>
            </Card>
          </MotionReveal>

          <div className="hidden min-h-[62vh] lg:block" aria-hidden="true" />
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
          -webkit-box-shadow: 0 0 0px 1000px rgba(0, 0, 0, 0.72) inset;
          transition: background-color 9999s ease-in-out 0s;
        }

        @keyframes shine {
          0% { transform: translateX(-120%) rotate(12deg); opacity: 0; }
          22% { opacity: 0.55; }
          55% { opacity: 0.18; }
          100% { transform: translateX(260%) rotate(12deg); opacity: 0; }
        }

        @keyframes fadeUpClean {
          from { opacity: 0; transform: translateY(18px); filter: blur(10px); }
          to { opacity: 1; transform: translateY(0); filter: blur(0); }
        }
      `}</style>
    </main>
  );
}

function MotionReveal({ children, delay = "0ms" }: { children: React.ReactNode; delay?: string }) {
  return (
    <div className="animate-[fadeUpClean_760ms_ease-out] [animation-fill-mode:both]" style={{ animationDelay: delay }}>
      {children}
    </div>
  );
}

function FieldShell({ children, active }: { children: React.ReactNode; active: boolean }) {
  return (
    <div className="group relative">
      {children}
      <div className={`pointer-events-none absolute inset-0 rounded-2xl transition duration-300 ${active ? "opacity-100 [box-shadow:0_0_32px_rgba(103,232,249,0.12)]" : "opacity-0 group-focus-within:opacity-100 [box-shadow:0_0_32px_rgba(103,232,249,0.13)]"}`} />
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
        setPosition({ x: x * 0.055, y: y * 0.055 });
      }}
      onMouseLeave={() => setPosition({ x: 0, y: 0 })}
      style={{ transform: `translate3d(${position.x}px, ${position.y}px, 0)`, transition: "transform 120ms ease-out" }}
    >
      {children}
    </div>
  );
}
