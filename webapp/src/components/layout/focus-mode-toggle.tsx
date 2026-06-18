"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
}

export function FocusModeToggle({ className = "" }: { className?: string }) {
  const [isFocus, setIsFocus] = useState(false);

  useEffect(() => {
    const sync = () => {
      const active = Boolean(document.fullscreenElement) || document.documentElement.classList.contains("studio-focus-mode");
      setIsFocus(active);
      document.documentElement.classList.toggle("studio-focus-mode", active);
      document.body.classList.toggle("studio-focus-mode", active);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "f" || event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
      event.preventDefault();
      void toggleFocus();
    };

    document.addEventListener("fullscreenchange", sync);
    window.addEventListener("keydown", onKeyDown);
    sync();

    return () => {
      document.removeEventListener("fullscreenchange", sync);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  async function toggleFocus() {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        document.documentElement.classList.remove("studio-focus-mode");
        document.body.classList.remove("studio-focus-mode");
        setIsFocus(false);
        return;
      }

      document.documentElement.classList.add("studio-focus-mode");
      document.body.classList.add("studio-focus-mode");
      setIsFocus(true);
      await document.documentElement.requestFullscreen?.();
    } catch {
      const next = !document.documentElement.classList.contains("studio-focus-mode");
      document.documentElement.classList.toggle("studio-focus-mode", next);
      document.body.classList.toggle("studio-focus-mode", next);
      setIsFocus(next);
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => void toggleFocus()}
      title="Press F to toggle Focus Mode"
      className={`rounded-xl border border-cyan-300/20 bg-cyan-300/10 px-4 font-semibold text-cyan-50 shadow-[0_0_26px_rgba(34,211,238,0.12)] transition hover:border-cyan-200/40 hover:bg-cyan-300/15 ${className}`}
    >
      {isFocus ? "Exit Focus" : "Focus Mode"}
    </Button>
  );
}
