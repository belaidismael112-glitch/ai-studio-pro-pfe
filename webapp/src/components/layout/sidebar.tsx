"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";
import {
  LayoutDashboard,
  Image as ImageIcon,
  History as HistoryIcon,
  CreditCard,
  Settings,
  MessageSquareText,
  BarChart3,
  GitCompare,
  Bot,
  BrainCircuit,
} from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: any;
  adminOnly?: boolean;
};

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/operator", label: "Operator", icon: Bot },
  {
    href: "/dashboard/autonomous-platform",
    label: "Platform Builder",
    icon: BrainCircuit,
  },
  { href: "/generate/image", label: "Image Generation", icon: ImageIcon },
  { href: "/generate/image-to-image", label: "Image-to-Image", icon: ImageIcon },
  { href: "/history", label: "History", icon: HistoryIcon },
  { href: "/credits", label: "Credits", icon: CreditCard },
  { href: "/support", label: "Reclamations", icon: MessageSquareText },
  { href: "/compare", label: "Model Comparison", icon: GitCompare },
  { href: "/admin", label: "Admin Analytics", icon: BarChart3, adminOnly: true },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();

  const visible = navItems.filter((item) => !item.adminOnly || !!user?.is_admin);

  return (
    <aside className="theme-sidebar-surface relative hidden w-72 border-r border-white/10 bg-black/30 backdrop-blur-2xl md:block">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(168,85,247,0.08),transparent_35%),radial-gradient(circle_at_bottom_left,rgba(34,211,238,0.06),transparent_28%)]" />

      <div className="relative flex h-full flex-col p-4">
        <div className="mb-6 rounded-[24px] border border-white/10 bg-white/[0.045] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.18)]">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 grid-cols-2 gap-1 rounded-xl border border-white/10 bg-black/20 p-2">
              <span className="rounded-[4px] bg-fuchsia-400/70" />
              <span className="rounded-[4px] bg-cyan-300/60" />
              <span className="rounded-[4px] bg-white/20" />
              <span className="rounded-[4px] bg-white/10" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-[0.02em] text-white">{user?.full_name || "Studio workspace"}</p>
              <p className="max-w-[170px] truncate text-xs text-white/45">{user?.email || "Project panel"}</p>
            </div>
          </div>
        </div>

        <nav className="flex flex-col gap-2">
          {visible.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 overflow-hidden rounded-[20px] px-4 py-3 text-sm font-medium transition-all duration-300",
                  isActive
                    ? "border border-white/10 bg-white/10 text-white shadow-[0_0_25px_rgba(168,85,247,0.10)]"
                    : "border border-transparent text-white/60 hover:border-white/10 hover:bg-white/5 hover:text-white"
                )}
              >
                {isActive && (
                  <>
                    <div className="absolute inset-y-2 left-1 w-1 rounded-full bg-gradient-to-b from-fuchsia-400 to-cyan-400" />
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_left,rgba(168,85,247,0.10),transparent_45%)]" />
                  </>
                )}

                <div
                  className={cn(
                    "relative z-10 flex h-9 w-9 items-center justify-center rounded-xl transition-all duration-300",
                    isActive
                      ? "bg-white/10 text-white"
                      : "bg-white/5 text-white/60 group-hover:bg-white/10 group-hover:text-white"
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>

                <span className="relative z-10 truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto pt-6">
          <div className="rounded-[22px] border border-white/10 bg-white/[0.045] p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-white/35">Workspace</p>
            <p className="mt-2 text-sm leading-6 text-white/68">
              Images, image-to-image workflows, compare tools and project settings in one place.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
