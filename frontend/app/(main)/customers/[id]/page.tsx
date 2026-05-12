"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  apiGet,
  apiGetGeneratedInvoices,
  type CustomerRow,
  type GeneratedInvoiceItem,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function sendStatusStyle(s: string) {
  if (s === "sent") return { label: "Sent", cls: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20", dot: "bg-emerald-400" };
  if (s === "failed") return { label: "Failed", cls: "text-red-400 bg-red-400/10 border-red-400/20", dot: "bg-red-400" };
  return { label: "Pending", cls: "text-amber-400 bg-amber-400/10 border-amber-400/20", dot: "bg-amber-400" };
}

function statusStyle(s: string) {
  if (s === "approved") return { label: "Approved", cls: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20" };
  if (s === "rejected") return { label: "Rejected", cls: "text-red-400 bg-red-400/10 border-red-400/20" };
  return { label: "Pending", cls: "text-amber-400 bg-amber-400/10 border-amber-400/20" };
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtAmt(v: string) {
  return "$" + parseFloat(v).toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-0.5">{label}</p>
      <p className="text-sm text-slate-200">{value}</p>
    </div>
  );
}

function InfoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/[0.07] p-5" style={{ background: "rgba(255,255,255,0.02)" }}>
      <p className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-4">{title}</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">{children}</div>
    </div>
  );
}

// ── Info Tab ──────────────────────────────────────────────────────────────────

function InfoTab({ customer: c }: { customer: CustomerRow }) {
  const ss = statusStyle(c.status);
  return (
    <div className="space-y-4">
      <InfoSection title="Identity">
        <InfoField label="Display Name" value={c.display_name} />
        <InfoField label="Company" value={c.company_name} />
        <InfoField label="Given Name" value={[c.title, c.given_name, c.middle_name, c.family_name, c.suffix].filter(Boolean).join(" ")} />
        <InfoField label="Print On Check" value={c.print_on_check_name} />
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-0.5">Status</p>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${ss.cls}`}>{ss.label}</span>
        </div>
        <InfoField label="QBO ID" value={c.qbo_id} />
      </InfoSection>

      <InfoSection title="Contact">
        <InfoField label="Primary Email" value={c.primary_email} />
        <InfoField label="CC Email" value={c.cc_email} />
        <InfoField label="BCC Email" value={c.bcc_email} />
        <InfoField label="Phone" value={c.phone_number} />
        <InfoField label="Mobile" value={c.mobile} />
        <InfoField label="Fax" value={c.fax} />
        <InfoField label="Website" value={c.website} />
        <InfoField label="Other Contact" value={c.other_contact} />
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-0.5">Attachment in Mail</p>
          <span className={`text-sm font-semibold ${c.add_attachment_in_mail ? "text-emerald-400" : "text-slate-500"}`}>
            {c.add_attachment_in_mail ? "Yes" : "No"}
          </span>
        </div>
      </InfoSection>

      <InfoSection title="Billing Address">
        <InfoField label="Line 1" value={c.billing_line1} />
        <InfoField label="Line 2" value={c.billing_line2} />
        <InfoField label="City" value={c.billing_city} />
        <InfoField label="State" value={c.billing_state} />
        <InfoField label="ZIP" value={c.billing_zip} />
        <InfoField label="Country" value={c.billing_country} />
      </InfoSection>

      {!c.ship_same_as_billing && (
        <InfoSection title="Shipping Address">
          <InfoField label="Line 1" value={c.shipping_line1} />
          <InfoField label="Line 2" value={c.shipping_line2} />
          <InfoField label="City" value={c.shipping_city} />
          <InfoField label="State" value={c.shipping_state} />
          <InfoField label="ZIP" value={c.shipping_zip} />
          <InfoField label="Country" value={c.shipping_country} />
        </InfoSection>
      )}

      {c.notes && (
        <InfoSection title="Notes">
          <div className="col-span-full">
            <p className="text-sm text-slate-300 whitespace-pre-wrap">{c.notes}</p>
          </div>
        </InfoSection>
      )}

      <InfoSection title="Timestamps">
        <InfoField label="Created" value={fmt(c.created_at)} />
        <InfoField label="Updated" value={fmt(c.updated_at)} />
        <InfoField label="QBO Last Updated" value={c.qbo_last_updated ? fmt(c.qbo_last_updated) : null} />
        <InfoField label="Last Pushed to QBO" value={c.last_pushed_to_qbo_at ? fmt(c.last_pushed_to_qbo_at) : null} />
      </InfoSection>
    </div>
  );
}

// ── Invoices Tab ──────────────────────────────────────────────────────────────

function InvoicesTab({ customerId }: { customerId: number }) {
  const [items, setItems] = useState<GeneratedInvoiceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const load = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiGetGeneratedInvoices({ customer_id: customerId, limit: PAGE_SIZE, offset: (p - 1) * PAGE_SIZE });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load invoices");
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => { void load(page); }, [load, page]);

  const toggleExpand = (id: number) => {
    setExpanded((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (loading) return <div className="py-12 text-center text-slate-500 text-sm">Loading…</div>;
  if (error) return <p className="text-rose-400 text-sm">{error}</p>;
  if (items.length === 0) return <div className="py-12 text-center text-slate-500 text-sm">No invoices found for this customer.</div>;

  return (
    <div>
      <div className="rounded-2xl border border-white/[0.07] overflow-hidden" style={{ background: "var(--bg-card)" }}>
        <div className="grid grid-cols-[2rem_minmax(0,1.5fr)_7rem_6rem_6rem_2rem] px-5 py-3 border-b border-white/[0.06] max-md:hidden">
          {["", "Invoice #", "Amount", "Status", "Date", ""].map((h, i) => (
            <span key={i} className={`text-xs font-semibold uppercase tracking-wider text-slate-500 ${i >= 2 ? "text-right" : ""}`}>{h}</span>
          ))}
        </div>

        <div className="divide-y divide-white/[0.04]">
          {items.map((inv) => {
            const ss = sendStatusStyle(inv.send_status);
            const isExpanded = expanded.has(inv.id);
            return (
              <div key={inv.id}>
                <div
                  className="grid max-md:grid-cols-1 items-center px-5 py-3.5 hover:bg-white/[0.03] transition-colors cursor-pointer grid-cols-[2rem_minmax(0,1.5fr)_7rem_6rem_6rem_2rem]"
                  onClick={() => toggleExpand(inv.id)}
                >
                  <span className="text-slate-600 text-xs">{isExpanded ? "▾" : "▸"}</span>
                  <span className="text-slate-200 text-sm font-mono">
                    {inv.invoice_number ?? inv.quickbooks_invoice_id ?? "—"}
                  </span>
                  <span className="text-white text-sm font-semibold text-right">{fmtAmt(inv.total_amount)}</span>
                  <div className="flex justify-end">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${ss.cls}`}>
                      <span className={`w-1 h-1 rounded-full ${ss.dot}`} />
                      {ss.label}
                    </span>
                  </div>
                  <span className="text-slate-500 text-xs text-right">{fmt(inv.created_at)}</span>
                  <span />
                </div>
                {isExpanded && (
                  <div className="px-6 pb-4 pt-2 bg-white/[0.015] border-t border-white/[0.05]">
                    {inv.centers.length > 0 && (
                      <div className="mb-3">
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Centers</p>
                        <div className="flex flex-wrap gap-1.5">
                          {inv.centers.map((c) => (
                            <span key={c.id} className="px-2.5 py-0.5 rounded-full text-xs bg-white/[0.06] text-slate-300 border border-white/[0.08]">{c.center_name}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {inv.line_items.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Line Items</p>
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
                      <p className="mt-3 text-xs text-rose-400 bg-rose-500/10 rounded-lg px-3 py-2 border border-rose-500/20">{inv.error_message}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between">
            <span className="text-slate-600 text-xs">{total} invoice{total !== 1 ? "s" : ""}</span>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 transition-colors">‹</button>
              <span className="text-xs text-slate-500">{page} / {totalPages}</span>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 transition-colors">›</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "info" | "invoices";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const customerId = parseInt(params.id, 10);

  const [customer, setCustomer] = useState<CustomerRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("info");

  useEffect(() => {
    setLoading(true);
    apiGet<CustomerRow>(`/customers/${customerId}`)
      .then(setCustomer)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load customer"))
      .finally(() => setLoading(false));
  }, [customerId]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center text-slate-500 text-sm">Loading…</div>
    );
  }

  if (error || !customer) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <p className="text-rose-400 text-sm">{error ?? "Customer not found."}</p>
        <button onClick={() => router.push("/customers")} className="mt-4 text-indigo-400 text-sm hover:underline">← Back to Customers</button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto animate-fadeInUp">
      {/* Back */}
      <Link href="/customers" className="inline-flex items-center gap-1.5 text-slate-500 hover:text-slate-300 text-sm mb-5 transition-colors">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Customers
      </Link>

      {/* Customer header */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/30 to-violet-600/30 border border-indigo-500/30 flex items-center justify-center text-indigo-400 text-xl font-bold shrink-0">
          {customer.display_name[0]?.toUpperCase() ?? "?"}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">{customer.display_name}</h1>
          {customer.company_name && <p className="text-slate-400 text-sm">{customer.company_name}</p>}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-white/[0.03] rounded-xl p-1 w-fit border border-white/[0.06]">
        {(["info", "invoices"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all capitalize ${
              tab === t
                ? "bg-indigo-600 text-white shadow-lg"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "info" && <InfoTab customer={customer} />}
      {tab === "invoices" && <InvoicesTab customerId={customerId} />}
    </div>
  );
}
