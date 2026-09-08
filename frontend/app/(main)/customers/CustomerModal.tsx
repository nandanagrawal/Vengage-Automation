"use client";

import type { FormEvent } from "react";
import { createPortal } from "react-dom";
import type { CustomerRow } from "@/lib/api";
import { CustomerFormFields, useCustomerForm } from "./CustomerFormFields";

export function CustomerModal({
  open,
  onClose,
  onSubmit,
  submitting,
  mode = "create",
  customer,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => Promise<CustomerRow>;
  submitting: boolean;
  mode?: "create" | "edit";
  customer?: CustomerRow;
}) {
  const formApi = useCustomerForm(mode, customer, open);

  const resetAndClose = () => {
    formApi.reset();
    onClose();
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const saved = await formApi.submit(onSubmit).catch(() => null);
    if (saved) resetAndClose();
  };

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm animate-fadeInUp">
      <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-gray-200 shadow-2xl" style={{ background: "var(--surface)" }}>
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-gray-200" style={{ background: "var(--surface)" }}>
          <h2 className="text-base font-700 text-gray-900" style={{ fontWeight: 700 }}>{mode === "edit" ? "Edit Customer" : "Add Customer"}</h2>
          <button type="button" onClick={resetAndClose} className="icon-btn">
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <CustomerFormFields api={formApi} mode={mode} />

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={resetAndClose} className="px-4 py-2 rounded-xl text-sm text-gray-500 hover:text-gray-900">Cancel</button>
            <button type="submit" disabled={submitting} className="shimmer-btn px-5 py-2.5 rounded-xl text-gray-900 text-sm font-semibold disabled:opacity-50">
              {submitting ? "Saving…" : mode === "edit" ? "Save changes" : "Save customer"}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
