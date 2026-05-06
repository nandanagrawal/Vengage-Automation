function stripTrailingSlash(s: string): string {
  return s.replace(/\/$/, "");
}

export const API_ORIGIN = stripTrailingSlash(
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000",
);

const API_V1_PREFIX = stripTrailingSlash(process.env.NEXT_PUBLIC_API_V1_PREFIX ?? "/api/v1");
export const API_V1_BASE = `${API_ORIGIN}${API_V1_PREFIX.startsWith("/") ? API_V1_PREFIX : `/${API_V1_PREFIX}`}`;
export const QBO_AUTH_PREFIX = "/api/auth";

function authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("vengage_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  if (r.status === 204 || r.headers.get("content-length") === "0") return {} as T;
  const text = await r.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export async function apiUpload<T>(path: string, files: File[]): Promise<T> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
}

export async function qboAuthGet<T>(path: string): Promise<T> {
  const p = path.startsWith("/") ? path : `/${path}`;
  const r = await fetch(`${API_ORIGIN}${QBO_AUTH_PREFIX}${p}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
}

export async function qboAuthDelete<T>(path: string): Promise<T> {
  const p = path.startsWith("/") ? path : `/${path}`;
  const r = await fetch(`${API_ORIGIN}${QBO_AUTH_PREFIX}${p}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  if (r.status === 204 || r.headers.get("content-length") === "0") return {} as T;
  const text = await r.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export function qboConnectUrl(): string {
  return `${API_ORIGIN}${QBO_AUTH_PREFIX}/connect`;
}

// ── Types ──────────────────────────────────────────────────────────────────

export type CustomerStatus = "pending" | "approved" | "rejected";

export type CustomerRow = {
  id: number;
  status: CustomerStatus;
  created_by_id: number | null;
  approved_by_id: number | null;
  qbo_id: string | null;

  title: string | null;
  given_name: string | null;
  middle_name: string | null;
  family_name: string | null;
  suffix: string | null;
  company_name: string | null;
  display_name: string;

  primary_email: string | null;
  phone_number: string | null;
  cc_email: string | null;
  bcc_email: string | null;
  mobile: string | null;
  fax: string | null;
  other_contact: string | null;
  website: string | null;
  print_on_check_name: string | null;

  billing_line1: string | null;
  billing_line2: string | null;
  billing_line3: string | null;
  billing_line4: string | null;
  billing_city: string | null;
  billing_state: string | null;
  billing_zip: string | null;
  billing_country: string | null;
  ship_same_as_billing: boolean;
  shipping_line1: string | null;
  shipping_line2: string | null;
  shipping_line3: string | null;
  shipping_line4: string | null;
  shipping_city: string | null;
  shipping_state: string | null;
  shipping_zip: string | null;
  shipping_country: string | null;

  notes: string | null;
  rate: string;
  add_attachment_in_mail: boolean;

  created_at: string;
  updated_at: string;
  qbo_last_updated: string | null;
  last_pushed_to_qbo_at: string | null;
};

export type InvoiceActivityRow = {
  customer_display_name: string;
  invoice_number: string;
  email_status: string;
  txn_date?: string | null;
};

export type SyncResult = {
  customers_pulled: number;
  customers_pushed: number;
  customers_created_remote: number;
  invoice_activity_rows: number;
  message: string;
};

export type QboStatus = {
  connected: boolean;
  realmId: string | null;
  tokenExpiry: number | null;
  environment: string;
};

export type AuthToken = { access_token: string; token_type: string };

export type CurrentUser = {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "supervisor";
  is_active: boolean;
};
