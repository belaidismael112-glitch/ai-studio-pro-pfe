"use client";

import { normalizeApiV1Base, normalizeBackendRoot } from "@/lib/url-config";

export type AgentToolName =
  | "generate_image"
  | "regenerate"
  | "download";

export type AgentToolRequest = {
  id: string;
  tool: AgentToolName;
  title: string;
  description: string;
  requires_approval?: boolean;
  args: Record<string, any>;
};

export type AgentExecutionResult = {
  ok: boolean;
  message: string;
  resultUrl?: string | null;
  generationId?: number | string | null;
  raw?: any;
};

const API_V1_BASE = normalizeApiV1Base(
  process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL
);

const IMAGE_ENDPOINT =
  process.env.NEXT_PUBLIC_AGENT_IMAGE_ENDPOINT || "/generations/images";

const IMAGE_IMG2IMG_ENDPOINT =
  process.env.NEXT_PUBLIC_AGENT_IMAGE_IMG2IMG_ENDPOINT || "/generations/image/img2img";

const GENERATION_STATUS_ENDPOINT =
  process.env.NEXT_PUBLIC_AGENT_GENERATION_STATUS_ENDPOINT || "/generations";

function buildUrl(base: string, path: string) {
  const cleanBase = base.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
}

function normalizeApiPath(path: string) {
  const clean = String(path || "").trim() || "/";
  return clean.replace(/^https?:\/\/[^/]+/i, "").replace(/^\/api\/v1(?=\/|$)/i, "") || "/";
}

function strictIdentityReferenceBlocked(args: Record<string, any>) {
  const subjectType = String(args.subject_type || "").toLowerCase();
  const identityMode = args.identity_lock || subjectType === "person_face" || args.generation_mode === "person_identity";
  if (!identityMode) return false;

  const gateStatus = String(args.gate_status || "").toLowerCase();
  if (args.gate_allowed === false || gateStatus === "blocked") return true;

  const coverage = Number(args.subject_coverage_percent);
  const quality = Number(args.reference_quality_score);
  const preservation = Number(args.subject_preservation_score);

  // Hard-block only obviously unusable references. Premium thresholds are
  // warnings handled by Neural Camera, not a reason to destroy the workflow.
  if (!Number.isFinite(coverage) || coverage < 8) return true;
  if (Number.isFinite(quality) && quality < 35) return true;
  if (Number.isFinite(preservation) && preservation < 35) return true;
  return false;
}

function cleanToken(value?: string | null) {
  const token = String(value || "").trim();
  if (!token || token === "null" || token === "undefined") return null;
  return token;
}

function tokenFromAuthStorage(raw?: string | null) {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return cleanToken(
      parsed?.state?.accessToken ||
        parsed?.state?.access_token ||
        parsed?.state?.token ||
        parsed?.accessToken ||
        parsed?.access_token ||
        parsed?.token ||
        null
    );
  } catch {
    return null;
  }
}

function getAccessToken() {
  if (typeof window === "undefined") return null;

  const readDirectToken = () =>
    cleanToken(localStorage.getItem("access_token")) ||
    cleanToken(localStorage.getItem("accessToken")) ||
    cleanToken(localStorage.getItem("token")) ||
    cleanToken(sessionStorage.getItem("access_token")) ||
    cleanToken(sessionStorage.getItem("accessToken")) ||
    cleanToken(sessionStorage.getItem("token")) ||
    null;

  try {
    const direct = readDirectToken();
    if (direct) return direct;
  } catch {}

  return tokenFromAuthStorage(localStorage.getItem("auth-storage")) || tokenFromAuthStorage(sessionStorage.getItem("auth-storage"));
}

function authHeaders() {
  const token = getAccessToken();

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

function authHeaderObject() {
  return authHeaders();
}

function authOnlyHeaders() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function backendOrigin() {
  return normalizeBackendRoot(API_V1_BASE);
}

function resolveBackendAssetUrl(sourceUrl?: string | null) {
  if (!sourceUrl) return null;
  if (/^(https?:\/\/|blob:|data:)/i.test(sourceUrl)) return sourceUrl;
  return `${backendOrigin()}${sourceUrl.startsWith("/") ? sourceUrl : `/${sourceUrl}`}`;
}

async function fetchSourceImageAsFile(sourceUrl?: string | null, fallbackUrls: Array<string | null | undefined> = []) {
  const candidates = [sourceUrl, ...fallbackUrls].filter(Boolean) as string[];
  let lastError: Error | null = null;

  for (const candidate of candidates) {
    const assetUrl = resolveBackendAssetUrl(candidate);
    if (!assetUrl) continue;

    try {
      const needsAuth = !/^(blob:|data:)/i.test(assetUrl);
      const response = await fetch(assetUrl, needsAuth ? { headers: authOnlyHeaders() } : undefined);
      if (!response.ok) {
        throw new Error(`Could not load source image (${response.status})`);
      }

      const blob = await response.blob();
      const ext = blob.type.includes("png")
        ? "png"
        : blob.type.includes("webp")
        ? "webp"
        : "jpg";
      return new File([blob], `smart-agent-reference.${ext}`, { type: blob.type || "image/png" });
    } catch (error: any) {
      lastError = error instanceof Error ? error : new Error(String(error || "Could not load source image"));
    }
  }

  if (lastError) throw lastError;
  return null;
}


function finiteNumber(value: any, fallback: number, minimum: number, maximum: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, parsed));
}

function appendOptionalFormData(formData: FormData, key: string, value: any) {
  if (value === undefined || value === null || value === "") return;
  formData.append(key, String(value));
}

function shouldAutoCropReference(args: Record<string, any>) {
  const strategy = String(args.source_strategy || "").toLowerCase();
  if (args.auto_crop === false || args.auto_crop === "false") return false;
  if (strategy === "full_frame_camera_reference" || strategy === "full_frame_body_reference") return false;
  if (strategy === "face_crop_identity" || strategy === "subject_crop_reference") return false;
  return true;
}

function operatorEnabled() {
  return process.env.NEXT_PUBLIC_AGENT_USE_OPERATOR !== "false";
}

function operatorResultToExecutionResult(
  data: any
): AgentExecutionResult {
  const generations = data?.final_result?.generations || [];
  const typed = data?.final_result?.images?.[0];
  const generation = typed || generations[0] || data?.final_result || data;

  const rawResultUrl =
    generation?.result_url ||
    generation?.resultUrl ||
    generation?.image_url ||
    generation?.video_url ||
    generation?.thumbnail_url ||
    generation?.url ||
    null;
  const resultUrl = resolveBackendAssetUrl(rawResultUrl);

  const generationId =
    generation?.id ||
    generation?.generation_id ||
    generation?.job_id ||
    null;

  if (data?.approved === false) {
    return {
      ok: false,
      message: data?.message || "Operator could not approve or queue the generation.",
      raw: data,
    };
  }

  const failedEvent = (data?.events || []).find((event: any) => event?.status === "failed");
  if (failedEvent) {
    return {
      ok: false,
      message: failedEvent?.message || "Operator could not queue the generation.",
      raw: data,
    };
  }

  return {
    ok: true,
    message: generationId
      ? `Operator queued image generation. Generation ID: ${generationId}.`
      : "Operator queued image generation.",
    resultUrl,
    generationId,
    raw: data,
  };
}

async function executeWithOperator(
  payload: Record<string, any>,
  title: string
): Promise<AgentExecutionResult | null> {
  if (!operatorEnabled()) return null;

  try {
    const planResponse = await fetch(buildUrl(API_V1_BASE, "/operator/plan"), {
      method: "POST",
      headers: authHeaderObject(),
      body: JSON.stringify({
        command: `${title}: ${payload.prompt || ""}`,
        allow_image: true,
        max_credits: 50,
        context: {
          source: "smart_agent",
          force_mode: "image",
          direct_payload: payload,
        },
      }),
    });

    const planData = await planResponse.json().catch(() => ({}));
    if (!planResponse.ok || !planData?.session_id) {
      return {
        ok: false,
        message: extractErrorMessage(
          planData,
          `Operator planning failed with status ${planResponse.status}`
        ),
        raw: planData,
      };
    }

    const confirmResponse = await fetch(buildUrl(API_V1_BASE, "/operator/confirm"), {
      method: "POST",
      headers: authHeaderObject(),
      body: JSON.stringify({
        session_id: planData.session_id,
        approved: true,
      }),
    });

    const confirmData = await confirmResponse.json().catch(() => ({}));
    if (!confirmResponse.ok) {
      return {
        ok: false,
        message: extractErrorMessage(
          confirmData,
          `Operator confirmation failed with status ${confirmResponse.status}`
        ),
        raw: confirmData,
      };
    }

    return operatorResultToExecutionResult(confirmData);
  } catch (error: any) {
    console.warn("Smart Agent operator bridge failed:", error);
    return {
      ok: false,
      message: `Operator is enabled but unavailable. Direct-generation fallback was refused so the failure stays visible: ${error?.message || "unknown error"}`,
    };
  }
}

function extractErrorMessage(data: any, fallback: string) {
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.message === "string") return data.message;

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item: any) => {
        const loc = Array.isArray(item?.loc) ? item.loc.join(".") : "";
        const msg = item?.msg || "Validation error";
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join(" | ");
  }

  return fallback;
}

function normalizeGenerationResponse(
  data: any
): AgentExecutionResult {
  const rawResultUrl =
    data?.result_url ||
    data?.resultUrl ||
    data?.image_url ||
    data?.video_url ||
    data?.thumbnail_url ||
    data?.url ||
    data?.result?.url ||
    data?.generation?.result_url ||
    data?.generation?.thumbnail_url ||
    null;
  const resultUrl = resolveBackendAssetUrl(rawResultUrl);

  const generationId =
    data?.id ||
    data?.generation_id ||
    data?.job_id ||
    data?.generation?.id ||
    null;

  return {
    ok: true,
    message: resultUrl
      ? "Image generated. Do you like the result?"
      : "Generation started. Waiting for the result, or you can check History.",
    resultUrl,
    generationId,
    raw: data,
  };
}

export async function executeAgentTool(
  request: AgentToolRequest,
  lastResultUrl?: string | null,
  regenerateLast?: (() => Promise<AgentExecutionResult>) | null
): Promise<AgentExecutionResult> {
  if (request.tool === "download") {
    if (!lastResultUrl) {
      return {
        ok: false,
        message:
          "There is no result to download yet. Generate an image first.",
      };
    }

    const a = document.createElement("a");
    a.href = lastResultUrl;
    a.download = "ai-studio-image.png";

    document.body.appendChild(a);
    a.click();
    a.remove();

    return {
      ok: true,
      message: "Download started. Check your Downloads folder.",
      resultUrl: lastResultUrl,
    };
  }

  if (request.tool === "regenerate") {
    if (regenerateLast) {
      return regenerateLast();
    }

    return {
      ok: false,
      message:
        "I cannot regenerate because there is no saved previous action. Please give me a new prompt.",
    };
  }

  if (request.tool === "generate_image") {
    const body: Record<string, any> = {
      prompt: String(request.args.prompt || "").trim(),
      negative_prompt: String(request.args.negative_prompt || "").trim(),
      width: finiteNumber(request.args.width, 640, 256, 2048),
      height: finiteNumber(request.args.height, 896, 256, 2048),
      num_inference_steps: finiteNumber(request.args.num_inference_steps ?? request.args.steps, 24, 10, 100),
      guidance_scale: finiteNumber(request.args.guidance_scale ?? request.args.cfg, 7.0, 1.0, 20.0),
    };

    if (request.args.model_id) {
      body.model_id = String(request.args.model_id);
    }

    // Important: style is optional. Do not send "default" because the backend can reject it with 422.
    if (
      request.args.style &&
      request.args.style !== "default" &&
      request.args.style !== "Default"
    ) {
      body.style = request.args.style;
    }

    const hasSourceImage = Boolean(request.args.source_image_url);
    const preferImg2Img = hasSourceImage && request.args.prefer_img2img !== false;

    if ((request.args.identity_lock || request.args.subject_lock) && !hasSourceImage) {
      return {
        ok: false,
        message: "Generation blocked: reference image is required for identity/source-lock mode.",
      };
    }

    if (strictIdentityReferenceBlocked(request.args)) {
      return {
        ok: false,
        message: "Generation blocked: person identity reference must pass the coverage and reliability checks. Retake or crop closer before generating.",
      };
    }

    if (preferImg2Img) {
      try {
        const file = await fetchSourceImageAsFile(
          String(request.args.source_image_url),
          [request.args.original_source_image_url]
        );
        if (!file) throw new Error("Source image is missing");

        const formData = new FormData();
        formData.append("image", file);
        formData.append("prompt", body.prompt);
        formData.append("negative_prompt", body.negative_prompt);
        appendOptionalFormData(formData, "strength", request.args.strength ?? 0.10);
        appendOptionalFormData(formData, "size", `${body.width}x${body.height}`);
        appendOptionalFormData(formData, "num_inference_steps", body.num_inference_steps);
        appendOptionalFormData(formData, "guidance_scale", body.guidance_scale);
        appendOptionalFormData(formData, "style", body.style);
        appendOptionalFormData(formData, "model_id", request.args.model_id);
        appendOptionalFormData(formData, "generation_mode", request.args.generation_mode || (request.args.subject_type === "person_face" ? "person_identity" : request.args.subject_type && request.args.subject_type !== "unknown" ? "product_ad" : "auto"));
        appendOptionalFormData(formData, "auto_crop", shouldAutoCropReference(request.args) ? "true" : "false");
        appendOptionalFormData(formData, "source_strategy", request.args.source_strategy);
        appendOptionalFormData(formData, "subject_lock", request.args.subject_lock ? "true" : "");
        appendOptionalFormData(formData, "gate_status", request.args.gate_status);
        appendOptionalFormData(formData, "reference_quality_score", request.args.reference_quality_score);
        appendOptionalFormData(formData, "subject_preservation_score", request.args.subject_preservation_score);
        appendOptionalFormData(formData, "subject_coverage_percent", request.args.subject_coverage_percent);
        appendOptionalFormData(formData, "subject_type", request.args.subject_type);

        const response = await fetch(buildUrl(API_V1_BASE, normalizeApiPath(IMAGE_IMG2IMG_ENDPOINT)), {
          method: "POST",
          headers: authOnlyHeaders(),
          body: formData,
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          return {
            ok: false,
            message: extractErrorMessage(
              data,
              `Image-to-image generation failed with status ${response.status}`
            ),
            raw: data,
          };
        }

        const normalized = normalizeGenerationResponse(data);
        if (request.args.identity_review_required) {
          normalized.message += " Identity review required before client delivery.";
        }
        if (request.args.original_source_image_url) {
          normalized.message += " Face crop reference was used for stronger identity lock.";
        }
        return normalized;
      } catch (error: any) {
        console.warn("Reference-based img2img failed:", error);
        return {
          ok: false,
          message: `Reference-based image generation failed before fallback. The app refused text-to-image fallback to avoid identity/subject drift: ${error?.message || "unknown error"}`,
        };
      }
    }

    const operatorResult = !hasSourceImage
      ? await executeWithOperator(
          body,
          request.title || "Generate image"
        )
      : null;
    if (operatorResult) return operatorResult;

    const response = await fetch(buildUrl(API_V1_BASE, normalizeApiPath(IMAGE_ENDPOINT)), {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      return {
        ok: false,
        message: extractErrorMessage(
          data,
          `Image generation failed with status ${response.status}`
        ),
        raw: data,
      };
    }

    const normalized = normalizeGenerationResponse(data);
        if (request.args.identity_review_required) {
          normalized.message += " Identity review required before client delivery.";
        }
        if (request.args.original_source_image_url) {
          normalized.message += " Face crop reference was used for stronger identity lock.";
        }
        return normalized;
  }

  return {
    ok: false,
    message: `Unsupported tool: ${request.tool}`,
  };
}

export async function pollGenerationResult(
  generationId: string | number,
  maxAttempts = 90
): Promise<AgentExecutionResult> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((resolve) => setTimeout(resolve, 2000));

    const response = await fetch(
      buildUrl(API_V1_BASE, `${normalizeApiPath(GENERATION_STATUS_ENDPOINT)}/${generationId}`),
      {
        headers: authHeaders(),
      }
    );

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      return {
        ok: false,
        message: extractErrorMessage(
          data,
          `Status check failed with status ${response.status}`
        ),
        raw: data,
      };
    }

    if (data?.status === "completed") {
      const rawResultUrl =
        data?.result_url ||
        data?.resultUrl ||
        data?.image_url ||
        data?.video_url ||
        data?.thumbnail_url ||
        data?.url ||
        null;
      const resultUrl = resolveBackendAssetUrl(rawResultUrl);

      return {
        ok: true,
        message: resultUrl
          ? "Generation completed. Do you like the result?"
          : "Generation completed but no result URL was returned.",
        resultUrl,
        generationId,
        raw: data,
      };
    }

    if (data?.status === "failed") {
      return {
        ok: false,
        message: data?.error_message || "Generation failed.",
        raw: data,
      };
    }
  }

  return {
    ok: false,
    message: "Generation timed out. Check History page.",
  };
}