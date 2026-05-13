"use client";

import { useEffect, useState } from "react";
import { apiGet, type DashboardStats, type RecentInvoiceRow } from "@/lib/api";
import { ToastContainer, useToast } from "@/app/components/Toast";

function emailStatusLabel(status: string) {
  if (status === "EmailSent" || status === "sent") return "Sent";
  if (status === "NeedToSend") return "Queued";
  return "Created";
}

function emailStatusStyle(status: string) {
  if (status === "EmailSent" || status === "sent")
    return { dot: "bg-emerald-400", text: "text-emerald-400" };
  if (status === "NeedToSend")
    return { dot: "bg-amber-400", text: "text-amber-400" };
  return { dot: "bg-indigo-400", text: "text-indigo-400" };
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch {
    return "—";
  }
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin text-slate-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9" />
    </svg>
  );
}

type StatCardProps = {
  label: string;
  value: number | null;
  loading: boolean;
  icon: React.ReactNode;
  gradient: string;
  sub?: string;
};

function StatCard({ label, value, loading, icon, gradient, sub }: StatCardProps) {
  return (
    <div
      className="rounded-2xl border border-white/[0.07] p-5 hover:border-white/[0.14] hover:-translate-y-0.5 transition-all duration-200 card-glow"
      style={{ background: "var(--bg-card)" }}
    >
      <div className="flex items-center justify-between mb-4">
        <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white shrink-0`}>
          {icon}
        </div>
      </div>
      <div className="flex items-end gap-2 mb-0.5">
        {loading ? (
          <div className="flex items-center gap-2 h-9">
            <Spinner />
            <span className="text-slate-600 text-sm">Loading…</span>
          </div>
        ) : (
          <p className="text-3xl font-extrabold text-white tracking-tight">
            {value?.toLocaleString() ?? "—"}
          </p>
        )}
      </div>
      <p className="text-slate-500 text-xs mt-0.5">{label}</p>
      {sub && !loading && <p className="text-slate-700 text-[10px] mt-1">{sub}</p>}
    </div>
  );
}

const COLS = "grid-cols-[5rem_minmax(0,2fr)_minmax(0,2fr)_9rem_7rem_minmax(0,1.5fr)]";

export default function DashboardPage() {
  const { toasts, push: pushToast, dismiss: dismissToast } = useToast();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const [invoices, setInvoices] = useState<RecentInvoiceRow[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const s = await apiGet<DashboardStats>("/dashboard/stats");
        if (!cancelled) setStats(s);
      } catch (e) {
        if (!cancelled) pushToast(e instanceof Error ? e.message : "Could not load stats");
      } finally {
        if (!cancelled) setStatsLoading(false);
      }
    })();

    (async () => {
      try {
        const rows = await apiGet<RecentInvoiceRow[]>("/dashboard/recent-invoices");
        if (!cancelled) setInvoices(rows);
      } catch (e) {
        if (!cancelled) pushToast(e instanceof Error ? e.message : "Could not load invoices");
      } finally {
        if (!cancelled) setInvoicesLoading(false);
      }
    })();

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const statCards: StatCardProps[] = [
    {
      label: "Total Customers",
      value: stats?.total_customers ?? null,
      loading: statsLoading,
      sub: stats ? `${stats.approved_customers} approved · ${stats.pending_customers} pending` : undefined,
      gradient: "from-blue-500 to-indigo-600",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
        </svg>
      ),
    },
    {
      label: "Imports Today",
      value: stats?.imports_today ?? null,
      loading: statsLoading,
      sub: "Invoice file uploads since midnight (UTC)",
      gradient: "from-violet-500 to-purple-600",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
      ),
    },
    {
      label: "Invoices Sent",
      value: stats?.invoices_sent ?? null,
      loading: statsLoading,
      sub: "EmailSent — last 30-day QBO sync window",
      gradient: "from-emerald-400 to-teal-500",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      label: "Delivery Failures",
      value: stats?.delivery_failures ?? null,
      loading: statsLoading,
      sub: "NeedToSend — queued but not yet delivered",
      gradient: "from-rose-500 to-red-600",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
  ];

  const headers = ["INV #", "CUSTOMER", "GROUP", "DELIVERY DATE", "STATUS", "FILE NAME"];

  return (
    <div className="max-w-6xl mx-auto">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      <div className="mb-8 animate-fadeInUp">
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">
          Live snapshot of your account. Activity refreshes when you run Sync on Customers.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {statCards.map((card, i) => (
          <div key={card.label} className="animate-scaleIn" style={{ animationDelay: `${i * 0.06}s` }}>
            <StatCard {...card} />
          </div>
        ))}
      </div>

      {/* Invoices Created table */}
      <div
        className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp"
        style={{ background: "var(--bg-card)", animationDelay: "0.25s" }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-white font-semibold text-sm tracking-wide uppercase">Invoices Created</h2>
          <span className="text-[11px] text-slate-600">Last 50 · newest first</span>
        </div>

        {/* Header row */}
        <div className={`grid ${COLS} px-5 py-2.5 border-b border-white/[0.05] max-md:hidden`}>
          {headers.map((h) => (
            <span key={h} className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{h}</span>
          ))}
        </div>

        {invoicesLoading && (
          <div className="px-6 py-10 flex items-center justify-center gap-2 text-slate-600 text-sm">
            <Spinner /> Loading…
          </div>
        )}

        {!invoicesLoading && invoices.length === 0 && (
          <div className="px-6 py-10 text-center text-slate-600 text-sm">
            No invoices yet — upload a file in Import to generate invoices.
          </div>
        )}

        {!invoicesLoading && invoices.length > 0 && (
          <div className="divide-y divide-white/[0.04]">
            {invoices.map((row) => {
              const style = emailStatusStyle(row.send_status);
              return (
                <div
                  key={row.id}
                  className={`grid ${COLS} px-5 py-3 items-center hover:bg-white/[0.03] transition-colors max-md:flex max-md:flex-col max-md:gap-1 max-md:py-3`}
                >
                  {/* INV # */}
                  <span className="text-slate-400 text-xs font-mono">{row.invoice_number ?? "—"}</span>

                  {/* CUSTOMER */}
                  <span className="text-white text-sm truncate">{row.customer_name ?? "—"}</span>

                  {/* GROUP */}
                  <span className="text-indigo-300/80 text-xs truncate">{row.group}</span>

                  {/* DELIVERY DATE */}
                  <span className="text-slate-400 text-xs tabular-nums">{formatDate(row.sent_at)}</span>

                  {/* STATUS */}
                  <span className={`flex items-center gap-1.5 text-xs font-medium ${style.text}`}>
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${style.dot}`} />
                    {emailStatusLabel(row.send_status)}
                  </span>

                  {/* FILE NAME */}
                  <span className="text-slate-500 text-xs truncate">{row.file_name ?? "—"}</span>
                </div>
              );
            })}
          </div>
        )}

        {!invoicesLoading && invoices.length > 0 && (
          <div className="px-6 py-3 border-t border-white/[0.06]">
            <span className="text-slate-600 text-xs">{invoices.length} invoice{invoices.length !== 1 ? "s" : ""}</span>
          </div>
        )}
      </div>
    </div>
  );
}
