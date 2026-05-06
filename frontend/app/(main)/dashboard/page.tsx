"use client";

import { useEffect, useState } from "react";
import { apiGet, type InvoiceActivityRow } from "@/lib/api";

const stats = [
  {
    label: "Total Customers",
    value: "—",
    delta: "",
    up: true,
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
      </svg>
    ),
    gradient: "from-blue-500 to-indigo-600",
  },
  {
    label: "Imports Today",
    value: "—",
    delta: "",
    up: true,
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
    ),
    gradient: "from-violet-500 to-purple-600",
  },
  {
    label: "Invoices Sent",
    value: "—",
    delta: "",
    up: true,
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    gradient: "from-emerald-400 to-teal-500",
  },
  {
    label: "Delivery Failures",
    value: "—",
    delta: "",
    up: false,
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    gradient: "from-rose-500 to-red-600",
  },
];

function emailStatusStyle(status: string) {
  if (status === "EmailSent") return "text-emerald-400";
  if (status === "Delivered") return "text-emerald-400";
  if (status === "NotSet") return "text-slate-500";
  return "text-blue-400";
}

export default function DashboardPage() {
  const [activity, setActivity] = useState<InvoiceActivityRow[]>([]);
  const [activityErr, setActivityErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await apiGet<InvoiceActivityRow[]>("/activity/recent-invoices");
        if (!cancelled) setActivity(rows);
      } catch (e) {
        if (!cancelled) setActivityErr(e instanceof Error ? e.message : "Could not load activity");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8 animate-fadeInUp">
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">Welcome back. Invoice email delivery rows refresh when you run Sync on Customers.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, delta, up, icon, gradient }, i) => (
          <div
            key={label}
            className="rounded-2xl border border-white/[0.07] p-5 hover:border-white/[0.14] hover:-translate-y-0.5 transition-all duration-200 card-glow animate-scaleIn"
            style={{ background: "var(--bg-card)", animationDelay: `${i * 0.06}s` }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white`}>{icon}</div>
              {delta ? (
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full ${up ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10"}`}
                >
                  {delta}
                </span>
              ) : null}
            </div>
            <p className="text-3xl font-extrabold text-white tracking-tight">{value}</p>
            <p className="text-slate-500 text-xs mt-1">{label}</p>
          </div>
        ))}
      </div>

      <div
        className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp delay-300"
        style={{ background: "var(--bg-card)" }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-white font-semibold text-sm">Recent Activity</h2>
          <span className="text-[11px] text-slate-600">Invoice emails (last 30 days, from QuickBooks)</span>
        </div>

        {activityErr && <p className="px-6 py-3 text-rose-400 text-xs">{activityErr}</p>}

        <div className="divide-y divide-white/[0.04]">
          {activity.length === 0 && !activityErr && (
            <div className="px-6 py-8 text-center text-slate-600 text-sm">No invoice email rows yet — connect QuickBooks and press Sync on Customers.</div>
          )}
          {activity.map((row) => (
            <div key={`${row.invoice_number}-${row.customer_display_name}`} className="flex items-center justify-between px-6 py-3.5 hover:bg-white/[0.03] transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                  {row.customer_display_name[0]?.toUpperCase() ?? "?"}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-sm font-medium truncate">{row.customer_display_name}</p>
                  <p className="text-slate-600 text-xs font-mono">{row.invoice_number}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className={`text-xs font-semibold ${emailStatusStyle(row.email_status)}`}>{row.email_status}</span>
                <span className="text-slate-600 text-xs">{row.txn_date ?? ""}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
