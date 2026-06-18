"use client";

import { withAuthHeaders } from "@/lib/auth-fetch";

export type AudienceLang = "auto" | "en" | "fr";
export type ContentType = "image" | "brand_pack" | "prompt" | "other";
export type AudienceSet = "general" | "students" | "workers" | "premium" | "social";

export type PersonaReview = {
  persona: string;
  first_impression: string;
  understood: string;
  liked: string;
  confused: string;
  click_probability: number;
  improvement: string;
};

export type AudienceScores = {
  clarity: number;
  emotional_appeal: number;
  conversion_chance: number;
  brand_fit: number;
  trust: number;
  urgency: number;
  curiosity: number;
  premium_feel: number;
};

export type AudienceSuggestion = {
  action: "fix_prompt" | "generate_image" | "copy_review";
  title: string;
  description: string;
  prompt: string;
  negative_prompt?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
};

export type AudienceReview = {
  success: boolean;
  code_version?: string;
  provider?: string;
  analysis_mode?: string;
  lang: string;
  content_title: string;
  content_type: ContentType;
  audience_set: AudienceSet;
  executive_summary: string;
  scores: AudienceScores;
  personas: PersonaReview[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  improved_prompt: string;
  negative_prompt: string;
  publish_advice: string;
  suggestions: AudienceSuggestion[];
  error?: string | null;
};

export async function createAudienceReview(params: {
  apiBase: string;
  contentTitle: string;
  contentType: ContentType;
  content: string;
  brandName: string;
  targetAudience: string;
  audienceSet: AudienceSet;
  lang: AudienceLang;
  modelMode?: "auto" | "fast" | "advanced";
}): Promise<AudienceReview> {
  const response = await fetch(`${params.apiBase}/assistant/audience/review`, {
    method: "POST",
    headers: withAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      content_title: params.contentTitle,
      content_type: params.contentType,
      content: params.content,
      brand_name: params.brandName,
      target_audience: params.targetAudience,
      audience_set: params.audienceSet,
      lang: params.lang,
      model_mode: params.modelMode || "advanced",
    }),
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.detail || data?.error || `Audience Mirror failed: ${response.status}`);
  }

  if (!data?.success) {
    throw new Error(data?.error || "Audience Mirror returned an invalid response");
  }

  return data as AudienceReview;
}

export function audienceReviewToText(review: AudienceReview): string {
  return [
    `Audience Mirror Review: ${review.content_title}`,
    `Type: ${review.content_type}`,
    `Audience set: ${review.audience_set}`,
    `Mode: ${review.analysis_mode || "rule-based guidance"}`,
    "",
    "Executive summary:",
    review.executive_summary,
    "",
    "Scores:",
    `Clarity: ${review.scores.clarity}/100`,
    `Emotional appeal: ${review.scores.emotional_appeal}/100`,
    `Conversion chance: ${review.scores.conversion_chance}/100`,
    `Brand fit: ${review.scores.brand_fit}/100`,
    `Trust: ${review.scores.trust}/100`,
    `Urgency: ${review.scores.urgency}/100`,
    `Curiosity: ${review.scores.curiosity}/100`,
    `Premium feel: ${review.scores.premium_feel}/100`,
    "",
    "Personas:",
    ...review.personas.flatMap((p) => [
      `- ${p.persona}`,
      `  First impression: ${p.first_impression}`,
      `  Understood: ${p.understood}`,
      `  Liked: ${p.liked}`,
      `  Confused: ${p.confused}`,
      `  Indicative signal: ${p.click_probability}%`,
      `  Improvement: ${p.improvement}`,
    ]),
    "",
    "Strengths:",
    ...review.strengths.map((x) => `- ${x}`),
    "",
    "Weaknesses:",
    ...review.weaknesses.map((x) => `- ${x}`),
    "",
    "Recommendations:",
    ...review.recommendations.map((x) => `- ${x}`),
    "",
    "Publish advice:",
    review.publish_advice,
    "",
    "Improved prompt:",
    review.improved_prompt,
    "",
    "Negative prompt:",
    review.negative_prompt,
  ].join("\n");
}
