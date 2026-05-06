"use client";

import { API_V1_BASE, type AuthToken, type CurrentUser } from "@/lib/api";

const TOKEN_KEY = "vengage_token";

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function loginRequest(email: string, password: string): Promise<AuthToken> {
  const r = await fetch(`${API_V1_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) {
    const text = await r.text();
    let msg = "Login failed";
    try {
      msg = (JSON.parse(text) as { detail?: string }).detail ?? msg;
    } catch {
      msg = text || msg;
    }
    throw new Error(msg);
  }
  return r.json() as Promise<AuthToken>;
}

export async function fetchMe(): Promise<CurrentUser> {
  const token = getToken();
  const r = await fetch(`${API_V1_BASE}/auth/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  if (!r.ok) throw new Error("Not authenticated");
  return r.json() as Promise<CurrentUser>;
}
