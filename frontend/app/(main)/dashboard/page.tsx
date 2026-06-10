"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, type DashboardStats, type RecentInvoiceRow } from "@/lib/api";

function initials(name: string | null): string {
  if (!name) return "?";
  return name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  } catch { return "—"; }
}

function invoiceStatusBadge(status: string) {
  if (status === "EmailSent" || status === "sent")
    return <span className="badge badge-success"><span className="badge-dot badge-dot-success" />Sent</span>;
  if (status === "NeedToSend")
    return <span className="badge badge-warning"><span className="badge-dot badge-dot-warning" />Queued</span>;
  return <span className="badge badge-primary"><span className="badge-dot badge-dot-primary" />Created</span>;
}

function pgBtn(disabled: boolean, active = false): React.CSSProperties {
  return {
    minWidth: 28, height: 28, padding: "0 6px", fontSize: 12, fontWeight: active ? 700 : 400,
    borderRadius: 6, border: "1px solid var(--border)", cursor: disabled ? "default" : "pointer",
    background: active ? "var(--primary)" : "var(--surface-2)",
    color: active ? "#fff" : disabled ? "var(--text-4)" : "var(--text-2)",
    opacity: disabled ? 0.4 : 1,
  };
}

function Spinner() {
  return (
    <svg className="spinner" width="16" height="16" fill="none" stroke="var(--primary)" strokeWidth={2} viewBox="0 0 24 24">
      <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9" />
    </svg>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [invoices, setInvoices] = useState<RecentInvoiceRow[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const s = await apiGet<DashboardStats>("/dashboard/stats");
        if (!cancelled) setStats(s);
      } catch { /* silently fail */ }
      finally { if (!cancelled) setStatsLoading(false); }
    })();

    (async () => {
      try {
        const rows = await apiGet<RecentInvoiceRow[]>("/dashboard/recent-invoices");
        if (!cancelled) setInvoices(rows);
      } catch { /* silently fail */ }
      finally { if (!cancelled) setInvoicesLoading(false); }
    })();

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return invoices;
    return invoices.filter((r) =>
      (r.invoice_number ?? "").toLowerCase().includes(q) ||
      (r.customer_name ?? "").toLowerCase().includes(q) ||
      r.group.toLowerCase().includes(q) ||
      (r.file_name ?? "").toLowerCase().includes(q),
    );
  }, [invoices, search]);

  useEffect(() => { setPage(1); }, [search, pageSize]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

  const statCards = [
    {
      label: "Total Customers",
      value: stats?.total_customers ?? null,
      sub: stats ? `${stats.approved_customers} approved · ${stats.pending_customers} pending` : undefined,
      iconBg: "var(--primary-bg)",
      icon: <svg width="20" height="20" fill="none" stroke="var(--primary)" strokeWidth="1.8" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>,
      delay: "0s",
    },
    {
      label: "Imports Today",
      value: stats?.imports_today ?? null,
      sub: "Invoice file uploads since midnight UTC",
      iconBg: "#F5F3FF",
      icon: <svg width="20" height="20" fill="none" stroke="#7C3AED" strokeWidth="1.8" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
      delay: "0.06s",
    },
    {
      label: "Invoices Sent",
      value: stats?.invoices_sent ?? null,
      sub: "EmailSent · last 30-day QBO sync window",
      iconBg: "var(--success-bg)",
      icon: <svg width="20" height="20" fill="none" stroke="var(--success)" strokeWidth="1.8" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>,
      delay: "0.12s",
    },
    {
      label: "Delivery Failures",
      value: stats?.delivery_failures ?? null,
      sub: "NeedToSend · queued but not delivered",
      iconBg: "var(--error-bg)",
      icon: <svg width="20" height="20" fill="none" stroke="var(--error)" strokeWidth="1.8" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>,
      delay: "0.18s",
    },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      {/* Page header */}
      <div className="anim-fade-up" style={{ marginBottom: 24 }}>
        <div className="page-title">Dashboard</div>
        <div className="page-subtitle">Live snapshot of your account. Activity refreshes when you run Sync on Customers.</div>
      </div>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 28 }}>
        {statCards.map((card) => (
          <div key={card.label} className="stat-card anim-scale-in" style={{ animationDelay: card.delay }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ width: 42, height: 42, borderRadius: 12, background: card.iconBg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                {card.icon}
              </div>
            </div>
            {statsLoading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, height: 40 }}>
                <Spinner />
                <span style={{ fontSize: 13, color: "var(--text-4)" }}>Loading…</span>
              </div>
            ) : (
              <div style={{ fontSize: 32, fontWeight: 800, color: "var(--text-1)", letterSpacing: "-1px", lineHeight: 1 }}>
                {card.value?.toLocaleString() ?? "—"}
              </div>
            )}
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-2)", marginTop: 4 }}>{card.label}</div>
            {card.sub && !statsLoading && (
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4, lineHeight: 1.4 }}>{card.sub}</div>
            )}
          </div>
        ))}
      </div>

      {/* Pending banner */}
      {stats && stats.pending_customers > 0 && (
        <div className="notice-banner notice-warning anim-fade-up" style={{ animationDelay: "0.2s" }}>
          <span style={{ fontSize: 16 }}>⚠</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{stats.pending_customers} customer{stats.pending_customers !== 1 ? "s" : ""} awaiting your approval.</span>
          <span style={{ fontSize: 13, opacity: 0.75 }}>Review them in the Customers tab.</span>
        </div>
      )}

      {/* Recent Invoices table */}
      <div className="card anim-fade-up" style={{ overflow: "hidden", animationDelay: "0.25s" }}>
        <div className="section-header" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <div className="section-title">Invoices Created</div>
            <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 1 }}>Last 50 · newest first</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {/* Search */}
            <div style={{ position: "relative" }}>
              <svg style={{ position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }} width="13" height="13" fill="none" stroke="var(--text-4)" strokeWidth={2} viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" d="M21 21l-4.35-4.35" />
              </svg>
              <input
                type="text"
                placeholder="Search invoices…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ paddingLeft: 28, paddingRight: search ? 28 : 10, paddingTop: 6, paddingBottom: 6, fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg-input, var(--surface-2))", color: "var(--text-1)", width: 180, outline: "none" }}
              />
              {search && (
                <button onClick={() => setSearch("")} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--text-4)", fontSize: 12, padding: 0 }}>✕</button>
              )}
            </div>
            {!invoicesLoading && (
              <span className="badge badge-neutral">
                {search ? `${filtered.length} / ${invoices.length}` : `${invoices.length}`} records
              </span>
            )}
          </div>
        </div>

        {/* Header row */}
        <div className="table-header-row" style={{ gridTemplateColumns: "90px 1fr 1fr 110px 100px 140px" }}>
          {["INV #", "CUSTOMER", "GROUP", "DELIVERY DATE", "STATUS", "FILE NAME"].map((h) => (
            <span key={h} className="table-header-cell">{h}</span>
          ))}
        </div>

        {/* Loading */}
        {invoicesLoading && (
          <div style={{ padding: "40px 20px", display: "flex", alignItems: "center", justifyContent: "center", gap: 10, color: "var(--text-3)", fontSize: 13 }}>
            <Spinner /> Loading…
          </div>
        )}

        {/* Empty */}
        {!invoicesLoading && invoices.length === 0 && (
          <div style={{ padding: "48px 20px", textAlign: "center", color: "var(--text-3)", fontSize: 14 }}>
            No invoices yet — upload a file in Import to generate invoices.
          </div>
        )}
        {!invoicesLoading && invoices.length > 0 && filtered.length === 0 && (
          <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--text-3)", fontSize: 14 }}>
            No invoices match &ldquo;{search}&rdquo;
          </div>
        )}

        {/* Rows */}
        {!invoicesLoading && paginated.map((row, i) => (
          <div
            key={row.id}
            className="table-row"
            style={{ gridTemplateColumns: "90px 1fr 1fr 110px 100px 140px", animationDelay: `${0.03 * i}s` }}
          >
            {/* INV # */}
            <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--text-2)", fontWeight: 600 }}>
              {row.invoice_number ?? "—"}
            </span>

            {/* CUSTOMER */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
              <div className="avatar avatar-primary" style={{ width: 28, height: 28, fontSize: 11, flexShrink: 0 }}>
                {initials(row.customer_name)}
              </div>
              <span className="table-cell-primary" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {row.customer_name ?? "—"}
              </span>
            </div>

            {/* GROUP */}
            <span style={{ fontSize: 13, color: "var(--primary)", fontWeight: 500 }}>{row.group}</span>

            {/* DELIVERY DATE */}
            <span className="table-cell-secondary">{fmtDate(row.sent_at)}</span>

            {/* STATUS */}
            <div>{invoiceStatusBadge(row.send_status)}</div>

            {/* FILE NAME */}
            <span className="table-cell-muted" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {row.file_name ?? "—"}
            </span>
          </div>
        ))}

        {!invoicesLoading && filtered.length > 0 && (
          <div className="table-footer" style={{ flexWrap: "wrap", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12, color: "var(--text-3)" }}>
                {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, filtered.length)} of {filtered.length}
              </span>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                style={{ fontSize: 11, color: "var(--text-3)", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 6, padding: "2px 6px", cursor: "pointer" }}
              >
                {[10, 25, 50].map((s) => <option key={s} value={s}>{s} / page</option>)}
              </select>
            </div>
            {totalPages > 1 && (
              <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
                <button onClick={() => setPage(1)} disabled={page === 1} style={pgBtn(page === 1)}>«</button>
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={pgBtn(page === 1)}>‹</button>
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                  .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                    if (idx > 0 && typeof arr[idx - 1] === "number" && (p as number) - (arr[idx - 1] as number) > 1) acc.push("…");
                    acc.push(p);
                    return acc;
                  }, [])
                  .map((p, idx) =>
                    p === "…" ? (
                      <span key={`e-${idx}`} style={{ padding: "0 4px", fontSize: 11, color: "var(--text-4)" }}>…</span>
                    ) : (
                      <button key={p} onClick={() => setPage(p as number)} style={pgBtn(false, page === p)}>{p}</button>
                    )
                  )}
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={pgBtn(page === totalPages)}>›</button>
                <button onClick={() => setPage(totalPages)} disabled={page === totalPages} style={pgBtn(page === totalPages)}>»</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
