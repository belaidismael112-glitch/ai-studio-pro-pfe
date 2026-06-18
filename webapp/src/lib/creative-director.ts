"use client";

import { withAuthHeaders } from "@/lib/auth-fetch";

export type DirectorLang = "auto" | "en" | "fr";
export type DirectorTarget = "image";

export type DirectorSuggestion = {
  action: "generate_image" | "make_prompt";
  title: string;
  description: string;
  prompt: string;
  negative_prompt?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
};

export type DirectorPlan = {
  success: boolean;
  code_version?: string;
  provider?: string;
  analysis_mode?: string;
  lang: string;
  target: DirectorTarget;
  title: string;
  summary: string;
  scene: string;
  style: string;
  lighting: string;
  camera: string;
  mood: string;
  improved_prompt: string;
  negative_prompt: string;
  caption: string;
  suggestions: DirectorSuggestion[];
  error?: string | null;
};

export async function createDirectorPlan(params: {
  apiBase: string;
  idea: string;
  lang: DirectorLang;
  target: DirectorTarget;
  pageContext?: string;
  modelMode?: "auto" | "fast" | "advanced";
}): Promise<DirectorPlan> {
  const response = await fetch(`${params.apiBase}/assistant/creative/plan`, {
    method: "POST",
    headers: withAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      idea: params.idea,
      lang: params.lang,
      target: params.target,
      page_context: params.pageContext || "",
      model_mode: params.modelMode || "advanced",
    }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail || data?.error || `Director Mode failed: ${response.status}`
    );
  }

  if (!data?.success) {
    throw new Error(data?.error || "Director Mode returned an invalid response");
  }

  return data as DirectorPlan;
}
