"use client";

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost, type ProductAndServiceRow, type SheetColumnRow } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { ToastContainer, useToast } from "@/app/components/Toast";

function MappingRow({
  product,
  sheetColumns,
  onChanged,
  push,
}: {
  product: ProductAndServiceRow;
  sheetColumns: SheetColumnRow[];
  onChanged: () => void;
  push: (msg: string, kind?: "success" | "error") => void;
}) {
  const [draft, setDraft] = useState<number | "">(product.sheet_column_id ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(product.sheet_column_id ?? "");
  }, [product.sheet_column_id]);

  const dirty = draft !== (product.sheet_column_id ?? "");

  // One column -> one product: hide columns already claimed by a different product,
  // but keep this product's own current selection visible in the list.
  const availableColumns = sheetColumns.filter(
    (c) => !c.mapped_product_name || c.mapped_product_name === product.name || c.id === product.sheet_column_id,
  );

  const handleSave = async () => {
    if (draft === "") {
      push("Choose a column before saving.", "error");
      return;
    }
    setSaving(true);
    try {
      await apiPatch(`/product-and-services/${product.id}/column-mapping`, { sheet_column_id: draft });
      push(`Saved mapping for "${product.name}"`, "success");
      onChanged();
    } catch (err) {
      push(err instanceof Error ? err.message : "Failed to save mapping", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    try {
      await apiDelete(`/product-and-services/${product.id}/column-mapping`);
      push(`Cleared mapping for "${product.name}" — back to default logic.`, "success");
      onChanged();
    } catch (err) {
      push(err instanceof Error ? err.message : "Failed to clear mapping", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="grid grid-cols-[minmax(0,1.3fr)_minmax(0,1.5fr)_auto_auto] items-center gap-3 px-5 py-3"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="text-sm font-semibold truncate" style={{ color: "var(--text-1)" }} title={product.name}>
          {product.name}
        </div>
        {product.description && (
          <div className="text-xs truncate mt-0.5" style={{ color: "var(--text-3)" }} title={product.description}>
            {product.description}
          </div>
        )}
      </div>
      <select
        value={draft === "" ? "" : String(draft)}
        onChange={(e) => setDraft(e.target.value === "" ? "" : Number(e.target.value))}
        className="rounded-lg bg-white border border-gray-200 px-2.5 py-2 text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200"
      >
        <option value="">Select a column…</option>
        {availableColumns.map((c) => (
          <option key={c.id} value={c.id}>{c.name}</option>
        ))}
      </select>
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={saving || !dirty}
        onClick={() => void handleSave()}
      >
        {saving ? "…" : "Save"}
      </button>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={saving || !product.sheet_column_id}
        onClick={() => void handleClear()}
      >
        Clear
      </button>
    </div>
  );
}

function ColumnCatalog({
  sheetColumns,
  onChanged,
  push,
}: {
  sheetColumns: SheetColumnRow[];
  onChanged: () => void;
  push: (msg: string, kind?: "success" | "error") => void;
}) {
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const addColumn = async (raw: string) => {
    const name = raw.trim();
    if (!name) return;
    try {
      await apiPost("/sheet-columns", { name });
      onChanged();
    } catch (err) {
      push(err instanceof Error ? err.message : `Failed to add "${name}"`, "error");
    }
  };

  const handleAdd = async () => {
    // Supports pasting several newline-separated headers at once.
    const names = newName.split("\n").map((n) => n.trim()).filter(Boolean);
    if (names.length === 0) return;
    setAdding(true);
    try {
      for (const name of names) {
        await addColumn(name);
      }
      setNewName("");
      push(names.length > 1 ? `Added ${names.length} columns` : `Added "${names[0]}"`, "success");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (col: SheetColumnRow) => {
    setDeletingId(col.id);
    try {
      await apiDelete(`/sheet-columns/${col.id}`);
      push(`Removed "${col.name}"`, "success");
      onChanged();
    } catch (err) {
      push(err instanceof Error ? err.message : "Failed to remove column", "error");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 overflow-hidden mb-5" style={{ background: "var(--bg-card)" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-left hover:bg-gray-50"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          Column catalog
          <span className="badge badge-neutral" style={{ fontSize: 11 }}>{sheetColumns.length}</span>
        </span>
        <span className="text-gray-400 text-xs">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-gray-200">
          <p className="text-xs mb-3" style={{ color: "var(--text-3)" }}>
            The exact column headers from your RAW Data-Imaging sheet. Add them here (one per line if pasting
            several), then assign each to a product below.
          </p>
          <div className="flex gap-2 items-start mb-4">
            <textarea
              className="input"
              style={{ flex: 1, fontSize: 13, minHeight: 38 }}
              rows={1}
              placeholder="Paste one or more column headers (one per line)…"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleAdd();
                }
              }}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm shrink-0"
              disabled={adding || !newName.trim()}
              onClick={() => void handleAdd()}
            >
              {adding ? "Adding…" : "+ Add"}
            </button>
          </div>

          {sheetColumns.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--text-3)" }}>No columns added yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {sheetColumns.map((c) => (
                <span
                  key={c.id}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs"
                  title={c.mapped_product_name ? `Mapped to ${c.mapped_product_name}` : undefined}
                >
                  <span style={{ color: "var(--text-2)" }}>{c.name}</span>
                  {c.mapped_product_name && (
                    <span style={{ color: "var(--primary)", fontWeight: 600 }}>→ {c.mapped_product_name}</span>
                  )}
                  <button
                    type="button"
                    disabled={!!c.mapped_product_name || deletingId === c.id}
                    onClick={() => void handleDelete(c)}
                    className="text-gray-400 hover:text-red-600 disabled:opacity-30 disabled:hover:text-gray-400"
                    aria-label={`Remove ${c.name}`}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProductMappingPage() {
  const { user, loading: authLoading } = useAuth();
  const { toasts, push, dismiss } = useToast();

  const [products, setProducts] = useState<ProductAndServiceRow[] | null>(null);
  const [sheetColumns, setSheetColumns] = useState<SheetColumnRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    Promise.all([
      apiGet<ProductAndServiceRow[]>("/product-and-services"),
      apiGet<SheetColumnRow[]>("/sheet-columns"),
    ])
      .then(([p, sc]) => { setProducts(p); setSheetColumns(sc); })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load data"));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (authLoading) {
    return <div className="max-w-5xl mx-auto py-12 text-center text-gray-400 text-sm">Loading…</div>;
  }

  if (user?.role !== "admin") {
    return (
      <div className="max-w-5xl mx-auto py-12 text-center">
        <p className="text-red-600 text-sm">Admin access required.</p>
      </div>
    );
  }

  const q = search.toLowerCase().trim();
  const activeProducts = (products ?? [])
    .filter((p) => p.active)
    .filter((p) => !q || p.name.toLowerCase().includes(q))
    .sort((a, b) => a.name.localeCompare(b.name));
  const mappedCount = (products ?? []).filter((p) => p.active && p.sheet_column_id).length;
  const totalActive = (products ?? []).filter((p) => p.active).length;

  return (
    <div className="max-w-5xl mx-auto animate-fadeInUp">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Product &amp; Service Mapping</h1>
        <p className="text-gray-400 text-sm mt-1">
          Point a product/service at the exact spreadsheet column it should read its quantity from. Once set,
          this fully replaces the built-in mapping logic for that product — clear it to go back to the default.
          Each column can only be assigned to one product at a time.
        </p>
        {!loadError && products && (
          <p className="text-xs mt-1.5" style={{ color: "var(--text-3)" }}>
            {mappedCount} of {totalActive} active products mapped
          </p>
        )}
      </div>

      {loadError && <p className="text-red-600 text-sm mb-4">{loadError}</p>}

      {!products && !loadError && (
        <div className="py-12 text-center text-gray-400 text-sm">Loading…</div>
      )}

      {products && (
        <>
          <ColumnCatalog sheetColumns={sheetColumns} onChanged={load} push={push} />

          <div className="mb-4 max-w-sm">
            <input
              type="text"
              placeholder="Search products…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-3 pr-3 py-2.5 rounded-xl border border-gray-200 bg-gray-50 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            />
          </div>

          <div className="rounded-2xl border border-gray-200 overflow-hidden" style={{ background: "var(--bg-card)" }}>
            <div
              className="grid grid-cols-[minmax(0,1.3fr)_minmax(0,1.5fr)_auto_auto] gap-3 px-5 py-3"
              style={{ borderBottom: "1px solid var(--border)" }}
            >
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Product</span>
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Column header</span>
              <span />
              <span />
            </div>

            {activeProducts.length === 0 ? (
              <div className="px-5 py-12 text-center text-gray-400 text-sm">
                {search ? `No products match "${search}"` : "No active products found — sync from QuickBooks first."}
              </div>
            ) : (
              activeProducts.map((p) => (
                <MappingRow key={p.id} product={p} sheetColumns={sheetColumns} onChanged={load} push={push} />
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
