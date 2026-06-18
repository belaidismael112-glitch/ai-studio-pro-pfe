"use client";

import { withAuthHeaders } from "@/lib/auth-fetch";

export type BrandLang = "auto" | "en" | "fr";
export type BrandTarget = "image";

export type BrandSuggestion = {
  action: "generate_image" | "copy_pack";
  title: string;
  description: string;
  prompt: string;
  negative_prompt?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
};

export type BrandPack = {
  success: boolean;
  code_version?: string;
  provider?: string;
  analysis_mode?: string;
  lang: string;
  target: BrandTarget;
  brand_name: string;
  business_type: string;
  audience: string;
  slogan: string;
  brand_voice: string;
  colors: string[];
  description: string;
  captions: string[];
  hashtags: string[];
  cta: string;
  image_prompt: string;
  negative_prompt: string;
  launch_plan: string[];
  suggestions: BrandSuggestion[];
  error?: string | null;
};

export async function createBrandPack(params: {
  apiBase: string;
  brandName: string;
  businessType: string;
  audience: string;
  idea: string;
  lang: BrandLang;
  target: BrandTarget;
  modelMode?: "auto" | "fast" | "advanced";
}): Promise<BrandPack> {
  const response = await fetch(`${params.apiBase}/assistant/brand/pack`, {
    method: "POST",
    headers: withAuthHeaders({
      "Content-Type": "application/json",
    }),
    body: JSON.stringify({
      brand_name: params.brandName,
      business_type: params.businessType,
      audience: params.audience,
      idea: params.idea,
      lang: params.lang,
      target: params.target,
      model_mode: params.modelMode || "advanced",
    }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail || data?.error || `Brand Studio failed: ${response.status}`
    );
  }

  if (!data?.success) {
    throw new Error(data?.error || "Brand Studio returned an invalid response");
  }

  return data as BrandPack;
}

export function brandPackToText(pack: BrandPack): string {
  return [
    `Brand: ${pack.brand_name}`,
    `Type: ${pack.business_type}`,
    `Audience: ${pack.audience}`,
    `Slogan: ${pack.slogan}`,
    `Brand voice: ${pack.brand_voice}`,
    `Colors: ${pack.colors.join(", ")}`,
    "",
    "Description:",
    pack.description,
    "",
    "Captions:",
    ...pack.captions.map((caption) => `- ${caption}`),
    "",
    "Hashtags:",
    pack.hashtags.join(" "),
    "",
    "CTA:",
    pack.cta,
    "",
    "Launch plan:",
    ...pack.launch_plan.map((step) => `- ${step}`),
    "",
    "Image prompt:",
    pack.image_prompt,
    "",
    "Negative prompt:",
    pack.negative_prompt,
  ].join("\n");
}
