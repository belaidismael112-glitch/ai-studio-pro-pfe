import { normalizeApiV1Base, normalizeBackendRoot } from "@/lib/url-config";

export type OperatorAction = {
  id: string;
  type: string;
  title: string;
  description: string;
  credits_cost: number;
  requires_confirmation: boolean;
  status: string;
  payload: Record<string, unknown>;
};

export type OperatorPlanRequest = {
  command: string;
  brand_name?: string;
  max_credits?: number;
  allow_image?: boolean;
  auto_execute_safe_actions?: boolean;
  context?: Record<string, unknown>;
};

export type OperatorPlanResponse = {
  session_id: string;
  title: string;
  summary: string;
  total_estimated_credits: number;
  requires_confirmation: boolean;
  actions: OperatorAction[];
  assistant_message: string;
  cursor_script: Array<Record<string, unknown>>;
};

export type OperatorExecutionEvent = {
  id: string;
  kind: string;
  title: string;
  message: string;
  status: string;
  progress: number;
  cursor_target: { x?: number; y?: number; label?: string };
  data: Record<string, unknown>;
};

export type OperatorExecutionResponse = {
  session_id: string;
  approved: boolean;
  message: string;
  events: OperatorExecutionEvent[];
  final_result: Record<string, unknown>;
};

export type GenerationStatus = "queued" | "pending" | "processing" | "completed" | "failed";

export type GenerationResponse = {
  id: number;
  generation_type: "image" | "video" | "img2img" | "img2vid";
  prompt: string;
  status: GenerationStatus;
  result_url?: string | null;
  thumbnail_url?: string | null;
  error_message?: string | null;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  credits_used: number;
  created_at: string;
  completed_at?: string | null;
};

const API_BASE = normalizeApiV1Base(
  process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL
);
const BACKEND_ROOT = normalizeBackendRoot(API_BASE);

export function resolveOperatorAssetUrl(url?: string | null) {
  if (!url) return null;
  if (/^(https?:\/\/|blob:|data:)/i.test(url)) return url;
  return `${BACKEND_ROOT}${url.startsWith("/") ? url : `/${url}`}`;
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

function getToken() {
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

async function parseResponse(response: Response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  const data = await parseResponse(response);

  if (!response.ok) {
    const detail =
      typeof data === "object" && data
        ? (data as any).detail || (data as any).message || (data as any).error
        : data;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail || `HTTP ${response.status}`));
  }

  return data as T;
}

export const aiOperatorApi = {
  health() {
    return requestJson<{ status: string; module: string; version: string }>("/operator/health");
  },

  createPlan(payload: OperatorPlanRequest) {
    return requestJson<OperatorPlanResponse>("/operator/plan", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  confirm(sessionId: string, approved: boolean) {
    return requestJson<OperatorExecutionResponse>("/operator/confirm", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, approved }),
    });
  },

  getGeneration(id: number) {
    return requestJson<GenerationResponse>(`/generations/${id}`);
  },
};
