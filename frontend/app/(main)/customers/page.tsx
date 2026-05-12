"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost, apiUpload, type CustomerRow, type SyncResult, type UploadAttachmentsResult } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { CustomerModal } from "./CustomerModal";

type SortKey = "display_name" | "primary_email" | "status";
type SortDir = "asc" | "desc";

function statusStyle(s: string) {
  if (s === "approved") return { label: "Approved", cls: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20", dot: "bg-emerald-400" };
  if (s === "rejected") return { label: "Rejected", cls: "text-red-400 bg-red-400/10 border-red-400/20", dot: "bg-red-400" };
  return { label: "Pending", cls: "text-amber-400 bg-amber-400/10 border-amber-400/20", dot: "bg-amber-400" };
}

const STATUS_ORDER = { approved: 0, pending: 1, rejected: 2 };
const PAGE_SIZES = [10, 25, 50];

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  return (
    <span className={`ml-1 inline-flex flex-col leading-none ${active ? "text-indigo-400" : "text-slate-700"}`}>
      <span className={`text-[8px] leading-none ${active && dir === "asc" ? "text-indigo-400" : "text-slate-600"}`}>▲</span>
      <span className={`text-[8px] leading-none ${active && dir === "desc" ? "text-indigo-400" : "text-slate-600"}`}>▼</span>
    </span>
  );
}

// Col layout: Customer | Email | Attach | Status | Actions
const COLS = "grid-cols-[minmax(0,2fr)_minmax(0,1.5fr)_4.5rem_8rem_12rem]";

export default function CustomersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  const [rows, setRows] = useState<CustomerRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState<number | null>(null);

  // Create / edit modal
  const [createOpen, setCreateOpen] = useState(false);
  const [editCustomer, setEditCustomer] = useState<CustomerRow | null>(null);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<CustomerRow | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Search / sort / page
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("display_name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const pendingCount = rows.filter((r) => r.status === "pending").length;

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      setRows(await apiGet<CustomerRow[]>("/customers"));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load customers");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setPage(1); }, [search, sortKey, sortDir, pageSize]);

  const onSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await apiPost<SyncResult>("/sync/quickbooks");
      setSyncMsg(`Pulled ${res.customers_pulled} · Pushed ${res.customers_pushed} · Created in QBO ${res.customers_created_remote} · Email rows ${res.invoice_activity_rows} · Attachments pruned ${res.attachments_pruned} · Items upserted ${res.items_upserted} · Items removed locally ${res.items_removed_local}`);
      await load();
    } catch (e) {
      setSyncMsg(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const uploadFiles = async (customerId: number, files: File[]) => {
    if (!files.length) return;
    try {
      const res = await apiUpload<UploadAttachmentsResult>(`/customers/${customerId}/attachments`, files);
      if (res.errors.length) {
        setLoadError(`Some uploads failed: ${res.errors.join("; ")}`);
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Attachment upload failed");
    }
  };

  const onCreate = async (payload: Record<string, unknown>, files: File[]): Promise<CustomerRow> => {
    setSaving(true);
    try {
      const created = await apiPost<CustomerRow>("/customers", payload);
      if (files.length && created.qbo_id) await uploadFiles(created.id, files);
      await load();
      return created;
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Save failed");
      throw e;
    } finally {
      setSaving(false);
    }
  };

  const onEdit = async (payload: Record<string, unknown>, files: File[]): Promise<CustomerRow> => {
    if (!editCustomer) throw new Error("No customer selected");
    setSaving(true);
    try {
      const updated = await apiPatch<CustomerRow>(`/customers/${editCustomer.id}`, payload);
      if (files.length) await uploadFiles(updated.id, files);
      await load();
      return updated;
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Update failed");
      throw e;
    } finally {
      setSaving(false);
    }
  };

  const onApprove = async (id: number, action: "approve" | "reject") => {
    setApproving(id);
    try {
      await apiPost<CustomerRow>(`/customers/${id}/approve`, { action });
      await load();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setApproving(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiDelete(`/customers/${deleteTarget.id}`);
      setDeleteTarget(null);
      await load();
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return rows;
    return rows.filter((r) =>
      r.display_name.toLowerCase().includes(q) ||
      (r.primary_email ?? "").toLowerCase().includes(q)
    );
  }, [rows, search]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const mul = sortDir === "asc" ? 1 : -1;
      if (sortKey === "status") {
        const ao = STATUS_ORDER[a.status as keyof typeof STATUS_ORDER] ?? 9;
        const bo = STATUS_ORDER[b.status as keyof typeof STATUS_ORDER] ?? 9;
        return (ao - bo) * mul;
      }
      return String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? "")) * mul;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paginated = sorted.slice((page - 1) * pageSize, page * pageSize);

  const headers: { label: string; key?: SortKey; align?: string }[] = [
    { label: "Customer", key: "display_name" },
    { label: "Email", key: "primary_email" },
    { label: "Attach", align: "text-center" },
    { label: "Status", key: "status", align: "text-center" },
    { label: "Actions", align: "text-center" },
  ];

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6 animate-fadeInUp">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Customers</h1>
          <p className="text-slate-500 text-sm mt-1">Two-way sync with QuickBooks · Supervisors create, admins approve and push to QBO · Use the grid icon to manage invoice groupings per customer.</p>
          {isAdmin && pendingCount > 0 && (
            <p className="text-amber-400 text-xs mt-1.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              {pendingCount} customer{pendingCount > 1 ? "s" : ""} awaiting your approval
            </p>
          )}
          {loadError && <p className="text-rose-400 text-xs mt-2">{loadError}</p>}
          {syncMsg && <p className="text-indigo-300 text-xs mt-2">{syncMsg}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
          <button type="button" onClick={() => void onSync()} disabled={syncing}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white/[0.12] text-white text-sm font-semibold hover:bg-white/[0.06] transition-colors disabled:opacity-50">
            <svg className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {syncing ? "Syncing…" : "Sync"}
          </button>
          <button type="button" onClick={() => setCreateOpen(true)}
            className="shimmer-btn inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-white text-sm font-semibold hover:scale-105 active:scale-95 transition-transform">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            Add Customer
          </button>
        </div>
      </div>

      {/* Modals */}
      <CustomerModal open={createOpen} onClose={() => setCreateOpen(false)} onSubmit={onCreate} submitting={saving} mode="create" />
      <CustomerModal open={!!editCustomer} onClose={() => setEditCustomer(null)} onSubmit={onEdit} submitting={saving} mode="edit" customer={editCustomer ?? undefined} />

      {/* Delete confirmation */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-white/[0.1] p-6 shadow-2xl" style={{ background: "var(--bg-card)" }}>
            <div className="w-10 h-10 rounded-xl bg-red-500/15 border border-red-500/20 flex items-center justify-center mb-4">
              <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <h3 className="text-white font-semibold mb-1">Delete customer?</h3>
            <p className="text-slate-400 text-sm mb-5">
              <span className="text-white font-medium">{deleteTarget.display_name}</span> will be permanently deleted from the app. This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleteTarget(null)} className="px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
              <button onClick={() => void confirmDelete()} disabled={deleting}
                className="px-4 py-2 rounded-xl text-sm font-semibold bg-red-500/20 text-red-400 border border-red-500/25 hover:bg-red-500/30 transition-colors disabled:opacity-50">
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="mb-4 animate-fadeInUp">
        <div className="relative max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" d="M21 21l-4.35-4.35" />
          </svg>
          <input type="text" placeholder="Search by name or email…" value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-8 py-2.5 rounded-xl border border-white/[0.09] bg-white/[0.04] text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40" />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white text-xs">✕</button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp delay-100" style={{ background: "var(--bg-card)" }}>
        {/* Header row */}
        <div className={`grid ${COLS} px-5 py-3 border-b border-white/[0.06] max-md:hidden`}>
          {headers.map((h) => (
            <button key={h.label} type="button" disabled={!h.key} onClick={() => h.key && toggleSort(h.key)}
              className={`flex items-center text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-300 transition-colors disabled:cursor-default disabled:hover:text-slate-500 ${h.align ?? ""}`}>
              {h.label}
              {h.key && <SortIcon active={sortKey === h.key} dir={sortDir} />}
            </button>
          ))}
        </div>

        {/* Rows */}
        <div className="divide-y divide-white/[0.04]">
          {paginated.length === 0 && (
            <div className="px-6 py-12 text-center text-slate-500 text-sm">
              {search ? `No customers match "${search}"` : "No customers yet — add one or run Sync."}
            </div>
          )}
          {paginated.map((c, i) => {
            const ss = statusStyle(c.status);
            return (
              <div key={c.id}
                className={`grid max-md:grid-cols-1 items-center px-5 py-3.5 hover:bg-white/[0.03] transition-colors animate-fadeInLeft cursor-pointer ${COLS}`}
                style={{ animationDelay: `${0.02 * i}s` }}
                onClick={() => router.push(`/customers/${c.id}`)}>

                {/* Customer */}
                <div className="flex items-center gap-3 min-w-0 pr-4">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                    {c.display_name[0]?.toUpperCase() ?? "?"}
                  </div>
                  <span className="text-white text-sm font-medium truncate">{c.display_name}</span>
                </div>

                {/* Email */}
                <span className="text-slate-400 text-sm truncate pr-4">{c.primary_email ?? "—"}</span>

                {/* Attach */}
                <div className="flex justify-center">
                  <span className={`text-xs font-semibold ${c.add_attachment_in_mail ? "text-emerald-400" : "text-slate-600"}`}>
                    {c.add_attachment_in_mail ? "Yes" : "No"}
                  </span>
                </div>

                {/* Status */}
                <div className="flex justify-center">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${ss.cls}`}>
                    <span className={`w-1 h-1 rounded-full ${ss.dot}`} />
                    {ss.label}
                  </span>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-center gap-0.5 flex-wrap" onClick={(e) => e.stopPropagation()}>
                  <Link
                    href={`/invoices?company=${c.id}`}
                    title="Invoice groupings for this customer"
                    className="p-1.5 rounded-lg text-slate-500 hover:text-sky-400 hover:bg-sky-500/10 transition-colors"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  </Link>
                  {/* Edit */}
                  <button
                    title="Edit customer"
                    onClick={(e) => { e.stopPropagation(); setEditCustomer(c); }}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
                    </svg>
                  </button>

                  {/* Approve / Reject (admin, pending only) */}
                  {isAdmin && c.status === "pending" && (
                    <>
                      <button disabled={approving === c.id} onClick={(e) => { e.stopPropagation(); void onApprove(c.id, "approve"); }}
                        className="px-2 py-1 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/25 hover:bg-emerald-500/30 transition-colors disabled:opacity-50">
                        {approving === c.id ? "…" : "✓"}
                      </button>
                      <button disabled={approving === c.id} onClick={(e) => { e.stopPropagation(); void onApprove(c.id, "reject"); }}
                        className="px-2 py-1 rounded-lg text-xs font-semibold bg-red-500/20 text-red-400 border border-red-500/25 hover:bg-red-500/30 transition-colors disabled:opacity-50">
                        ✕
                      </button>
                    </>
                  )}

                  {/* Delete (admin only) */}
                  {isAdmin && (
                    <button
                      title="Delete customer"
                      onClick={(e) => { e.stopPropagation(); setDeleteTarget(c); }}
                      className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-white/[0.06] flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-slate-600 text-xs">
              {filtered.length} result{filtered.length !== 1 ? "s" : ""}
              {search ? ` for "${search}"` : ` · ${rows.filter(r => r.status === "approved").length} approved · ${pendingCount} pending`}
            </span>
            <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}
              className="text-xs text-slate-400 bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-500/40">
              {PAGE_SIZES.map((s) => <option key={s} value={s}>{s} per page</option>)}
            </select>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(1)} disabled={page === 1}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-default transition-colors">«</button>
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-default transition-colors">‹</button>

              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                  if (idx > 0 && typeof arr[idx - 1] === "number" && (p as number) - (arr[idx - 1] as number) > 1) acc.push("…");
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, idx) =>
                  p === "…" ? (
                    <span key={`e-${idx}`} className="px-1 text-xs text-slate-700">…</span>
                  ) : (
                    <button key={p} onClick={() => setPage(p as number)}
                      className={`w-7 h-7 rounded-lg text-xs font-semibold transition-colors ${page === p ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white hover:bg-white/[0.06]"}`}>
                      {p}
                    </button>
                  )
                )}

              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-default transition-colors">›</button>
              <button onClick={() => setPage(totalPages)} disabled={page === totalPages}
                className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-white/[0.06] disabled:opacity-30 disabled:cursor-default transition-colors">»</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
