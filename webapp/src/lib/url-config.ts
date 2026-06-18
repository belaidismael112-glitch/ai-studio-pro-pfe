const DEFAULT_BACKEND_ROOT = "http://127.0.0.1:8000";

export function normalizeBackendRoot(raw?: string | null) {
  const value = String(raw || DEFAULT_BACKEND_ROOT).trim().replace(/\/+$/, "");
  return value.replace(/\/api\/v1$/i, "");
}

export function normalizeApiV1Base(raw?: string | null) {
  const value = String(raw || DEFAULT_BACKEND_ROOT).trim().replace(/\/+$/, "");
  return /\/api\/v1$/i.test(value) ? value : `${value}/api/v1`;
}
