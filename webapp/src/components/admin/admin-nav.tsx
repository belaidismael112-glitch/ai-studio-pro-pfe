"use client";

import Link from "next/link";
import type { ElementType } from "react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Users, Layers, MessageSquareText } from "lucide-react";

type Item = {
  href: string;
  label: string;
  icon: ElementType;
};

const items: Item[] = [
  { href: "/admin", label: "Overview", icon: Layers },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/generations", label: "Generations", icon: Layers },
  { href: "/admin/complaints", label: "Reclamations", icon: MessageSquareText },
];

export function AdminNav() {
  const pathname = usePathname();

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "group inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition-all backdrop-blur",
              active
                ? "border-white/15 bg-white/10 text-white shadow-[0_0_0_1px_rgba(255,255,255,0.06),0_10px_30px_-18px_rgba(236,72,153,0.55)]"
                : "border-white/10 bg-white/5 text-white/70 hover:text-white hover:bg-white/10 hover:border-white/15"
            )}
          >
            <Icon className={cn("h-4 w-4 transition-transform", active ? "text-fuchsia-200" : "text-white/60 group-hover:text-white")} />
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
