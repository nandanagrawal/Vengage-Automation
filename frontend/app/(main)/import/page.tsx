"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  apiGenerateInvoices,
  apiGet,
  apiPreview,
  apiRevalidate,
  apiValidateInvoiceFile,
  type CustomerError,
  type GenerateRequest,
  type InvoiceUploadResult,
  type PreviewCustomer,
  type PreviewResponse,
  type UploadDetailResponse,
  type UploadHistoryRow,
  type ValidatedRow,
  type ValidationResponse,
} from "@/lib/api";
import { addJob, updateJob } from "@/lib/jobQueue";

// ── Shared helpers ────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    completed_with_errors: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    failed: "text-rose-400 bg-rose-500/10 border-rose-500/20",
    processing: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
  };
  const label: Record<string, string> = {
    completed: "Completed", completed_with_errors: "Partial",
    failed: "Failed", processing: "Processing",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-semibold uppercase tracking-wide ${map[status] ?? "text-slate-400 bg-white/[0.05] border-white/10"}`}>
      {label[status] ?? status}
    </span>
  );
}

function SendStatusDot({ status }: { status: string }) {
  if (status === "sent") return <span className="inline-flex items-center gap-1 text-emerald-400 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />Sent</span>;
  if (status === "failed") return <span className="inline-flex items-center gap-1 text-rose-400 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />Failed</span>;
  return <span className="inline-flex items-center gap-1 text-indigo-400 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-indigo-400 inline-block" />Created</span>;
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) +
    " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// ── Step indicator ────────────────────────────────────────────────────────────

const STEPS = ["Upload", "Validate", "Preview", "Done"] as const;

function StepBar({ active }: { active: 0 | 1 | 2 | 3 }) {
  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center">
          <div className={`flex items-center justify-center w-7 h-7 rounded-full border text-xs font-bold transition-colors ${i < active ? "bg-indigo-600 border-indigo-600 text-white" : i === active ? "bg-indigo-600/20 border-indigo-500 text-indigo-300" : "bg-white/[0.03] border-white/[0.1] text-slate-600"}`}>
            {i < active ? "✓" : i + 1}
          </div>
          <span className={`ml-1.5 text-xs font-medium ${i === active ? "text-white" : "text-slate-500"}`}>{label}</span>
          {i < STEPS.length - 1 && <div className={`mx-3 h-px w-8 ${i < active ? "bg-indigo-600" : "bg-white/[0.08]"}`} />}
        </div>
      ))}
    </div>
  );
}

// ── Stage: Upload ─────────────────────────────────────────────────────────────

function UploadStage({ onValidated }: { onValidated: (v: ValidationResponse, file: File) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File | null) => { if (f) { setFile(f); setError(null); } };
  const onDrop = (e: React.DragEvent) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0] ?? null); };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true); setError(null);
    try {
      const res = await apiValidateInvoiceFile(file);
      onValidated(res, file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="rounded-2xl border border-white/[0.07] p-6 space-y-5" style={{ background: "var(--bg-card)" }}>
      <div>
        <h2 className="text-sm font-semibold text-white">Upload spreadsheet</h2>
        <p className="text-[11px] text-slate-500 mt-1">Upload a .csv, .xlsx, or .xls file. We&apos;ll validate it before generating any invoices.</p>
      </div>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${dragging ? "border-indigo-400 bg-indigo-500/10" : file ? "border-emerald-500/50 bg-emerald-500/5" : "border-white/[0.1] hover:border-white/[0.2] bg-white/[0.02]"}`}
      >
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(e) => handleFile(e.target.files?.[0] ?? null)} />
        {file ? (
          <div className="flex flex-col items-center gap-2">
            <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <p className="text-sm text-emerald-400 font-medium">{file.name}</p>
            <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB · click to change</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <svg className="w-8 h-8 text-slate-600" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
            <p className="text-sm text-slate-400">Drag & drop or <span className="text-indigo-400 underline underline-offset-2">browse</span></p>
            <p className="text-xs text-slate-600">.csv, .xlsx, .xls — max 10 MB</p>
          </div>
        )}
      </div>
      {error && <p className="text-rose-400 text-sm rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-2.5">{error}</p>}
      <button type="submit" disabled={!file || loading} className="shimmer-btn px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50 flex items-center gap-2">
        {loading && <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" /></svg>}
        {loading ? "Validating…" : "Validate file"}
      </button>
    </form>
  );
}

// ── Stage: Errors (editable table) ────────────────────────────────────────────

function ErrorsStage({
  validation,
  onFixed,
  onBack,
}: {
  validation: ValidationResponse;
  onFixed: (v: ValidationResponse) => void;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<ValidatedRow[]>(() => validation.rows.map(r => ({ ...r, metrics: { ...r.metrics } })));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateCell = (rowIdx: number, field: "center_id" | "center_name" | "center_prefix", val: string) => {
    setRows(prev => prev.map((r, i) => i === rowIdx ? { ...r, [field]: val } : r));
  };
  const updateMetric = (rowIdx: number, col: string, val: string) => {
    setRows(prev => prev.map((r, i) => i === rowIdx ? { ...r, metrics: { ...r.metrics, [col]: parseFloat(val) || 0 } } : r));
  };

  const onRevalidate = async () => {
    setLoading(true); setError(null);
    try {
      const res = await apiRevalidate(validation.metric_columns, rows);
      if (!res.has_errors) {
        onFixed(res);
      } else {
        setRows(res.rows.map(r => ({ ...r, metrics: { ...r.metrics } })));
        onFixed(res); // pass back so parent can decide whether to stay or advance
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revalidation failed");
    } finally {
      setLoading(false);
    }
  };

  const errorCount = rows.filter(r => r.errors.length > 0).length;
  const cols = validation.metric_columns;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Fix validation errors</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">{errorCount} row{errorCount !== 1 ? "s" : ""} with errors — edit cells and re-validate.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onBack} className="px-4 py-2 rounded-xl text-slate-400 hover:text-white text-sm border border-white/[0.07] transition-colors">Back</button>
          <button type="button" onClick={() => void onRevalidate()} disabled={loading} className="shimmer-btn px-4 py-2 rounded-xl text-white text-sm font-semibold disabled:opacity-50 flex items-center gap-2">
            {loading && <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" /></svg>}
            {loading ? "Re-validating…" : "Re-validate"}
          </button>
        </div>
      </div>

      {error && <p className="text-rose-400 text-sm rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-2.5">{error}</p>}

      {/* Customer-level errors */}
      {validation.customer_errors.length > 0 && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 space-y-2">
          <p className="text-xs font-semibold text-rose-400 uppercase tracking-wide">Customer configuration issues</p>
          {validation.customer_errors.map((ce, i) => (
            <div key={i}>
              <p className="text-xs text-white font-medium">{ce.customer_display_name}</p>
              {ce.errors.map((e, j) => <p key={j} className="text-xs text-rose-300 ml-2">· {e}</p>)}
            </div>
          ))}
        </div>
      )}

      {/* Editable table */}
      <div className="rounded-xl border border-white/[0.07] overflow-auto">
        <table className="w-full text-xs min-w-max">
          <thead>
            <tr className="border-b border-white/[0.07] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-3 py-2.5 text-left sticky left-0 bg-[var(--bg-card)] z-10">#</th>
              <th className="px-3 py-2.5 text-left min-w-[140px]">Center ID</th>
              <th className="px-3 py-2.5 text-left min-w-[140px]">Center Name</th>
              <th className="px-3 py-2.5 text-left min-w-[120px]">Prefix</th>
              {cols.map(c => <th key={c} className="px-3 py-2.5 text-right min-w-[90px]">{c}</th>)}
              <th className="px-3 py-2.5 text-left min-w-[160px]">Customer</th>
              <th className="px-3 py-2.5 text-left">Errors</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {rows.map((row, i) => {
              const hasErr = row.errors.length > 0;
              return (
                <tr key={i} className={hasErr ? "bg-rose-500/5" : ""}>
                  <td className="px-3 py-1.5 text-slate-600 sticky left-0 bg-inherit">{row.row_index + 1}</td>
                  <td className="px-2 py-1">
                    <input value={row.center_id} onChange={e => updateCell(i, "center_id", e.target.value)}
                      className={`w-full bg-transparent border rounded px-2 py-1 text-white outline-none focus:border-indigo-500 transition-colors ${hasErr ? "border-rose-500/50" : "border-white/[0.1]"}`} />
                  </td>
                  <td className="px-2 py-1">
                    <input value={row.center_name} onChange={e => updateCell(i, "center_name", e.target.value)}
                      className="w-full bg-transparent border border-white/[0.1] rounded px-2 py-1 text-white outline-none focus:border-indigo-500 transition-colors" />
                  </td>
                  <td className="px-2 py-1">
                    <input value={row.center_prefix} onChange={e => updateCell(i, "center_prefix", e.target.value)}
                      className="w-full bg-transparent border border-white/[0.1] rounded px-2 py-1 text-white outline-none focus:border-indigo-500 transition-colors" />
                  </td>
                  {cols.map(c => (
                    <td key={c} className="px-2 py-1">
                      <input type="number" value={row.metrics[c] ?? 0} onChange={e => updateMetric(i, c, e.target.value)}
                        className="w-full bg-transparent border border-white/[0.1] rounded px-2 py-1 text-right text-slate-300 outline-none focus:border-indigo-500 transition-colors" />
                    </td>
                  ))}
                  <td className="px-3 py-1.5 text-slate-400">{row.customer_display_name ?? <span className="text-slate-600">—</span>}</td>
                  <td className="px-3 py-1.5">
                    {row.errors.length > 0
                      ? <span className="text-rose-400">{row.errors.join("; ")}</span>
                      : <span className="text-emerald-500">✓</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Stage: Preview (customer-grouped, editable) ───────────────────────────────

function PreviewStage({
  preview,
  validatedRows,
  onSubmit,
  onBack,
}: {
  preview: PreviewResponse;
  validatedRows: ValidatedRow[];
  onSubmit: (req: GenerateRequest) => void;
  onBack: () => void;
}) {
  // Editable rows — track dirty state
  const [rows, setRows] = useState<ValidatedRow[]>(() => validatedRows.map(r => ({ ...r, metrics: { ...r.metrics } })));
  const [isDirty, setIsDirty] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const cols = preview.metric_columns;

  const updateMetric = (centerIdLower: string, col: string, val: string) => {
    setRows(prev => prev.map(r =>
      r.center_id.toLowerCase() === centerIdLower
        ? { ...r, metrics: { ...r.metrics, [col]: parseFloat(val) || 0 } }
        : r
    ));
    setIsDirty(true);
  };

  const updatePrefix = (centerIdLower: string, val: string) => {
    setRows(prev => prev.map(r =>
      r.center_id.toLowerCase() === centerIdLower ? { ...r, center_prefix: val } : r
    ));
    setIsDirty(true);
  };

  const handleSubmitClick = () => {
    if (isDirty) { setShowConfirm(true); } else { onSubmit({ metric_columns: cols, rows }); }
  };

  const confirmSubmit = () => { setShowConfirm(false); onSubmit({ metric_columns: cols, rows }); };

  // row lookup by center_id lower
  const rowByCenterId = Object.fromEntries(rows.map(r => [r.center_id.toLowerCase(), r]));

  return (
    <div className="space-y-5">
      {/* Confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-white/[0.1] p-6 space-y-4 shadow-2xl" style={{ background: "var(--bg-deep)" }}>
            <h3 className="text-base font-bold text-white">Confirm changes</h3>
            <p className="text-sm text-slate-400">You&apos;ve edited values in the preview. These changes will be used when generating invoices. Are you sure?</p>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowConfirm(false)} className="px-4 py-2 rounded-xl text-slate-400 hover:text-white border border-white/[0.07] text-sm transition-colors">Cancel</button>
              <button type="button" onClick={confirmSubmit} className="shimmer-btn px-4 py-2 rounded-xl text-white text-sm font-semibold">Confirm & submit</button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white">Preview</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">{preview.customers.length} customer{preview.customers.length !== 1 ? "s" : ""} · review and submit.</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onBack} className="px-4 py-2 rounded-xl text-slate-400 hover:text-white text-sm border border-white/[0.07] transition-colors">Back</button>
          <button type="button" onClick={handleSubmitClick} className="shimmer-btn px-5 py-2.5 rounded-xl text-white text-sm font-semibold">
            {isDirty ? "Submit with changes" : "Submit invoices"}
          </button>
        </div>
      </div>

      {preview.warnings.length > 0 && (
        <ul className="space-y-1">
          {preview.warnings.map((w, i) => (
            <li key={i} className="text-xs text-amber-400/90 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">{w}</li>
          ))}
        </ul>
      )}

      {/* Per-customer sections */}
      <div className="space-y-4">
        {preview.customers.map((cust) => (
          <div key={cust.customer_id} className="rounded-2xl border border-white/[0.07] overflow-hidden" style={{ background: "var(--bg-card)" }}>
            {/* Customer header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-3">
                <div>
                  <span className="text-sm font-semibold text-white">{cust.display_name}</span>
                  <div className="flex items-center gap-2 mt-0.5">
                    {!cust.has_qbo_id && <span className="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.5 rounded">No QBO ID</span>}
                    {cust.primary_email
                      ? <span className="text-[10px] text-slate-500">{cust.primary_email}</span>
                      : <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded">No email</span>}
                  </div>
                </div>
              </div>
            </div>

            {/* Groups */}
            {cust.groups.map((grp, gi) => (
              <div key={gi} className={gi < cust.groups.length - 1 ? "border-b border-white/[0.05]" : ""}>
                <div className="px-5 py-2 bg-white/[0.02]">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Group: </span>
                  <span className="text-[11px] text-slate-400">{grp.group_label}</span>
                </div>
                <div className="overflow-auto">
                  <table className="w-full text-xs min-w-max">
                    <thead>
                      <tr className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 border-b border-white/[0.05]">
                        <th className="px-4 py-2 text-left">Center ID</th>
                        <th className="px-4 py-2 text-left">Prefix</th>
                        {cols.map(c => <th key={c} className="px-3 py-2 text-right min-w-[90px]">{c}</th>)}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.03]">
                      {grp.centers.map((ctr) => {
                        const row = rowByCenterId[ctr.center_id.toLowerCase()];
                        return (
                          <tr key={ctr.center_id}>
                            <td className="px-4 py-1.5 text-slate-300 font-mono text-[11px]">{ctr.center_id}</td>
                            <td className="px-3 py-1">
                              <input value={row?.center_prefix ?? ctr.center_prefix}
                                onChange={e => updatePrefix(ctr.center_id.toLowerCase(), e.target.value)}
                                className="w-24 bg-transparent border border-white/[0.1] rounded px-2 py-0.5 text-slate-300 outline-none focus:border-indigo-500 transition-colors text-[11px]" />
                            </td>
                            {cols.map(c => (
                              <td key={c} className="px-2 py-1">
                                <input type="number" value={row?.metrics[c] ?? ctr.metrics[c] ?? 0}
                                  onChange={e => updateMetric(ctr.center_id.toLowerCase(), c, e.target.value)}
                                  className="w-full bg-transparent border border-white/[0.1] rounded px-2 py-0.5 text-right text-slate-300 outline-none focus:border-indigo-500 transition-colors text-[11px]" />
                              </td>
                            ))}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stage: Result ─────────────────────────────────────────────────────────────

function ResultStage({ result, onReset }: { result: InvoiceUploadResult; onReset: () => void }) {
  return (
    <div className="rounded-2xl border border-white/[0.07] p-6 space-y-5" style={{ background: "var(--bg-card)" }}>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Result</h3>
        <StatusBadge status={result.status} />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {[
          { label: "Centers matched", value: result.centers_matched, color: "text-emerald-400" },
          { label: "Centers skipped", value: result.centers_skipped, color: result.centers_skipped > 0 ? "text-amber-400" : undefined },
          { label: "Invoices created", value: result.invoices_created, color: result.invoices_created > 0 ? "text-emerald-400" : undefined },
          { label: "Invoices failed", value: result.invoices_failed, color: result.invoices_failed > 0 ? "text-rose-400" : undefined },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3">
            <p className="text-[11px] text-slate-500 uppercase tracking-wide">{label}</p>
            <p className={`text-2xl font-bold mt-0.5 ${color ?? "text-white"}`}>{value}</p>
          </div>
        ))}
      </div>
      {result.invoice_details.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Invoices created</h4>
          <div className="rounded-xl border border-white/[0.07] overflow-hidden">
            <div className="grid grid-cols-[5rem_minmax(0,2fr)_minmax(0,2fr)_8rem_5rem] px-4 py-2.5 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              <span>Inv #</span><span>Customer</span><span>Group</span><span className="text-right">Delivery Date</span><span className="text-center">Status</span>
            </div>
            {result.invoice_details.map((d, i) => (
              <div key={i} className="grid grid-cols-[5rem_minmax(0,2fr)_minmax(0,2fr)_8rem_5rem] px-4 py-2.5 border-b border-white/[0.04] last:border-0 items-center">
                <span className="text-slate-400 text-xs font-mono truncate">{d.invoice_number ?? "—"}</span>
                <span className="text-white text-sm truncate pr-2">{d.customer}</span>
                <span className="text-slate-400 text-xs truncate pr-2">{d.group}</span>
                <span className="text-slate-300 text-xs text-right">{d.sent_at ? new Date(d.sent_at).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" }) : "—"}</span>
                <div className="flex justify-center"><SendStatusDot status={d.send_status} /></div>
              </div>
            ))}
          </div>
        </div>
      )}
      {result.errors.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Warnings / skipped ({result.errors.length})</h4>
          <ul className="space-y-1.5">
            {result.errors.map((e, i) => (
              <li key={i} className="text-xs text-amber-400/90 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">{e}</li>
            ))}
          </ul>
        </div>
      )}
      <button type="button" onClick={onReset} className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors underline underline-offset-2">
        Upload another file
      </button>
    </div>
  );
}

// ── History tab (unchanged) ───────────────────────────────────────────────────

function HistoryDetailModal({ uploadId, onClose }: { uploadId: number; onClose: () => void }) {
  const [data, setData] = useState<UploadDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiGet<UploadDetailResponse>(`/invoice-uploads/${uploadId}`)
      .then(setData).catch((e) => setError(e instanceof Error ? e.message : "Failed to load")).finally(() => setLoading(false));
  }, [uploadId]);

  return (
    <div className="fixed inset-x-0 top-16 z-30 flex items-start justify-center p-4 bg-black/70 backdrop-blur-sm overflow-hidden" style={{ height: "calc(100vh - 4rem)" }}>
      <div className="w-full max-w-4xl max-h-full rounded-2xl border border-white/[0.1] shadow-2xl flex flex-col overflow-hidden" style={{ background: "var(--bg-deep)" }}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] shrink-0">
          <div className="min-w-0">
            <h2 className="text-base font-bold text-white truncate">{data?.file_name ?? "Upload detail"}</h2>
            {data && <p className="text-xs text-slate-500 mt-0.5">{fmtDate(data.created_at)}{data.uploaded_by && <> · {data.uploaded_by}</>} · <StatusBadge status={data.status} /></p>}
          </div>
          <button type="button" onClick={onClose} className="ml-4 shrink-0 text-slate-400 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-6 space-y-4">
          {loading && <p className="text-slate-500 text-sm text-center py-8">Loading…</p>}
          {error && <p className="text-rose-400 text-sm">{error}</p>}
          {data && (
            <>
              {/* Stats */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: "Total", value: data.total_invoices ?? 0 },
                  { label: "Succeeded", value: data.success_count ?? 0, color: "text-emerald-400" },
                  { label: "Failed", value: data.failed_count ?? 0, color: (data.failed_count ?? 0) > 0 ? "text-rose-400" : undefined },
                ].map(({ label, value, color }) => (
                  <div key={label} className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3">
                    <p className="text-[11px] text-slate-500 uppercase tracking-wide">{label}</p>
                    <p className={`text-2xl font-bold mt-0.5 ${color ?? "text-white"}`}>{value}</p>
                  </div>
                ))}
                <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] px-4 py-3 flex items-center">
                  <StatusBadge status={data.status} />
                </div>
              </div>

              {/* Errors */}
              {data.errors.length > 0 && (
                <ul className="space-y-1.5">
                  {data.errors.map((e, i) => <li key={i} className="text-xs text-amber-400/90 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2">{e}</li>)}
                </ul>
              )}

              {/* Invoice table */}
              {data.generated_invoices.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Invoices Created</p>
                  <div className="rounded-xl border border-white/[0.07] overflow-hidden">
                    <div className="grid grid-cols-[5rem_minmax(0,2fr)_minmax(0,1.5fr)_8rem_6rem] px-4 py-2.5 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      <span>INV #</span><span>Customer</span><span>Group</span><span className="text-right">Delivery Date</span><span className="text-right">Status</span>
                    </div>
                    <div className="divide-y divide-white/[0.04]">
                      {data.generated_invoices.map((inv) => (
                        <div key={inv.id} className="grid grid-cols-[5rem_minmax(0,2fr)_minmax(0,1.5fr)_8rem_6rem] px-4 py-2.5 items-center">
                          <span className="text-slate-300 text-xs font-mono">{inv.invoice_number ?? "—"}</span>
                          <span className="text-white text-sm truncate pr-3">{inv.customer_name ?? "—"}</span>
                          <span className="text-slate-500 text-xs truncate pr-3">{inv.center_group_name}</span>
                          <span className="text-slate-300 text-xs text-right">
                            {inv.sent_at ? new Date(inv.sent_at).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" }) : "—"}
                          </span>
                          <div className="flex justify-end">
                            <SendStatusDot status={inv.send_status} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Stage =
  | { type: "upload" }
  | { type: "errors"; validation: ValidationResponse }
  | { type: "previewing"; validation: ValidationResponse }
  | { type: "preview"; preview: PreviewResponse; validatedRows: ValidatedRow[] }
  | { type: "submitting" }
  | { type: "processing"; uploadId: number }
  | { type: "done"; result: InvoiceUploadResult };

export default function ImportPage() {
  const [activeTab, setActiveTab] = useState<"generate" | "history">("generate");
  const [stage, setStage] = useState<Stage>({ type: "upload" });

  const [history, setHistory] = useState<UploadHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyDetailId, setHistoryDetailId] = useState<number | null>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true); setHistoryError(null);
    try { setHistory(await apiGet<UploadHistoryRow[]>("/invoice-uploads")); }
    catch (e) { setHistoryError(e instanceof Error ? e.message : "Failed to load history"); }
    finally { setHistoryLoading(false); }
  }, []);

  useEffect(() => { if (activeTab === "history") void loadHistory(); }, [activeTab, loadHistory]);

  // Step bar index
  const stepIndex: 0 | 1 | 2 | 3 =
    stage.type === "upload" ? 0 :
    stage.type === "errors" || stage.type === "previewing" ? 1 :
    stage.type === "preview" ? 2 : 3;

  const handleValidated = async (v: ValidationResponse) => {
    if (v.has_errors) {
      setStage({ type: "errors", validation: v });
    } else {
      await advanceToPreview(v);
    }
  };

  const handleFixed = async (v: ValidationResponse) => {
    if (v.has_errors) {
      setStage({ type: "errors", validation: v });
    } else {
      await advanceToPreview(v);
    }
  };

  const advanceToPreview = async (v: ValidationResponse) => {
    setStage({ type: "previewing", validation: v });
    try {
      const preview = await apiPreview(v.metric_columns, v.rows);
      setStage({ type: "preview", preview, validatedRows: v.rows });
    } catch (err) {
      setStage({ type: "errors", validation: { ...v, has_errors: true, customer_errors: [{ customer_display_name: "", errors: [err instanceof Error ? err.message : "Failed to load preview"] }] } });
    }
  };

  const handleSubmit = async (req: GenerateRequest) => {
    setStage({ type: "submitting" });
    try {
      const res = await apiGenerateInvoices(req);
      addJob(res.upload_id);
      setStage({ type: "processing", uploadId: res.upload_id });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Generation failed");
      setStage({ type: "upload" });
    }
  };

  // Poll the upload status while in processing stage
  useEffect(() => {
    if (stage.type !== "processing") return;
    const uploadId = stage.uploadId;
    const interval = setInterval(async () => {
      try {
        const detail = await apiGet<UploadDetailResponse>(`/invoice-uploads/${uploadId}`);
        if (detail.status !== "processing") {
          clearInterval(interval);
          updateJob(uploadId, detail.status as "completed" | "completed_with_errors" | "failed");
          // Convert UploadDetailResponse to InvoiceUploadResult shape
          const result: InvoiceUploadResult = {
            upload_id: detail.id,
            status: detail.status,
            total_center_rows: detail.total_invoices ?? 0,
            centers_matched: 0,
            centers_skipped: 0,
            invoices_created: detail.success_count ?? 0,
            invoices_failed: detail.failed_count ?? 0,
            invoice_details: detail.generated_invoices.map((inv) => ({
              customer: inv.customer_name ?? "",
              group: inv.center_group_name,
              qbo_invoice_id: inv.quickbooks_invoice_id ?? "",
              invoice_number: inv.invoice_number,
              sent_at: inv.sent_at,
              send_status: inv.send_status,
              sent: inv.send_status === "sent",
            })),
            errors: detail.errors,
          };
          setStage({ type: "done", result });
          void apiGet<UploadHistoryRow[]>("/invoice-uploads").then(setHistory).catch(() => undefined);
        }
      } catch {
        // keep polling on transient errors
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [stage]);

  return (
    <div className="max-w-5xl mx-auto animate-fadeInUp">
      {historyDetailId !== null && <HistoryDetailModal uploadId={historyDetailId} onClose={() => setHistoryDetailId(null)} />}

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Import</h1>
        <p className="text-slate-500 text-sm mt-1">Generate QBO invoices from spreadsheet uploads.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-xl border border-white/[0.07] w-fit" style={{ background: "var(--bg-card)" }}>
        {(["generate", "history"] as const).map(tab => (
          <button key={tab} type="button" onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-colors ${activeTab === tab ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-white"}`}>
            {tab === "generate" ? "Generate Invoice" : "Recent History"}
          </button>
        ))}
      </div>

      {activeTab === "generate" && (
        <div className="space-y-6">
          <StepBar active={stepIndex} />

          {stage.type === "upload" && <UploadStage onValidated={(v) => void handleValidated(v)} />}

          {stage.type === "errors" && (
            <ErrorsStage
              validation={stage.validation}
              onFixed={(v) => void handleFixed(v)}
              onBack={() => setStage({ type: "upload" })}
            />
          )}

          {stage.type === "previewing" && (
            <div className="text-center py-16 text-slate-500 text-sm flex flex-col items-center gap-3">
              <svg className="w-6 h-6 animate-spin text-indigo-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" /></svg>
              Building preview…
            </div>
          )}

          {stage.type === "preview" && (
            <PreviewStage
              preview={stage.preview}
              validatedRows={stage.validatedRows}
              onSubmit={(req) => void handleSubmit(req)}
              onBack={() => setStage({ type: "errors", validation: { metric_columns: stage.preview.metric_columns, rows: stage.validatedRows, customer_errors: [], has_errors: false } })}
            />
          )}

          {stage.type === "submitting" && (
            <div className="text-center py-16 text-slate-500 text-sm flex flex-col items-center gap-3">
              <svg className="w-6 h-6 animate-spin text-indigo-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" /></svg>
              Submitting…
            </div>
          )}

          {stage.type === "processing" && (
            <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-8 flex flex-col items-center gap-4 text-center">
              <div className="w-14 h-14 rounded-2xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center">
                <svg className="w-7 h-7 animate-spin text-indigo-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                </svg>
              </div>
              <div>
                <p className="text-white font-semibold text-lg">Processing in background</p>
                <p className="text-slate-400 text-sm mt-1">
                  Your invoices are being created and sent in QBO. This may take a minute.
                </p>
                <p className="text-slate-500 text-xs mt-2">
                  Job #{stage.uploadId} · Check the bell icon for updates
                </p>
              </div>
              <div className="flex items-center gap-1.5 text-indigo-400 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                Checking every 3 seconds…
              </div>
            </div>
          )}

          {stage.type === "done" && (
            <ResultStage result={stage.result} onReset={() => setStage({ type: "upload" })} />
          )}
        </div>
      )}

      {/* History tab */}
      {activeTab === "history" && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs text-slate-500">Last 50 uploads</p>
            <button type="button" onClick={() => void loadHistory()} disabled={historyLoading} className="text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-50 transition-colors flex items-center gap-1">
              {historyLoading && <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" /></svg>}
              Refresh
            </button>
          </div>
          {historyError && <p className="text-rose-400 text-sm mb-4">{historyError}</p>}
          <div className="rounded-2xl border border-white/[0.07] overflow-hidden" style={{ background: "var(--bg-card)" }}>
            <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_8rem_3.5rem_3.5rem_6rem_5rem] px-5 py-3 border-b border-white/[0.06] text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              <span>File</span><span>Uploaded by</span><span>Date</span><span className="text-center">Total</span><span className="text-center text-emerald-500">OK</span><span className="text-center text-rose-500">Failed</span><span className="text-center">Status</span>
            </div>
            {historyLoading && history.length === 0 ? <p className="text-slate-500 text-sm text-center py-10">Loading…</p>
              : history.length === 0 ? <p className="text-slate-500 text-sm text-center py-10">No uploads yet.</p>
              : (
                <ul className="divide-y divide-white/[0.04]">
                  {history.map(row => (
                    <li key={row.id} onClick={() => setHistoryDetailId(row.id)}
                      className="grid grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_8rem_3.5rem_3.5rem_6rem_5rem] px-5 py-3.5 items-center cursor-pointer hover:bg-white/[0.03] transition-colors">
                      <div className="flex items-center gap-2.5 min-w-0 pr-3">
                        <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                          <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
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
