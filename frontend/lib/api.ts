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

async function assertOk(r: Response): Promise<void> {
  if (r.ok) return;
  if (r.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("vengage_token");
      window.location.href = "/login";
    }
    throw new Error("Session expired. Redirecting to login…");
  }
  const text = await r.text().catch(() => "");
  throw new Error(text || r.statusText);
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  await assertOk(r);
  return r.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  await assertOk(r);
  return r.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  await assertOk(r);
  return r.json() as Promise<T>;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  await assertOk(r);
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
  await assertOk(r);
  return r.json() as Promise<T>;
}

export async function apiDownloadBlob(path: string): Promise<Blob> {
  const r = await fetch(`${API_V1_BASE}${path}`, {
    headers: authHeaders(),
  });
  await assertOk(r);
  return r.blob();
}

export function downloadBlobAsFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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

export type UploadAttachmentsResult = {
  attachments: CustomerAttachmentRow[];
  errors: string[];
};

export type CustomerAttachmentRow = {
  id: number;
  customer_id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  qbo_attachable_id: string | null;
  created_at: string;
};

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
  product_and_service_ids: number[];
};

export type ProductAndServiceRow = {
  id: number;
  qbo_id: string;
  name: string;
  sku: string | null;
  item_type: string | null;
  active: boolean;
};

export type CenterRow = {
  id: number;
  company_id: number;
  name: string;
  created_at: string;
  updated_at: string;
};

export type InvoiceRow = {
  id: number;
  company_id: number;
  title: string | null;
  center_ids: number[];
  created_at: string;
  updated_at: string;
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
  attachments_pruned: number;
  items_upserted: number;
  items_removed_local: number;
  message: string;
};

export type QboStatus = {
  connected: boolean;
  realmId: string | null;
  tokenExpiry: number | null;
  environment: string;
};

export type InvoiceUploadDetail = {
  customer: string;
  group: string;
  qbo_invoice_id: string;
  invoice_number: string | null;
  total_amount: number;
  send_status: string;
  sent: boolean;
};

export type InvoiceUploadResult = {
  upload_id: number;
  status: string;
  total_center_rows: number;
  centers_matched: number;
  centers_skipped: number;
  invoices_created: number;
  invoices_failed: number;
  invoice_details: InvoiceUploadDetail[];
  errors: string[];
};

export async function apiUploadInvoiceFile(file: File): Promise<InvoiceUploadResult> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${API_V1_BASE}/invoice-uploads`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  await assertOk(r);
  return r.json() as Promise<InvoiceUploadResult>;
}

export type UploadHistoryRow = {
  id: number;
  file_name: string;
  status: string;
  created_at: string;
  total_invoices: number | null;
  success_count: number | null;
  failed_count: number | null;
  uploaded_by: string | null;
};

export type GeneratedInvoiceCenterRow = {
  id: number;
  center_name: string;
};

export type GeneratedInvoiceLineItemRow = {
  id: number;
  product_name: string;
  quantity: string;
  rate: string;
  amount: string;
};

export type GeneratedInvoiceRow = {
  id: number;
  invoice_number: string | null;
  quickbooks_invoice_id: string | null;
  customer_name: string | null;
  center_group_name: string;
  total_amount: string;
  send_status: string;
  error_message: string | null;
  centers: GeneratedInvoiceCenterRow[];
  line_items: GeneratedInvoiceLineItemRow[];
};

export type UploadDetailResponse = {
  id: number;
  file_name: string;
  status: string;
  created_at: string;
  total_invoices: number | null;
  success_count: number | null;
  failed_count: number | null;
  uploaded_by: string | null;
  errors: string[];
  generated_invoices: GeneratedInvoiceRow[];
};

export type AuthToken = { access_token: string; token_type: string };

export type CurrentUser = {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "supervisor";
  is_active: boolean;
};
