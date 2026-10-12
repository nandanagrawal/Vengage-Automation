"use client";

import { API_V1_BASE, type CurrentUser } from "@/lib/api";

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

export type LoginResult =
  | { status: "success"; access_token: string }
  | { status: "setup_required"; pending_token: string; qr_code_data_uri: string; manual_entry_key: string }
  | { status: "verify_required"; pending_token: string };

export type TwoFactorSuccess = { access_token: string; backup_codes: string[] | null };

async function parseErrorAndThrow(r: Response): Promise<never> {
  const text = await r.text();
  let msg = "Request failed";
  try {
    msg = (JSON.parse(text) as { detail?: string }).detail ?? msg;
  } catch {
    msg = text || msg;
  }
  throw new Error(msg);
}

// `credentials: "include"` on the three calls below: the trusted-device
// cookie is cross-origin (API runs on a different port than the frontend),
// so it needs an explicit opt-in both to be sent (login) and accepted
// (setup/confirm, verify) by the browser.

export async function loginRequest(email: string, password: string): Promise<LoginResult> {
  const r = await fetch(`${API_V1_BASE}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) return parseErrorAndThrow(r);
  return r.json() as Promise<LoginResult>;
}

export async function confirmTwoFactorSetup(
  pendingToken: string,
  code: string,
  rememberDevice: boolean,
): Promise<TwoFactorSuccess> {
  const r = await fetch(`${API_V1_BASE}/auth/2fa/setup/confirm`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pending_token: pendingToken, code, remember_device: rememberDevice }),
  });
  if (!r.ok) return parseErrorAndThrow(r);
  return r.json() as Promise<TwoFactorSuccess>;
}

export async function verifyTwoFactor(
  pendingToken: string,
  code: string,
  rememberDevice: boolean,
): Promise<TwoFactorSuccess> {
  const r = await fetch(`${API_V1_BASE}/auth/2fa/verify`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pending_token: pendingToken, code, remember_device: rememberDevice }),
  });
  if (!r.ok) return parseErrorAndThrow(r);
  return r.json() as Promise<TwoFactorSuccess>;
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
