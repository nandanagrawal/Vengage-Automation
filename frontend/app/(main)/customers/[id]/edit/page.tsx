"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch, type CustomerRow } from "@/lib/api";
import { CustomerFormFields, useCustomerForm } from "../../CustomerFormFields";

export default function CustomerEditPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const customerId = parseInt(params.id, 10);

  const [customer, setCustomer] = useState<CustomerRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiGet<CustomerRow>(`/customers/${customerId}`)
      .then(setCustomer)
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load customer"))
      .finally(() => setLoading(false));
  }, [customerId]);

  const formApi = useCustomerForm("edit", customer ?? undefined, !!customer);

  if (loading) {
    return <div className="max-w-4xl mx-auto py-12 text-center text-gray-400 text-sm">Loading…</div>;
  }

  if (loadError || !customer) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <p className="text-red-600 text-sm">{loadError ?? "Customer not found."}</p>
        <button onClick={() => router.push("/customers")} className="mt-4 text-indigo-600 text-sm hover:underline">← Back to Customers</button>
      </div>
    );
  }

  const onSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await formApi.submit((payload) => apiPatch<CustomerRow>(`/customers/${customerId}`, payload));
      if (saved) router.push(`/customers/${customerId}`);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save customer");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto animate-fadeInUp">
      <div className="flex items-center justify-between mb-5">
        <Link href={`/customers/${customerId}`} className="inline-flex items-center gap-1.5 text-gray-400 hover:text-gray-600 text-sm transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          {customer.display_name}
        </Link>
      </div>

      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/30 to-violet-600/30 border border-indigo-200 flex items-center justify-center text-indigo-600 text-xl font-bold shrink-0">
          {customer.display_name[0]?.toUpperCase() ?? "?"}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Edit {customer.display_name}</h1>
          {customer.company_name && <p className="text-gray-500 text-sm">{customer.company_name}</p>}
        </div>
      </div>

      {saveError && <p className="text-red-600 text-sm mb-4">{saveError}</p>}

      <form
        onSubmit={(e) => { e.preventDefault(); void onSave(); }}
        className="space-y-4 pb-10"
      >
        <CustomerFormFields api={formApi} mode="edit" />

        <div className="sticky bottom-0 flex justify-end gap-3 py-4 border-t border-gray-200" style={{ background: "var(--surface)" }}>
          <Link href={`/customers/${customerId}`} className="px-4 py-2 rounded-xl text-sm text-gray-500 hover:text-gray-900">Cancel</Link>
          <button type="submit" disabled={saving} className="shimmer-btn px-5 py-2.5 rounded-xl text-gray-900 text-sm font-semibold disabled:opacity-50">
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
