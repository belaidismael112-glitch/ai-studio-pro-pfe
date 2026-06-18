import type { RunResponse, WorkflowPayload } from "@/components/autonomous-platform-pro/types";
import { normalizeApiV1Base } from "@/lib/url-config";

const API_BASE = normalizeApiV1Base(
  process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL
);
const IMAGE_ENDPOINT = process.env.NEXT_PUBLIC_AGENT_IMAGE_ENDPOINT || "/generations/images";
const STATUS_ENDPOINT = process.env.NEXT_PUBLIC_AGENT_GENERATION_STATUS_ENDPOINT || "/generations";

function joinUrl(base: string, path: string) {
  const cleanBase = base.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
}

function normalizeApiPath(path: string) {
  const clean = String(path || "").trim() || "/";
  // API_BASE already points to /api/v1. Accept env values with or without /api/v1.
  return clean.replace(/^https?:\/\/[^/]+/i, "").replace(/^\/api\/v1(?=\/|$)/i, "") || "/";
}

function resolveAssetUrl(url: string) {
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/")) {
    const backendRoot = API_BASE.replace(/\/api\/v1$/i, "");
    return `${backendRoot}${url}`;
  }
  return url;
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

function readStoredToken() {
  if (typeof window === "undefined") return null;

  const direct =
    cleanToken(localStorage.getItem("access_token")) ||
    cleanToken(localStorage.getItem("accessToken")) ||
    cleanToken(localStorage.getItem("token")) ||
    cleanToken(sessionStorage.getItem("access_token")) ||
    cleanToken(sessionStorage.getItem("accessToken")) ||
    cleanToken(sessionStorage.getItem("token"));

  if (direct) return direct;

  return tokenFromAuthStorage(localStorage.getItem("auth-storage")) || tokenFromAuthStorage(sessionStorage.getItem("auth-storage"));
}

function headers(includeContentType = true) {
  const token = readStoredToken();
  return {
    ...(includeContentType ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function parse(res: Response) {
  const text = await res.text();

  let data: any = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
        ? data.detail.map((d: any) => d?.msg || JSON.stringify(d)).join(" | ")
        : data?.message ||
          data?.error ||
          data?.raw ||
          (res.status === 401
            ? "Invalid authentication credentials. Log out then sign in again."
            : `Request failed: ${res.status}`);

    throw new Error(detail);
  }

  return data;
}

export function extractAssetUrl(data: any): string | undefined {
  if (!data) return undefined;

  const candidates = [
    data?.result_url,
    data?.resultUrl,
    data?.image_url,
    data?.video_url,
    data?.thumbnail_url,
    data?.file_url,
    data?.output_url,
    data?.url,
    data?.path,
    data?.asset_url,
    data?.data?.result_url,
    data?.data?.url,
    data?.data?.image_url,
    data?.data?.video_url,
    data?.result?.url,
    data?.result?.image_url,
    data?.result?.video_url,
    data?.generation?.result_url,
    data?.generation?.url,
    data?.generation?.image_url,
    data?.generation?.video_url,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) return resolveAssetUrl(candidate);
  }

  return undefined;
}

export function extractGenerationId(data: any): string | undefined {
  if (!data) return undefined;

  const candidates = [
    data?.id,
    data?.generation_id,
    data?.task_id,
    data?.job_id,
    data?.uuid,
    data?.data?.id,
    data?.data?.generation_id,
    data?.result?.id,
    data?.generation?.id,
    data?.generation?.generation_id,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" || typeof candidate === "number") return String(candidate);
  }

  return undefined;
}

export function getApiBase() {
  return API_BASE;
}

export async function planAutonomousPlatform(payload: WorkflowPayload): Promise<RunResponse> {
  const res = await fetch(joinUrl(API_BASE, "/autonomous-platform/plan"), {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return parse(res);
}

export async function runAutonomousPlatform(payload: WorkflowPayload): Promise<RunResponse> {
  const res = await fetch(joinUrl(API_BASE, "/autonomous-platform/run"), {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return parse(res);
}

export async function callGeneration(payload: Record<string, any>) {
  const endpoint = normalizeApiPath(IMAGE_ENDPOINT);

  const body: Record<string, any> = { ...payload };
  if (!body?.style || body.style === "default" || body.style === "Default") {
    delete body.style;
  }

  const res = await fetch(joinUrl(API_BASE, endpoint), {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });

  return parse(res);
}

export async function getGenerationStatus(generationId: string) {
  const res = await fetch(joinUrl(API_BASE, `${normalizeApiPath(STATUS_ENDPOINT)}/${generationId}`), {
    method: "GET",
    headers: headers(false),
  });

  return parse(res);
}

export async function pollGenerationResult(
  generationId: string,
  options?: { attempts?: number; delayMs?: number }
) {
  const attempts = options?.attempts ?? 30;
  const delayMs = options?.delayMs ?? 2000;

  for (let i = 0; i < attempts; i++) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    const status = await getGenerationStatus(generationId);
    const assetUrl = extractAssetUrl(status);
    const state =
      status?.status ||
      status?.state ||
      status?.data?.status ||
      status?.generation?.status ||
      status?.result?.status;

    if (assetUrl) {
      return { status, assetUrl };
    }

    if (typeof state === "string" && ["failed", "error", "cancelled"].includes(state.toLowerCase())) {
      throw new Error(status?.error_message || status?.error || status?.message || `Generation ${state}`);
    }
  }

  return { status: null, assetUrl: undefined };
}
