"use client";

import { useEffect, useState } from "react";
import { apiGet, type DashboardStats, type InvoiceActivityRow } from "@/lib/api";
import { ToastContainer, useToast } from "@/app/components/Toast";

// ── Helpers ───────────────────────────────────────────────────────────────────

function emailStatusLabel(status: string) {
  if (status === "EmailSent") return "Sent";
  if (status === "NeedToSend") return "Queued";
  if (status === "NotSet") return "Not set";
  return status;
}

function emailStatusStyle(status: string) {
  if (status === "EmailSent") return "text-emerald-400 bg-emerald-400/10 border-emerald-500/20";
  if (status === "NeedToSend") return "text-amber-400 bg-amber-400/10 border-amber-500/20";
  if (status === "NotSet") return "text-slate-500 bg-slate-500/10 border-slate-500/20";
  return "text-blue-400 bg-blue-400/10 border-blue-500/20";
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin text-slate-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9" />
    </svg>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { toasts, push: pushToast, dismiss: dismissToast } = useToast();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const [activity, setActivity] = useState<InvoiceActivityRow[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);

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
        const rows = await apiGet<InvoiceActivityRow[]>("/activity/recent-invoices");
        if (!cancelled) setActivity(rows);
      } catch (e) {
        if (!cancelled) pushToast(e instanceof Error ? e.message : "Could not load activity");
      } finally {
        if (!cancelled) setActivityLoading(false);
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

      {/* Recent Activity */}
      <div
        className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp"
        style={{ background: "var(--bg-card)", animationDelay: "0.25s" }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-white font-semibold text-sm">Recent Activity</h2>
          <span className="text-[11px] text-slate-600">Invoice emails · last 30 days · from QuickBooks</span>
        </div>

        {activityLoading && (
          <div className="px-6 py-8 flex items-center justify-center gap-2 text-slate-600 text-sm">
            <Spinner />
            Loading activity…
          </div>
        )}

        {!activityLoading && activity.length === 0 && (
          <div className="px-6 py-8 text-center text-slate-600 text-sm">
            No invoice email rows yet — connect QuickBooks and press Sync on Customers.
          </div>
        )}

        {!activityLoading && activity.length > 0 && (
          <div className="divide-y divide-white/[0.04]">
            {activity.map((row, i) => (
              <div
                key={`${row.invoice_number}-${i}`}
                className="flex items-center justify-between px-6 py-3.5 hover:bg-white/[0.03] transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                    {row.customer_display_name[0]?.toUpperCase() ?? "?"}
                  </div>
                  <div className="min-w-0">
                    <p className="text-white text-sm font-medium truncate">{row.customer_display_name}</p>
                    <p className="text-slate-600 text-xs font-mono">{row.invoice_number}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span
                    className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${emailStatusStyle(row.email_status)}`}
                  >
                    {emailStatusLabel(row.email_status)}
                  </span>
                  {row.txn_date && (
                    <span className="text-slate-600 text-xs tabular-nums">{row.txn_date}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {!activityLoading && activity.length > 0 && (
          <div className="px-6 py-3 border-t border-white/[0.06]">
            <span className="text-slate-600 text-xs">{activity.length} row{activity.length !== 1 ? "s" : ""}</span>
          </div>
        )}
      </div>
    </div>
  );
}
