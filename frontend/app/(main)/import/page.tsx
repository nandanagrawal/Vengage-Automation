"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  apiGet,
  apiUploadInvoiceFile,
  type GeneratedInvoiceRow,
  type InvoiceUploadResult,
  type UploadDetailResponse,
  type UploadHistoryRow,
} from "@/lib/api";

// ── Status helpers ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    completed_with_errors: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    failed: "text-rose-400 bg-rose-500/10 border-rose-500/20",
    processing: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  };
  const label: Record<string, string> = {
    completed: "Completed",
    completed_with_errors: "Partial",
    failed: "Failed",
    processing: "Processing",
  };
  const cls = map[status] ?? "text-slate-400 bg-white/[0.05] border-white/10";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-semibold uppercase tracking-wide ${cls}`}>
      {label[status] ?? status}
    </span>
  );
}

function SendStatusDot({ status }: { status: string }) {
  if (status === "sent")
    return <span className="inline-flex items-center gap-1 text-emerald-400 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />Sent</span>;
  if (status === "failed")
    return <span className="inline-flex items-center gap-1 text-rose-400 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />Failed</span>;
  return <span className="inline-flex items-center gap-1 text-slate-400 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-slate-500 inline-block" />Pending</span>;
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) +
    " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// ── Detail modal ──────────────────────────────────────────────────────────────

function UploadDetailModal({
  uploadId,
  onClose,
}: {
  uploadId: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<UploadDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    void apiGet<UploadDetailResponse>(`/invoice-uploads/${uploadId}`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [uploadId]);

  return (
    <div className="fixed inset-x-0 bottom-0 top-16 z-30 flex items-start justify-center p-4 bg-black/70 backdrop-blur-sm overflow-hidden">
      <div
        className="w-full max-w-4xl max-h-full rounded-2xl border border-white/[0.1] shadow-2xl flex flex-col"
        style={{ background: "var(--bg-deep)" }}
      >
        {/* Header — stays pinned */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] shrink-0">
          <div>
            <h2 className="text-base font-bold text-white">{data?.file_name ?? "Upload detail"}</h2>
            {data && (
              <p className="text-xs text-slate-500 mt-0.5">
                {fmtDate(data.created_at)}
                {data.uploaded_by && <> · {data.uploaded_by}</>}
                {" · "}<StatusBadge status={data.status} />
              </p>
            )}
          </div>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body — scrolls inside the modal */}
        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          {loading && <p className="text-slate-500 text-sm text-center py-8">Loading…</p>}
          {error && <p className="text-rose-400 text-sm">{error}</p>}

          {data && (
            <>
              {/* Stats row */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Total Invoices", value: data.total_invoices ?? 0 },
                  { label: "Succeeded", value: data.success_count ?? 0, color: "text-emerald-400" },
                  { label: "Failed", value: data.failed_count ?? 0, color: (data.failed_count ?? 0) > 0 ? "text-rose-400" : undefined },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3">
                    <p className="text-[11px] text-slate-500 uppercase tracking-wide">{label}</p>
                    <p className={`text-2xl font-bold mt-0.5 ${color ?? "text-white"}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* Generated invoices table */}
              {data.generated_invoices.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Generated Invoices</h3>
                  <div className="rounded-xl border border-white/[0.07] overflow-hidden">
                    {/* Table header */}
                    <div className="grid grid-cols-[5rem_minmax(0,1.5fr)_minmax(0,2fr)_5rem_5rem] px-4 py-2.5 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      <span>Inv #</span>
                      <span>Customer</span>
                      <span>Center Group</span>
                      <span className="text-right">Amount</span>
                      <span className="text-center">Status</span>
                    </div>

                    {data.generated_invoices.map((gi) => (
                      <InvoiceDetailRow
                        key={gi.id}
                        gi={gi}
                        expanded={expandedId === gi.id}
                        onToggle={() => setExpandedId(expandedId === gi.id ? null : gi.id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Errors / warnings */}
              {data.errors.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
                    Warnings / errors ({data.errors.length})
                  </h3>
                  <ul className="space-y-1.5">
                    {data.errors.map((e, i) => (
                      <li key={i} className="text-xs text-amber-400/90 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">
                        {e}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {data.generated_invoices.length === 0 && data.errors.length === 0 && (
                <p className="text-slate-500 text-sm text-center py-4">No invoices were generated.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function InvoiceDetailRow({
  gi,
  expanded,
  onToggle,
}: {
  gi: GeneratedInvoiceRow;
  expanded: boolean;
  onToggle: () => void;
}) {
  const hasLineItems = gi.line_items.length > 0;
  return (
    <>
      <div
        className={`grid grid-cols-[5rem_minmax(0,1.5fr)_minmax(0,2fr)_5rem_5rem] px-4 py-2.5 border-b border-white/[0.04] items-center transition-colors ${hasLineItems ? "cursor-pointer hover:bg-white/[0.03]" : ""}`}
        onClick={hasLineItems ? onToggle : undefined}
      >
        <span className="text-slate-400 text-xs font-mono truncate" title={gi.invoice_number ?? undefined}>
          {gi.invoice_number ?? <span className="text-slate-600">—</span>}
        </span>
        <span className="text-white text-sm truncate pr-2">{gi.customer_name ?? <span className="text-slate-600">—</span>}</span>
        <div className="min-w-0 pr-2">
          <p className="text-slate-300 text-xs truncate">{gi.center_group_name}</p>
          {gi.centers.length > 0 && (
            <p className="text-slate-600 text-[10px] truncate">{gi.centers.map((c) => c.center_name).join(", ")}</p>
          )}
        </div>
        <span className="text-slate-300 text-sm text-right">${parseFloat(gi.total_amount).toFixed(2)}</span>
        <div className="flex justify-center">
          <SendStatusDot status={gi.send_status} />
        </div>
      </div>

      {/* Expanded line items */}
      {expanded && gi.line_items.length > 0 && (
        <div className="border-b border-white/[0.04] bg-white/[0.02] px-6 pb-3">
          {gi.error_message && (
            <p className="text-xs text-rose-400 mb-2 pt-2">{gi.error_message}</p>
          )}
          <table className="w-full text-xs mt-2">
            <thead>
              <tr className="text-slate-500 uppercase tracking-wide text-[10px]">
                <th className="text-left pb-1 font-semibold">Product</th>
                <th className="text-right pb-1 font-semibold">Qty</th>
                <th className="text-right pb-1 font-semibold">Rate</th>
                <th className="text-right pb-1 font-semibold">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {gi.line_items.map((li) => (
                <tr key={li.id}>
                  <td className="py-1 text-slate-300">{li.product_name}</td>
                  <td className="py-1 text-right text-slate-400">{parseFloat(li.quantity).toLocaleString()}</td>
                  <td className="py-1 text-right text-slate-400">${parseFloat(li.rate).toFixed(2)}</td>
                  <td className="py-1 text-right text-slate-300 font-medium">${parseFloat(li.amount).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ── History detail modal ──────────────────────────────────────────────────────

function HistoryDetailModal({
  uploadId,
  onClose,
}: {
  uploadId: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<UploadDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    void apiGet<UploadDetailResponse>(`/invoice-uploads/${uploadId}`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [uploadId]);

  return (
    <div className="fixed inset-x-0 top-16 z-30 flex items-start justify-center p-4 bg-black/70 backdrop-blur-sm overflow-hidden" style={{ height: "calc(100vh - 4rem)" }}>
      <div
        className="w-full max-w-4xl max-h-full rounded-2xl border border-white/[0.1] shadow-2xl flex flex-col overflow-hidden"
        style={{ background: "var(--bg-deep)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-bold text-white truncate">{data?.file_name ?? "Upload detail"}</h2>
              {data && (
                <p className="text-xs text-slate-500 mt-0.5">
                  {fmtDate(data.created_at)}
                  {data.uploaded_by && <> · {data.uploaded_by}</>}
                  {" · "}<StatusBadge status={data.status} />
                </p>
              )}
            </div>
          </div>
          <button type="button" onClick={onClose} className="ml-4 shrink-0 text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          {loading && <p className="text-slate-500 text-sm text-center py-8">Loading…</p>}
          {error && <p className="text-rose-400 text-sm">{error}</p>}

          {data && (
            <>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Total Invoices", value: data.total_invoices ?? 0 },
                  { label: "Succeeded", value: data.success_count ?? 0, color: "text-emerald-400" },
                  { label: "Failed", value: data.failed_count ?? 0, color: (data.failed_count ?? 0) > 0 ? "text-rose-400" : undefined },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3">
                    <p className="text-[11px] text-slate-500 uppercase tracking-wide">{label}</p>
                    <p className={`text-2xl font-bold mt-0.5 ${color ?? "text-white"}`}>{value}</p>
                  </div>
                ))}
              </div>

              {data.generated_invoices.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Generated Invoices</h3>
                  <div className="rounded-xl border border-white/[0.07] overflow-hidden">
                    <div className="grid grid-cols-[5rem_minmax(0,1.5fr)_minmax(0,2fr)_5rem_5rem] px-4 py-2.5 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      <span>Inv #</span>
                      <span>Customer</span>
                      <span>Center Group</span>
                      <span className="text-right">Amount</span>
                      <span className="text-center">Status</span>
                    </div>
                    {data.generated_invoices.map((gi) => (
                      <InvoiceDetailRow
                        key={gi.id}
                        gi={gi}
                        expanded={expandedId === gi.id}
                        onToggle={() => setExpandedId(expandedId === gi.id ? null : gi.id)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {data.errors.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
                    Warnings / errors ({data.errors.length})
                  </h3>
                  <ul className="space-y-1.5">
                    {data.errors.map((e, i) => (
                      <li key={i} className="text-xs text-amber-400/90 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">
                        {e}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {data.generated_invoices.length === 0 && data.errors.length === 0 && (
                <p className="text-slate-500 text-sm text-center py-4">No invoices were generated.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ImportPage() {
  const [activeTab, setActiveTab] = useState<"generate" | "history">("generate");

  // Generate tab state
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<InvoiceUploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // History tab state
  const [history, setHistory] = useState<UploadHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyDetailId, setHistoryDetailId] = useState<number | null>(null);
  // Generate tab "view full detail" modal
  const [generateDetailId, setGenerateDetailId] = useState<number | null>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      setHistory(await apiGet<UploadHistoryRow[]>("/invoice-uploads"));
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : "Failed to load history");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "history") void loadHistory();
  }, [activeTab, loadHistory]);

  const handleFile = (f: File | null) => {
    if (f) {
      setFile(f);
      setUploadResult(null);
      setUploadError(null);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0] ?? null);
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const res = await apiUploadInvoiceFile(file);
      setUploadResult(res);
      // Refresh history so new entry appears when user switches tab
      void apiGet<UploadHistoryRow[]>("/invoice-uploads")
        .then(setHistory)
        .catch(() => undefined);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto animate-fadeInUp">
      {/* Post-upload detail modal (Generate tab) */}
      {generateDetailId !== null && (
        <UploadDetailModal uploadId={generateDetailId} onClose={() => setGenerateDetailId(null)} />
      )}
      {/* History row detail modal */}
      {historyDetailId !== null && (
        <HistoryDetailModal uploadId={historyDetailId} onClose={() => setHistoryDetailId(null)} />
      )}

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Import</h1>
        <p className="text-slate-500 text-sm mt-1">Generate QBO invoices from spreadsheet uploads.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-xl border border-white/[0.07] w-fit" style={{ background: "var(--bg-card)" }}>
        {(["generate", "history"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-colors ${
              activeTab === tab ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-white"
            }`}
          >
            {tab === "generate" ? "Generate Invoice" : "Recent History"}
          </button>
        ))}
      </div>

      {/* ── Generate Invoice tab ── */}
      {activeTab === "generate" && (
        <div className="space-y-6">
          <form
            onSubmit={(e) => void onSubmit(e)}
            className="rounded-2xl border border-white/[0.07] p-6 space-y-5"
            style={{ background: "var(--bg-card)" }}
          >
            <div>
              <h2 className="text-sm font-semibold text-white">Generate invoices from file</h2>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Upload a <span className="text-slate-400">.csv</span>, <span className="text-slate-400">.xlsx</span>, or <span className="text-slate-400">.xls</span> file.
                First column = center names (case-sensitive). Remaining columns = product/service names.
                Invoices are created in QuickBooks and emailed automatically.
              </p>
            </div>

            {/* Drop zone */}
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
                dragging
                  ? "border-indigo-400 bg-indigo-500/10"
                  : file
                  ? "border-emerald-500/50 bg-emerald-500/5"
                  : "border-white/[0.1] hover:border-white/[0.2] bg-white/[0.02]"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
              />
              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-sm text-emerald-400 font-medium">{file.name}</p>
                  <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB · click to change</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <svg className="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                  </svg>
                  <p className="text-sm text-slate-400">Drag & drop or <span className="text-indigo-400 underline underline-offset-2">browse</span></p>
                  <p className="text-xs text-slate-600">.csv, .xlsx, .xls — max 10 MB</p>
                </div>
              )}
            </div>

            {uploadError && (
              <p className="text-rose-400 text-sm rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-2.5">{uploadError}</p>
            )}

            <button
              type="submit"
              disabled={!file || uploading}
              className="shimmer-btn px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50 flex items-center gap-2"
            >
              {uploading && (
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                </svg>
              )}
              {uploading ? "Generating invoices…" : "Generate & send invoices"}
            </button>
          </form>

          {/* Result panel */}
          {uploadResult && (
            <div className="rounded-2xl border border-white/[0.07] p-6 space-y-5" style={{ background: "var(--bg-card)" }}>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">Result</h3>
                <StatusBadge status={uploadResult.status} />
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {[
                  { label: "Center rows", value: uploadResult.total_center_rows },
                  { label: "Centers matched", value: uploadResult.centers_matched, color: "text-emerald-400" },
                  { label: "Centers skipped", value: uploadResult.centers_skipped, color: uploadResult.centers_skipped > 0 ? "text-amber-400" : undefined },
                  { label: "Invoices created", value: uploadResult.invoices_created, color: uploadResult.invoices_created > 0 ? "text-emerald-400" : undefined },
                  { label: "Invoices failed", value: uploadResult.invoices_failed, color: uploadResult.invoices_failed > 0 ? "text-rose-400" : undefined },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3">
                    <p className="text-[11px] text-slate-500 uppercase tracking-wide">{label}</p>
                    <p className={`text-2xl font-bold mt-0.5 ${color ?? "text-white"}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* Created invoices */}
              {uploadResult.invoice_details.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Invoices created</h4>
                  <div className="rounded-xl border border-white/[0.07] overflow-hidden">
                    <div className="grid grid-cols-[5rem_minmax(0,2fr)_minmax(0,2fr)_5rem_5rem] px-4 py-2.5 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      <span>Inv #</span><span>Customer</span><span>Group</span><span className="text-right">Amount</span><span className="text-center">Status</span>
                    </div>
                    {uploadResult.invoice_details.map((d, i) => (
                      <div key={i} className="grid grid-cols-[5rem_minmax(0,2fr)_minmax(0,2fr)_5rem_5rem] px-4 py-2.5 border-b border-white/[0.04] last:border-0 items-center">
                        <span className="text-slate-400 text-xs font-mono truncate">{d.invoice_number ?? "—"}</span>
                        <span className="text-white text-sm truncate pr-2">{d.customer}</span>
                        <span className="text-slate-400 text-xs truncate pr-2">{d.group}</span>
                        <span className="text-slate-300 text-sm text-right">${d.total_amount.toFixed(2)}</span>
                        <div className="flex justify-center"><SendStatusDot status={d.send_status} /></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Errors */}
              {uploadResult.errors.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
                    Warnings / skipped ({uploadResult.errors.length})
                  </h4>
                  <ul className="space-y-1.5">
                    {uploadResult.errors.map((e, i) => (
                      <li key={i} className="text-xs text-amber-400/90 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">
                        {e}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                type="button"
                onClick={() => setGenerateDetailId(uploadResult.upload_id)}
                className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors underline underline-offset-2"
              >
                View full detail
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Recent History tab ── */}
      {activeTab === "history" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs text-slate-500">Last 50 uploads</p>
            <button
              type="button"
              onClick={() => void loadHistory()}
              disabled={historyLoading}
              className="text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              {historyLoading && (
                <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                </svg>
              )}
              Refresh
            </button>
          </div>

          {historyError && <p className="text-rose-400 text-sm mb-4">{historyError}</p>}

          <div className="rounded-2xl border border-white/[0.07] overflow-hidden" style={{ background: "var(--bg-card)" }}>
            {/* Header */}
            <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_8rem_3.5rem_3.5rem_6rem_5rem] px-5 py-3 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              <span>File</span>
              <span>Uploaded by</span>
              <span>Date</span>
              <span className="text-center">Total</span>
              <span className="text-center text-emerald-500">OK</span>
              <span className="text-center text-rose-500">Failed</span>
              <span className="text-center">Status</span>
            </div>

            {historyLoading && history.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-10">Loading…</p>
            ) : history.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-10">No uploads yet.</p>
            ) : (
              <ul className="divide-y divide-white/[0.04]">
                {history.map((row) => (
                  <li
                    key={row.id}
                    onClick={() => setHistoryDetailId(row.id)}
                    className="grid grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_8rem_3.5rem_3.5rem_6rem_5rem] px-5 py-3.5 items-center cursor-pointer hover:bg-white/[0.03] transition-colors"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-3">
                      <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                        <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <span className="text-white text-sm truncate">{row.file_name}</span>
                    </div>
                    <span className="text-slate-400 text-xs truncate pr-3">{row.uploaded_by ?? "—"}</span>
                    <span className="text-slate-500 text-xs">{fmtDate(row.created_at)}</span>
                    <span className="text-slate-300 text-sm font-medium text-center">{row.total_invoices ?? "—"}</span>
                    <span className="text-emerald-400 text-sm font-medium text-center">{row.success_count ?? "—"}</span>
                    <span className={`text-sm font-medium text-center ${(row.failed_count ?? 0) > 0 ? "text-rose-400" : "text-slate-600"}`}>{row.failed_count ?? "—"}</span>
                    <div className="flex justify-center"><StatusBadge status={row.status} /></div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
