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
  let message = text || r.statusText;
  try {
    const json = JSON.parse(text) as Record<string, unknown>;
    if (json?.detail) message = String(json.detail);
  } catch { /* not JSON */ }
  throw new Error(message);
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
  add_attachment_in_mail: boolean;

  created_at: string;
  updated_at: string;
  qbo_last_updated: string | null;
  last_pushed_to_qbo_at: string | null;
  customer_services: CustomerServiceRow[];
  customer_type_ids: number[];
};

export type CustomerTypeRow = {
  id: number;
  name: string;
  status: boolean;
  created_at: string;
  updated_at: string;
};

export type ServiceCodeRow = {
  id: number;
  code: string;
  status: boolean;
  created_at: string;
  updated_at: string;
};

export type CustomerServiceRow = {
  id: number;
  product_and_service_id: number;
  rate: string;
  description: string | null;
};

export type ProductAndServiceRow = {
  id: number;
  qbo_id: string;
  name: string;
  sku: string | null;
  item_type: string | null;
  active: boolean;
  description: string | null;
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

export type SyncResult = {
  customers_pulled: number;
  customers_pushed: number;
  customers_created_remote: number;
  invoice_activity_rows: number;
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
  sent_at: string | null;
  send_status: string;
  sent: boolean;
  generated_invoice_id: number | null;
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
  sent_at: string | null;
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

export type DashboardStats = {
  total_customers: number;
  imports_today: number;
  invoices_sent: number;
  delivery_failures: number;
  pending_customers: number;
  approved_customers: number;
};

export type RecentInvoiceRow = {
  id: number;
  invoice_number: string | null;
  customer_name: string | null;
  group: string;
  sent_at: string | null;
  send_status: string;
  file_name: string | null;
};

// ── Invoice validation / multi-step flow ──────────────────────────────────────

export type ValidatedRow = {
  row_index: number;
  center_id: string;
  center_name: string;
  center_prefix: string;
  metrics: Record<string, number>;
  errors: string[];
  customer_id: number | null;
  customer_display_name: string | null;
  matched: boolean;
};

export type CustomerError = {
  customer_display_name: string;
  errors: string[];
};

export type ValidationResponse = {
  metric_columns: string[];
  rows: ValidatedRow[];
  customer_errors: CustomerError[];
  has_errors: boolean;
};

export type PreviewCenter = {
  center_id: string;
  center_name: string;
  center_prefix: string;
  metrics: Record<string, number>;
};

export type PreviewGroup = {
  group_label: string;
  centers: PreviewCenter[];
};

export type PreviewCustomer = {
  customer_id: number;
  display_name: string;
  add_attachment_in_mail: boolean;
  primary_email: string | null;
  has_qbo_id: boolean;
  groups: PreviewGroup[];
};

export type PreviewResponse = {
  metric_columns: string[];
  customers: PreviewCustomer[];
  warnings: string[];
};

export type GenerateRequest = {
  metric_columns: string[];
  rows: ValidatedRow[];
};

export async function apiValidateInvoiceFile(file: File): Promise<ValidationResponse> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch(`${API_V1_BASE}/invoice-uploads/validate`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  await assertOk(r);
  return r.json() as Promise<ValidationResponse>;
}

export async function apiRevalidate(
  metric_columns: string[],
  rows: ValidatedRow[],
): Promise<ValidationResponse> {
  return apiPost<ValidationResponse>("/invoice-uploads/revalidate", { metric_columns, rows });
}

export async function apiPreview(
  metric_columns: string[],
  rows: ValidatedRow[],
): Promise<PreviewResponse> {
  return apiPost<PreviewResponse>("/invoice-uploads/preview", { metric_columns, rows });
}

export type GenerateJobResponse = { upload_id: number; status: string };

export async function apiGenerateInvoices(req: GenerateRequest): Promise<GenerateJobResponse> {
  return apiPost<GenerateJobResponse>("/invoice-uploads/generate", req);
}

export type SheetConfigResponse = {
  last_invoice_no: string | null;
  service_code_products: { name: string; code: string }[];
};

export async function apiGetSheetConfig(): Promise<SheetConfigResponse> {
  return apiGet<SheetConfigResponse>("/invoice-uploads/sheet-config");
}

export type LineItemPreviewLineItem = {
  product_name: string;
  description: string;
  quantity: number;
  rate: number;
  amount: number;
  tax_amount: number;
  tax_code: string;
};

export type LineItemPreviewInvoice = {
  invoice_no: number;
  customer_display_name: string;
  line_items: LineItemPreviewLineItem[];
};

export type LineItemPreviewResponse = {
  last_invoice_no: string | null;
  invoice_date: string;
  due_date: string;
  memo: string;
  invoices: LineItemPreviewInvoice[];
};

export async function apiGetLineItemPreview(
  metric_columns: string[],
  rows: ValidatedRow[],
): Promise<LineItemPreviewResponse> {
  return apiPost<LineItemPreviewResponse>("/invoice-uploads/line-item-preview", { metric_columns, rows });
}

export type AuthToken = { access_token: string; token_type: string };

export type CurrentUser = {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "supervisor";
  is_active: boolean;
};
