"use client";

import { useAuthStore } from "@/store/authStore";

/** Add the current bearer token to direct fetch calls that cannot use Axios. */
export function withAuthHeaders(headers: Record<string, string> = {}) {
  const accessToken = useAuthStore.getState().accessToken;
  return {
    ...headers,
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };
}
