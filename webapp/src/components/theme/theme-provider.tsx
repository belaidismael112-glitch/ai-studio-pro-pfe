"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "dark";

type ThemeContextValue = {
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function applyDarkTheme() {
  if (typeof document === "undefined") return;

  document.documentElement.dataset.theme = "dark";
  document.documentElement.classList.add("dark");
  document.documentElement.style.colorScheme = "dark";

  try {
    window.localStorage.removeItem("studio-theme-mode");
  } catch {
    // ignore storage access issues
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme] = useState<ThemeMode>("dark");

  useEffect(() => {
    applyDarkTheme();
  }, []);

  const setTheme = useCallback((_nextTheme: ThemeMode) => {
    applyDarkTheme();
  }, []);

  const toggleTheme = useCallback(() => {
    applyDarkTheme();
  }, []);

  const value = useMemo(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useThemeMode() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useThemeMode must be used inside ThemeProvider");
  }

  return context;
}
