"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGetGeneratedInvoices, type GeneratedInvoiceItem } from "@/lib/api";

const PAGE_SIZE = 25;

function sendStatusStyle(s: string) {
  if (s === "sent") return { label: "Sent", cls: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20", dot: "bg-emerald-400" };
  if (s === "failed") return { label: "Failed", cls: "text-red-400 bg-red-400/10 border-red-400/20", dot: "bg-red-400" };
  return { label: "Pending", cls: "text-amber-400 bg-amber-400/10 border-amber-400/20", dot: "bg-amber-400" };
}

function sourceStyle(s: string) {
  if (s === "quickbooks") return { label: "QuickBooks", cls: "text-sky-400 bg-sky-400/10 border-sky-400/20" };
  return { label: "Platform", cls: "text-indigo-400 bg-indigo-400/10 border-indigo-400/20" };
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtAmt(v: string) {
  return "$" + parseFloat(v).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ExpandedDetail({ inv }: { inv: GeneratedInvoiceItem }) {
  return (
    <div className="px-6 pb-5 pt-2 bg-white/[0.015] border-t border-white/[0.05]">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {inv.centers.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Centers</p>
            <div className="flex flex-wrap gap-1.5">
              {inv.centers.map((c) => (
                <span key={c.id} className="px-2.5 py-0.5 rounded-full text-xs bg-white/[0.06] text-slate-300 border border-white/[0.08]">
                  {c.center_name}
                </span>
              ))}
            </div>
          </div>
        )}
        {inv.line_items.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Line Items</p>
            <div className="rounded-xl overflow-hidden border border-white/[0.06]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left px-3 py-2 text-slate-500 font-semibold">Product</th>
                    <th className="text-right px-3 py-2 text-slate-500 font-semibold">Qty</th>
                    <th className="text-right px-3 py-2 text-slate-500 font-semibold">Rate</th>
                    <th className="text-right px-3 py-2 text-slate-500 font-semibold">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {inv.line_items.map((li) => (
                    <tr key={li.id}>
                      <td className="px-3 py-1.5 text-slate-300">{li.product_name}</td>
                      <td className="px-3 py-1.5 text-slate-400 text-right">{li.quantity}</td>
                      <td className="px-3 py-1.5 text-slate-400 text-right">{fmtAmt(li.rate)}</td>
                      <td className="px-3 py-1.5 text-slate-200 text-right font-medium">{fmtAmt(li.amount)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t border-white/[0.08]">
                  {(() => {
                    const subtotal = inv.line_items.reduce((s, li) => s + parseFloat(li.amount), 0);
                    const tax = subtotal * 0.1;
                    return (
                      <>
                        <tr>
                          <td colSpan={3} className="px-3 py-1.5 text-slate-500 text-right font-semibold">Subtotal</td>
                          <td className="px-3 py-1.5 text-slate-300 text-right font-semibold">{fmtAmt(subtotal.toFixed(2))}</td>
                        </tr>
                        <tr>
                          <td colSpan={3} className="px-3 py-1.5 text-slate-500 text-right font-semibold">GST (10%)</td>
                          <td className="px-3 py-1.5 text-slate-300 text-right font-semibold">{fmtAmt(tax.toFixed(2))}</td>
                        </tr>
                        <tr className="border-t border-white/[0.08]">
                          <td colSpan={3} className="px-3 py-2 text-white text-right font-bold">Total</td>
                          <td className="px-3 py-2 text-white text-right font-bold">{fmtAmt((subtotal + tax).toFixed(2))}</td>
                        </tr>
                      </>
                    );
                  })()}
                </tfoot>
              </table>
            </div>
          </div>
        )}
        {inv.error_message && (
          <div className="md:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-rose-500 mb-1">Error</p>
            <p className="text-xs text-rose-400 bg-rose-500/10 rounded-lg px-3 py-2 border border-rose-500/20">{inv.error_message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RecentInvoicesPage() {
  const [items, setItems] = useState<GeneratedInvoiceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiGetGeneratedInvoices({ limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(page); }, [load, page]);

  const toggleExpand = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const filtered = search.trim()
    ? items.filter((i) =>
        (i.customer_name ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (i.invoice_number ?? "").toLowerCase().includes(search.toLowerCase()) ||
        (i.quickbooks_invoice_id ?? "").includes(search)
      )
    : items;

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6 animate-fadeInUp">
        <h1 className="text-2xl font-bold text-white tracking-tight">Recent Invoices</h1>
        <p className="text-slate-500 text-sm mt-1">
          All invoices created via the platform or received from QuickBooks webhooks.
        </p>
      </div>

      {/* Search */}
      <div className="mb-4 animate-fadeInUp">
        <div className="relative max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" d="M21 21l-4.35-4.35" />
          </svg>
          <input type="text" placeholder="Search by customer, invoice #…" value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-8 py-2.5 rounded-xl border border-white/[0.09] bg-white/[0.04] text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white text-xs">✕</button>
          )}
        </div>
      </div>

      {error && <p className="text-rose-400 text-sm mb-4">{error}</p>}

      {/* Table */}
      <div className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp delay-100" style={{ background: "var(--bg-card)" }}>
        {/* Header */}
        <div className="grid grid-cols-[2rem_minmax(0,2fr)_minmax(0,1.5fr)_7rem_7rem_6rem_6rem_2rem] px-5 py-3 border-b border-white/[0.06] max-md:hidden">
          {["", "Customer", "Invoice #", "Group / Centers", "Amount", "Status", "Source", ""].map((h, i) => (
            <span key={i} className={`text-xs font-semibold uppercase tracking-wider text-slate-500 ${i >= 4 ? "text-right" : ""}`}>{h}</span>
          ))}
        </div>

        <div className="divide-y divide-white/[0.04]">
          {loading && (
            <div className="px-6 py-12 text-center text-slate-500 text-sm">Loading…</div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="px-6 py-12 text-center text-slate-500 text-sm">
              {search ? `No invoices match "${search}"` : "No invoices yet."}
            </div>
          )}
          {!loading && filtered.map((inv, i) => {
            const ss = sendStatusStyle(inv.send_status);
            const src = sourceStyle(inv.source);
            const isExpanded = expanded.has(inv.id);
            return (
              <div key={inv.id} className="animate-fadeInLeft" style={{ animationDelay: `${0.02 * i}s` }}>
                <div
                  className="grid max-md:grid-cols-1 items-center px-5 py-3.5 hover:bg-white/[0.03] transition-colors cursor-pointer grid-cols-[2rem_minmax(0,2fr)_minmax(0,1.5fr)_7rem_7rem_6rem_6rem_2rem]"
                  onClick={() => toggleExpand(inv.id)}
                >
                  {/* Expand icon */}
                  <span className="text-slate-600 text-xs">{isExpanded ? "▾" : "▸"}</span>

                  {/* Customer */}
                  <div className="flex items-center gap-2.5 min-w-0 pr-3">
                    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                      {(inv.customer_name ?? "?")[0]?.toUpperCase()}
                    </div>
                    <span className="text-white text-sm font-medium truncate">{inv.customer_name ?? "—"}</span>
                  </div>

                  {/* Invoice # */}
                  <div className="min-w-0 pr-3">
                    <span className="text-slate-300 text-sm font-mono">
                      {inv.invoice_number ?? inv.quickbooks_invoice_id ?? "—"}
                    </span>
                  </div>

                  {/* Group */}
                  <span className="text-slate-500 text-xs truncate pr-2">{inv.center_group_name}</span>

                  {/* Amount */}
                  <span className="text-white text-sm font-semibold text-right">{fmtAmt(inv.total_amount)}</span>

                  {/* Status */}
                  <div className="flex justify-end">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border ${ss.cls}`}>
                      <span className={`w-1 h-1 rounded-full ${ss.dot}`} />
                      {ss.label}
                    </span>
                  </div>

                  {/* Source */}
                  <div className="flex justify-end">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${src.cls}`}>
                      {src.label}
                    </span>
                  </div>

                  {/* Date */}
                  <span className="text-slate-600 text-xs text-right">{fmt(inv.created_at)}</span>
                </div>

                {isExpanded && <ExpandedDetail inv={inv} />}
              </div>
            );
          })}
        </div>

        {/* Pagination */}
        <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between gap-3">
          <span className="text-slate-600 text-xs">{total} invoice{total !== 1 ? "s" : ""} total</span>
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 transition-colors">‹</button>
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                  if (idx > 0 && typeof arr[idx - 1] === "number" && (p as number) - (arr[idx - 1] as number) > 1) acc.push("…");
                  acc.push(p); return acc;
                }, [])
                .map((p, idx) => p === "…"
                  ? <span key={`e-${idx}`} className="px-1 text-xs text-slate-700">…</span>
                  : <button key={p} onClick={() => setPage(p as number)}
                      className={`w-7 h-7 rounded-lg text-xs font-semibold transition-colors ${page === p ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white hover:bg-white/[0.06]"}`}>
                      {p}
                    </button>
                )}
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 transition-colors">›</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
