"use client";

import { usePathname } from "next/navigation";
import { Navbar } from "./navbar";
import { Sidebar } from "./sidebar";
import { AssistantSmartAgent } from "@/components/assistant-smart-agent";
import { BackendDashboardBackdrop } from "@/components/BackendDashboardBackdrop";
import { useAuth } from "@/hooks/useAuth";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  useAuth();
  const pathname = usePathname();
  const isOperatorFlow = pathname?.startsWith("/dashboard/operator");

  return (
    <div className="theme-dashboard-shell relative min-h-screen overflow-hidden bg-[#020812] text-white">
      <BackendDashboardBackdrop />

      <div className="relative z-10 flex min-h-screen flex-col">
        <div className="sticky top-0 z-50 border-b border-white/10 bg-[#020812]/34 backdrop-blur-xl supports-[backdrop-filter]:bg-[#020812]/30">
          <Navbar />
        </div>

        <div className="flex flex-1">
          <aside className="studio-dashboard-sidebar hidden border-r border-white/10 bg-[#020812]/18 backdrop-blur-xl md:block">
            <Sidebar />
          </aside>

          <main className="theme-main-surface relative flex-1 overflow-auto">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_28%_18%,rgba(34,211,238,0.05),transparent_26%),radial-gradient(circle_at_80%_12%,rgba(168,85,247,0.05),transparent_24%)]" />
            <div className="studio-dashboard-frame relative mx-auto min-h-full w-full max-w-[1600px] p-4 md:p-6 xl:p-8">
              <div className={`human-made-frame rounded-[30px] border border-white/10 shadow-[0_0_90px_rgba(0,0,0,0.28)] ${isOperatorFlow ? "bg-[#06111f]/12 backdrop-blur-[3px]" : "bg-[#06111f]/26 backdrop-blur-md"}`}>
                <div className="min-h-[calc(100vh-140px)] p-4 md:p-6 xl:p-8">
                  {children}
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>

      <AssistantSmartAgent />
    </div>
  );
}
