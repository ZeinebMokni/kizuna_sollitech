"use client";

import { useEffect, useState } from "react";

export interface PlatformFarm {
  id: string;
  name: string;
  code: string;
  country_code: string;
  governorate: string | null;
  timezone: string;
  boundary: unknown | null;
  data_class: string;
}

export interface PlatformUser {
  id: string;
  email: string;
  full_name: string;
  locale: string;
  roles: string[];
}

export function getPlatformToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("qatra-platform-token");
}

export function setPlatformToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("qatra-platform-token", token);
  else window.localStorage.removeItem("qatra-platform-token");
}

export async function platformRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getPlatformToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/platform-api${path}`, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail ?? `HTTP ${response.status}`);
  }
  return body as T;
}

export function usePlatformApi<T>(path: string | null) {
  const [state, setState] = useState<{
    path?: string;
    data?: T;
    error?: string;
  }>({});
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    platformRequest<T>(path)
      .then((data) => !cancelled && setState({ path, data }))
      .catch((error: Error) =>
        !cancelled && setState({ path, error: error.message }),
      );
    return () => {
      cancelled = true;
    };
  }, [path]);
  const current = state.path === path;
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: !!path && !current,
  };
}
