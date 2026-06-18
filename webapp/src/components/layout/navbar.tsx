"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { User, LogOut, CreditCard } from "lucide-react";
import { formatCredits } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { FocusModeToggle } from "./focus-mode-toggle";
import { authApi } from "@/lib/api";

export function Navbar() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Local cleanup must still happen when the backend is unreachable.
    } finally {
      logout();
      router.push("/login");
    }
  };

  return (
    <nav className="theme-nav-surface relative border-b border-white/10 bg-black/40 backdrop-blur-2xl">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(168,85,247,0.06),transparent_60%)]" />

      <div className="relative flex h-16 items-center px-4 md:px-8">
        <Link href="/" className="flex items-center gap-3 text-xl font-bold tracking-tight text-white">
          <div className="grid h-9 w-9 grid-cols-2 gap-1 rounded-xl border border-white/10 bg-white/5 p-2">
            <span className="rounded-[4px] bg-fuchsia-400/80" />
            <span className="rounded-[4px] bg-cyan-300/70" />
            <span className="rounded-[4px] bg-white/25" />
            <span className="rounded-[4px] bg-white/12" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-base font-semibold text-white">Studio Pro</span>
            <span className="text-[10px] uppercase tracking-[0.22em] text-white/38">workspace</span>
          </div>
        </Link>

        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle compact />
          {isAuthenticated ? (
            <>
              <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-white/80 backdrop-blur sm:flex">
                <CreditCard className="h-4 w-4 text-cyan-300" />
                <span className="font-medium">{formatCredits(user?.credits || 0)} credits</span>
              </div>

              <FocusModeToggle />

              <Link href="/settings" className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-white/80 backdrop-blur lg:flex">
                <User className="h-4 w-4 text-fuchsia-300" />
                <span className="max-w-[170px] truncate">{user?.full_name || user?.email || "Account"}</span>
              </Link>

              <Link href="/dashboard">
                <Button variant="ghost" size="sm" className="rounded-xl border border-transparent hover:border-white/10 hover:bg-white/5">
                  <User className="mr-2 h-4 w-4 text-fuchsia-300" />
                  Dashboard
                </Button>
              </Link>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="rounded-xl border border-transparent hover:border-red-400/30 hover:bg-red-500/10"
              >
                <LogOut className="mr-2 h-4 w-4 text-red-400" />
                Logout
              </Button>
            </>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost" size="sm" className="rounded-xl border border-transparent hover:border-white/10 hover:bg-white/5">
                  Login
                </Button>
              </Link>

              <Link href="/register">
                <Button size="sm" className="rounded-xl bg-gradient-to-r from-fuchsia-500 via-pink-500 to-violet-500 text-white shadow-[0_0_25px_rgba(217,70,239,0.35)] hover:opacity-95">
                  Get Started
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
