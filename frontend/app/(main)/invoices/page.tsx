"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiDelete, apiGet, apiPatch, apiPost, type CenterRow, type CustomerRow, type InvoiceRow } from "@/lib/api";

// ── Styles ────────────────────────────────────────────────────────────────────

function fieldCls() {
  return "w-full rounded-lg bg-[#1a1d2e] border border-white/[0.08] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40";
}

type SortKey = "id" | "customer" | "title" | "centers";
type SortDir = "asc" | "desc";

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  return (
    <span className={`ml-1 inline-flex flex-col leading-none`}>
      <span className={`text-[8px] leading-none ${active && dir === "asc" ? "text-indigo-400" : "text-slate-700"}`}>▲</span>
      <span className={`text-[8px] leading-none ${active && dir === "desc" ? "text-indigo-400" : "text-slate-700"}`}>▼</span>
    </span>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

function InvoicesPageContent() {
  const searchParams = useSearchParams();

  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [invoices, setInvoices] = useState<InvoiceRow[]>([]);
  const [centerNameById, setCenterNameById] = useState<Record<number, string>>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Grouping form
  const [companyId, setCompanyId] = useState<number | "">("");
  const [centers, setCenters] = useState<CenterRow[]>([]);
  const [centersLoading, setCentersLoading] = useState(false);
  const [selectedCenterIds, setSelectedCenterIds] = useState<number[]>([]);
  const [title, setTitle] = useState("");

  // Tabs
  const [activeTab, setActiveTab] = useState<"grouping" | "listing">("grouping");

  // Listing search / sort
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("id");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Edit modal
  const [editInvoice, setEditInvoice] = useState<InvoiceRow | null>(null);
  const [editCenters, setEditCenters] = useState<CenterRow[]>([]);
  const [editCentersLoading, setEditCentersLoading] = useState(false);
  const [editSelectedIds, setEditSelectedIds] = useState<number[]>([]);
  const [editTitle, setEditTitle] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // ── Data loading ────────────────────────────────────────────────────────────

  const loadCustomers = useCallback(async () => {
    try {
      setCustomers(await apiGet<CustomerRow[]>("/customers"));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load customers");
    }
  }, []);

  const loadInvoices = useCallback(async () => {
    try {
      setInvoices(await apiGet<InvoiceRow[]>("/invoices"));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load invoices");
    }
  }, []);

  useEffect(() => {
    void loadCustomers();
    void loadInvoices();
  }, [loadCustomers, loadInvoices]);

  // Pre-select company from query param (e.g. from Customer page grid icon)
  useEffect(() => {
    const raw = searchParams.get("company");
    if (!raw) return;
    const id = Number(raw);
    if (!Number.isFinite(id) || id < 1) return;
    setCompanyId(id);
    setActiveTab("grouping");
  }, [searchParams]);

  // Load centers when company changes
  useEffect(() => {
    if (companyId === "") {
      setCenters([]);
      setSelectedCenterIds([]);
      return;
    }
    let cancelled = false;
    setCentersLoading(true);
    void apiGet<CenterRow[]>(`/customers/${companyId}/centers`)
      .then((rows) => {
        if (!cancelled) {
          setCenters(rows);
          setSelectedCenterIds((prev) => prev.filter((id) => rows.some((r) => r.id === id)));
        }
      })
      .catch((e) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : "Failed to load centers");
      })
      .finally(() => { if (!cancelled) setCentersLoading(false); });
    return () => { cancelled = true; };
  }, [companyId]);

  // Build center name lookup for the listing
  useEffect(() => {
    const companyIds = [...new Set(invoices.map((i) => i.company_id))];
    if (companyIds.length === 0) { setCenterNameById({}); return; }
    let cancelled = false;
    void (async () => {
      const next: Record<number, string> = {};
      for (const cid of companyIds) {
        try {
          const rows = await apiGet<CenterRow[]>(`/customers/${cid}/centers`);
          for (const r of rows) next[r.id] = r.name;
        } catch { /* ignore */ }
      }
      if (!cancelled) setCenterNameById(next);
    })();
    return () => { cancelled = true; };
  }, [invoices]);

  // Load centers when edit modal opens
  useEffect(() => {
    if (!editInvoice) return;
    setEditTitle(editInvoice.title ?? "");
    setEditSelectedIds(editInvoice.center_ids);
    setEditError(null);
    let cancelled = false;
    setEditCentersLoading(true);
    void apiGet<CenterRow[]>(`/customers/${editInvoice.company_id}/centers`)
      .then((rows) => { if (!cancelled) setEditCenters(rows); })
      .catch((e) => { if (!cancelled) setEditError(e instanceof Error ? e.message : "Failed to load centers"); })
      .finally(() => { if (!cancelled) setEditCentersLoading(false); });
    return () => { cancelled = true; };
  }, [editInvoice]);

  // ── Derived ─────────────────────────────────────────────────────────────────

  const customerById = useMemo(() => new Map(customers.map((c) => [c.id, c])), [customers]);
  const companyLabel = (id: number) => customerById.get(id)?.display_name ?? `Company #${id}`;

  // Centers used in OTHER groupings for the invoice being edited
  const editCenterUsedInInvoiceId = useMemo(() => {
    if (!editInvoice) return new Map<number, number>();
    const m = new Map<number, number>();
    for (const inv of invoices) {
      if (inv.company_id !== editInvoice.company_id) continue;
      if (inv.id === editInvoice.id) continue;
      for (const cid of inv.center_ids) {
        if (!m.has(cid)) m.set(cid, inv.id);
      }
    }
    return m;
  }, [invoices, editInvoice]);

  const centerUsedInInvoiceId = useMemo(() => {
    if (companyId === "") return new Map<number, number>();
    const m = new Map<number, number>();
    for (const inv of invoices) {
      if (inv.company_id !== companyId) continue;
      for (const cid of inv.center_ids) {
        if (!m.has(cid)) m.set(cid, inv.id);
      }
    }
    return m;
  }, [invoices, companyId]);

  const formatCenters = (inv: InvoiceRow) =>
    inv.center_ids.map((id) => centerNameById[id] ?? `Center #${id}`).join(", ");

  // Filtered + sorted invoices for Listing tab
  const filteredInvoices = useMemo(() => {
    const q = search.toLowerCase().trim();
    let list = invoices;
    if (q) {
      list = list.filter((inv) => {
        const name = companyLabel(inv.company_id).toLowerCase();
        const t = (inv.title ?? "").toLowerCase();
        const c = formatCenters(inv).toLowerCase();
        return name.includes(q) || t.includes(q) || c.includes(q);
      });
    }
    return [...list].sort((a, b) => {
      const mul = sortDir === "asc" ? 1 : -1;
      if (sortKey === "id") return (a.id - b.id) * mul;
      if (sortKey === "centers") return (a.center_ids.length - b.center_ids.length) * mul;
      if (sortKey === "customer") return companyLabel(a.company_id).localeCompare(companyLabel(b.company_id)) * mul;
      if (sortKey === "title") return (a.title ?? "").localeCompare(b.title ?? "") * mul;
      return 0;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoices, search, sortKey, sortDir, centerNameById, customerById]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  // ── Actions ─────────────────────────────────────────────────────────────────

  const toggleCenter = (id: number) => {
    if (centerUsedInInvoiceId.get(id) !== undefined) return;
    setSelectedCenterIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const onDeleteGrouping = async (id: number) => {
    if (!window.confirm("Remove this invoice grouping? Centers become available for new groupings.")) return;
    setDeletingId(id);
    setLoadError(null);
    try {
      await apiDelete(`/invoices/${id}`);
      await loadInvoices();
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to delete");
    } finally {
      setDeletingId(null);
    }
  };

  const onCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (companyId === "" || selectedCenterIds.length === 0) return;
    setSaving(true);
    setLoadError(null);
    try {
      await apiPost<InvoiceRow>("/invoices", {
        company_id: companyId,
        center_ids: selectedCenterIds,
        title: title.trim() || null,
      });
      setTitle("");
      setSelectedCenterIds([]);
      await loadInvoices();
      setActiveTab("listing");
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to create invoice");
    } finally {
      setSaving(false);
    }
  };

  const toggleEditCenter = (id: number) => {
    if (editCenterUsedInInvoiceId.get(id) !== undefined) return;
    setEditSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const onSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editInvoice || editSelectedIds.length === 0) return;
    setEditSaving(true);
    setEditError(null);
    try {
      await apiPatch<InvoiceRow>(`/invoices/${editInvoice.id}`, {
        center_ids: editSelectedIds,
        title: editTitle.trim() || null,
      });
      setEditInvoice(null);
      await loadInvoices();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to update grouping");
    } finally {
      setEditSaving(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  const COLS = "grid-cols-[3rem_minmax(0,2fr)_minmax(0,1.5fr)_minmax(0,2fr)_5rem_7rem]";

  return (
    <div className="max-w-5xl mx-auto animate-fadeInUp">

      {/* ── Edit modal ── */}
      {editInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-white/[0.1] shadow-2xl" style={{ background: "var(--bg-deep)" }}>
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08]">
              <div>
                <h2 className="text-base font-bold text-white">Edit grouping #{editInvoice.id}</h2>
                <p className="text-xs text-slate-500 mt-0.5">{companyLabel(editInvoice.company_id)}</p>
              </div>
              <button type="button" onClick={() => setEditInvoice(null)} className="text-slate-400 hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={(e) => void onSaveEdit(e)} className="p-6 space-y-5">
              {editError && <p className="text-rose-400 text-xs">{editError}</p>}

              {/* Centers */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
                  Centers <span className="normal-case text-slate-600">(at least one required)</span>
                </label>
                {editCentersLoading && (
                  <p className="text-xs text-slate-600 py-2 flex items-center gap-1.5">
                    <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                    </svg>
                    Loading centers…
                  </p>
                )}
                {!editCentersLoading && editCenters.length === 0 && (
                  <p className="text-xs text-amber-400/90 py-2">No centers found for this company.</p>
                )}
                {editCenters.length > 0 && (
                  <ul className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2 space-y-2 max-h-52 overflow-y-auto">
                    {editCenters.map((c) => {
                      const usedInv = editCenterUsedInInvoiceId.get(c.id);
                      const disabled = usedInv !== undefined;
                      return (
                        <li key={c.id}>
                          <label className={`flex items-center gap-2.5 text-sm ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer text-slate-300"}`}>
                            <input
                              type="checkbox"
                              className="rounded border-white/20 disabled:opacity-40"
                              checked={editSelectedIds.includes(c.id)}
                              disabled={disabled}
                              onChange={() => toggleEditCenter(c.id)}
                            />
                            <span>{c.name}</span>
                            {disabled && <span className="text-[10px] text-slate-600 uppercase tracking-wide ml-1">in grouping #{usedInv}</span>}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {editSelectedIds.length > 0 && (
                  <p className="text-xs text-indigo-400 mt-1.5">{editSelectedIds.length} center{editSelectedIds.length !== 1 ? "s" : ""} selected</p>
                )}
              </div>

              {/* Title */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Title (optional)</label>
                <input
                  className={fieldCls()}
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="e.g. March combined — North + East"
                  maxLength={500}
                />
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button type="button" onClick={() => setEditInvoice(null)} className="px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white transition-colors">Cancel</button>
                <button
                  type="submit"
                  disabled={editSaving || editSelectedIds.length === 0}
                  className="shimmer-btn px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
                >
                  {editSaving ? "Saving…" : "Save changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white tracking-tight">Invoices</h1>
        <p className="text-slate-500 text-sm mt-1">
          Group centers per customer for invoice generation. Each center can only belong to one grouping per customer.
        </p>
        {loadError && <p className="text-rose-400 text-xs mt-2">{loadError}</p>}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-xl border border-white/[0.07] w-fit" style={{ background: "var(--bg-card)" }}>
        {(["grouping", "listing"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition-colors ${
              activeTab === tab
                ? "bg-indigo-600 text-white shadow"
                : "text-slate-400 hover:text-white"
            }`}
          >
            {tab === "grouping" ? "New Grouping" : `Saved Groupings${invoices.length ? ` (${invoices.length})` : ""}`}
          </button>
        ))}
      </div>

      {/* ── Grouping tab ── */}
      {activeTab === "grouping" && (
        <form
          onSubmit={(e) => void onCreateInvoice(e)}
          className="rounded-2xl border border-white/[0.07] p-6 space-y-5"
          style={{ background: "var(--bg-card)" }}
        >
          <div>
            <h2 className="text-sm font-semibold text-white">New invoice grouping</h2>
            <p className="text-[11px] text-slate-600 mt-0.5">
              Open from <span className="text-slate-500">Customers</span> via the grid icon on a row to pre-select that company.
            </p>
          </div>

          {/* Company select */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Company</label>
            <div className="relative">
              <select
                value={companyId === "" ? "" : String(companyId)}
                onChange={(e) => {
                  const v = e.target.value;
                  setCompanyId(v === "" ? "" : Number(v));
                  setSelectedCenterIds([]);
                }}
                required
                className="w-full rounded-lg border border-white/[0.08] px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/40 appearance-none pr-8"
                style={{ background: "#1a1d2e" }}
              >
                <option value="" style={{ background: "#1a1d2e", color: "#94a3b8" }}>Select customer…</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id} style={{ background: "#1a1d2e", color: "#f1f5f9" }}>
                    {c.display_name}
                  </option>
                ))}
              </select>
              {/* chevron */}
              <svg className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Centers */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
              Centers <span className="normal-case text-slate-600">(select one or more — unavailable if already grouped)</span>
            </label>
            {companyId === "" && <p className="text-xs text-slate-600 py-2">Choose a company to load centers.</p>}
            {companyId !== "" && centersLoading && (
              <p className="text-xs text-slate-600 py-2 flex items-center gap-1.5">
                <svg className="w-3 h-3 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9" />
                </svg>
                Loading centers…
              </p>
            )}
            {companyId !== "" && !centersLoading && centers.length === 0 && (
              <p className="text-xs text-amber-400/90 py-2">No centers yet — add them on the customer record first.</p>
            )}
            {centers.length > 0 && (
              <ul className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2 space-y-2 max-h-52 overflow-y-auto">
                {centers.map((c) => {
                  const usedInv = centerUsedInInvoiceId.get(c.id);
                  const disabled = usedInv !== undefined;
                  return (
                    <li key={c.id}>
                      <label className={`flex items-center gap-2.5 text-sm ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer text-slate-300"}`}>
                        <input
                          type="checkbox"
                          className="rounded border-white/20 disabled:opacity-40"
                          checked={selectedCenterIds.includes(c.id)}
                          disabled={disabled}
                          onChange={() => toggleCenter(c.id)}
                        />
                        <span>{c.name}</span>
                        {disabled && <span className="text-[10px] text-slate-600 uppercase tracking-wide ml-1">in grouping #{usedInv}</span>}
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Title */}
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Title (optional)</label>
            <input
              className={fieldCls()}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. March combined — North + East"
              maxLength={500}
            />
          </div>

          <button
            type="submit"
            disabled={saving || companyId === "" || selectedCenterIds.length === 0}
            className="shimmer-btn px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save invoice grouping"}
          </button>
        </form>
      )}

      {/* ── Listing tab ── */}
      {activeTab === "listing" && (
        <div className="space-y-4">
          {/* Search bar */}
          <div className="relative max-w-sm">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <circle cx="11" cy="11" r="8" /><path strokeLinecap="round" d="M21 21l-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Search by customer, title, or center…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-8 py-2.5 rounded-xl border border-white/[0.09] bg-white/[0.04] text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white text-xs">✕</button>
            )}
          </div>

          {/* Table */}
          <div className="rounded-2xl border border-white/[0.07] overflow-hidden" style={{ background: "var(--bg-card)" }}>
            {/* Header */}
            <div className={`grid ${COLS} px-5 py-3 border-b border-white/[0.06] max-md:hidden`}>
              {([
                { label: "#", key: "id" as SortKey, align: "text-right" },
                { label: "Customer", key: "customer" as SortKey },
                { label: "Title", key: "title" as SortKey },
                { label: "Centers", key: "centers" as SortKey },
                { label: "Count", key: "centers" as SortKey, align: "text-center" },
                { label: "Actions", align: "text-center" },
              ] as { label: string; key?: SortKey; align?: string }[]).map((h, idx) => (
                <button
                  key={`${h.label}-${idx}`}
                  type="button"
                  disabled={!h.key}
                  onClick={() => h.key && toggleSort(h.key)}
                  className={`flex items-center text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-300 transition-colors disabled:cursor-default disabled:hover:text-slate-500 ${h.align ?? ""}`}
                >
                  {h.label}
                  {h.key && <SortIcon active={sortKey === h.key} dir={sortDir} />}
                </button>
              ))}
            </div>

            {/* Rows */}
            {filteredInvoices.length === 0 ? (
              <p className="px-5 py-10 text-center text-slate-500 text-sm">
                {search ? `No groupings match "${search}"` : "No invoice groupings yet. Create one in the New Grouping tab."}
              </p>
            ) : (
              <ul className="divide-y divide-white/[0.04]">
                {filteredInvoices.map((inv) => (
                  <li key={inv.id} className={`grid max-md:grid-cols-1 ${COLS} items-center px-5 py-3.5 hover:bg-white/[0.03] transition-colors`}>
                    {/* ID */}
                    <span className="text-slate-600 text-xs font-mono text-right pr-4">#{inv.id}</span>

                    {/* Customer */}
                    <div className="flex items-center gap-2.5 min-w-0 pr-4">
                      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                        {companyLabel(inv.company_id)[0]?.toUpperCase() ?? "?"}
                      </div>
                      <span className="text-white text-sm font-medium truncate">{companyLabel(inv.company_id)}</span>
                    </div>

                    {/* Title */}
                    <span className="text-slate-400 text-sm truncate pr-4">{inv.title ?? <span className="text-slate-700 italic">—</span>}</span>

                    {/* Centers */}
                    <span className="text-slate-400 text-xs truncate pr-4" title={formatCenters(inv)}>
                      {formatCenters(inv) || <span className="text-slate-700">—</span>}
                    </span>

                    {/* Count badge */}
                    <div className="flex justify-center">
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
                        {inv.center_ids.length}
                      </span>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-center gap-1">
                      {/* Edit */}
                      <button
                        type="button"
                        title="Edit grouping"
                        onClick={() => setEditInvoice(inv)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                        </svg>
                      </button>
                      {/* Delete */}
                      <button
                        type="button"
                        title="Remove grouping"
                        disabled={deletingId === inv.id}
                        onClick={() => void onDeleteGrouping(inv.id)}
                        className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      >
                        {deletingId === inv.id ? (
                          <svg className="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                          </svg>
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {/* Footer */}
            {invoices.length > 0 && (
              <div className="px-5 py-3 border-t border-white/[0.06]">
                <span className="text-slate-600 text-xs">
                  {filteredInvoices.length} grouping{filteredInvoices.length !== 1 ? "s" : ""}
                  {search ? ` matching "${search}"` : ` · ${invoices.length} total`}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function InvoicesPage() {
  return (
    <Suspense fallback={<div className="max-w-5xl mx-auto py-16 text-center text-slate-500 text-sm animate-fadeInUp">Loading…</div>}>
      <InvoicesPageContent />
    </Suspense>
  );
}
