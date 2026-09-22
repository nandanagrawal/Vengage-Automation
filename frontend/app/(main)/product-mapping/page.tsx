"use client";

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, type SheetColumnRow } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { ToastContainer, useToast } from "@/app/components/Toast";

export default function ProductMappingPage() {
  const { user, loading: authLoading } = useAuth();
  const { toasts, push, dismiss } = useToast();

  const [sheetColumns, setSheetColumns] = useState<SheetColumnRow[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(() => {
    apiGet<SheetColumnRow[]>("/sheet-columns")
      .then(setSheetColumns)
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load data"));
  }, []);

  useEffect(() => { load(); }, [load]);

  const addColumn = async (raw: string) => {
    const name = raw.trim();
    if (!name) return;
    try {
      await apiPost("/sheet-columns", { name });
    } catch (err) {
      push(err instanceof Error ? err.message : `Failed to add "${name}"`, "error");
    }
  };

  const handleAdd = async () => {
    // Supports pasting several headers at once, one per line and/or comma-separated —
    // each becomes its own catalog entry.
    const names = newName
      .split(/[\n,]/)
      .map((n) => n.trim())
      .filter(Boolean);
    if (names.length === 0) return;
    setAdding(true);
    try {
      for (const name of names) {
        await addColumn(name);
      }
      setNewName("");
      push(names.length > 1 ? `Added ${names.length} columns` : `Added "${names[0]}"`, "success");
      load();
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (col: SheetColumnRow) => {
    setDeletingId(col.id);
    try {
      await apiDelete(`/sheet-columns/${col.id}`);
      push(`Removed "${col.name}"`, "success");
      load();
    } catch (err) {
      push(err instanceof Error ? err.message : "Failed to remove column", "error");
    } finally {
      setDeletingId(null);
    }
  };

  if (authLoading) {
    return <div className="max-w-3xl mx-auto py-12 text-center text-gray-400 text-sm">Loading…</div>;
  }

  if (user?.role !== "admin") {
    return (
      <div className="max-w-3xl mx-auto py-12 text-center">
        <p className="text-red-600 text-sm">Admin access required.</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto animate-fadeInUp">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Sheet Column Catalog</h1>
        <p className="text-gray-400 text-sm mt-1">
          The exact column headers from your RAW Data-Imaging sheet. Add them here, then pick one per
          service when editing a customer — each customer&apos;s service now chooses its own column, not
          a shared product-wide setting.
        </p>
      </div>

      {loadError && <p className="text-red-600 text-sm mb-4">{loadError}</p>}

      <div className="rounded-2xl border border-gray-200 overflow-hidden" style={{ background: "var(--bg-card)" }}>
        <div className="px-5 pb-5 pt-5">
          <div className="flex gap-2 items-start mb-4">
            <textarea
              className="input"
              style={{ flex: 1, fontSize: 13, minHeight: 38 }}
              rows={1}
              placeholder="Paste one or more column headers (one per line, or comma-separated)…"
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
                >
                  <span style={{ color: "var(--text-2)" }}>{c.name}</span>
                  <button
                    type="button"
                    disabled={deletingId === c.id}
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
      </div>
    </div>
  );
}
