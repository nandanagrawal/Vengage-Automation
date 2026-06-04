"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch, type CustomerRow } from "@/lib/api";
import { CustomerModal } from "../CustomerModal";

function statusStyle(s: string) {
  if (s === "approved") return { label: "Approved", cls: "text-emerald-700 bg-emerald-50 border-emerald-200" };
  if (s === "rejected") return { label: "Rejected", cls: "text-red-600 bg-red-400/10 border-red-400/20" };
  return { label: "Pending", cls: "text-amber-700 bg-amber-50 border-amber-200" };
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" });
}

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm text-gray-700">{value}</p>
    </div>
  );
}

function InfoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 p-5" style={{ background: "var(--surface-2)" }}>
      <p className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">{title}</p>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">{children}</div>
    </div>
  );
}

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const customerId = parseInt(params.id, 10);

  const [customer, setCustomer] = useState<CustomerRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiGet<CustomerRow>(`/customers/${customerId}`)
      .then(setCustomer)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load customer"))
      .finally(() => setLoading(false));
  }, [customerId]);

  if (loading) {
    return <div className="max-w-4xl mx-auto py-12 text-center text-gray-400 text-sm">Loading…</div>;
  }

  if (error || !customer) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <p className="text-red-600 text-sm">{error ?? "Customer not found."}</p>
        <button onClick={() => router.push("/customers")} className="mt-4 text-indigo-600 text-sm hover:underline">← Back to Customers</button>
      </div>
    );
  }

  const ss = statusStyle(customer.status);

  const onEdit = async (payload: Record<string, unknown>) => {
    setSaving(true);
    try {
      const updated = await apiPatch<CustomerRow>(`/customers/${customerId}`, payload);
      setCustomer(updated);
      setEditOpen(false);
      return updated;
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto animate-fadeInUp">
      <div className="flex items-center justify-between mb-5">
        <Link href="/customers" className="inline-flex items-center gap-1.5 text-gray-400 hover:text-gray-600 text-sm transition-colors">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Customers
        </Link>
        <button
          onClick={() => setEditOpen(true)}
          className="btn btn-secondary inline-flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Edit
        </button>
      </div>

      <CustomerModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onSubmit={onEdit}
        submitting={saving}
        mode="edit"
        customer={customer}
      />

      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/30 to-violet-600/30 border border-indigo-200 flex items-center justify-center text-indigo-600 text-xl font-bold shrink-0">
          {customer.display_name[0]?.toUpperCase() ?? "?"}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{customer.display_name}</h1>
          {customer.company_name && <p className="text-gray-500 text-sm">{customer.company_name}</p>}
        </div>
      </div>

      <div className="space-y-4">
        <InfoSection title="Identity">
          <InfoField label="Display Name" value={customer.display_name} />
          <InfoField label="Company" value={customer.company_name} />
          <InfoField label="Given Name" value={[customer.title, customer.given_name, customer.middle_name, customer.family_name, customer.suffix].filter(Boolean).join(" ")} />
          <InfoField label="Print On Check" value={customer.print_on_check_name} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-0.5">Status</p>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${ss.cls}`}>{ss.label}</span>
          </div>
          <InfoField label="QBO ID" value={customer.qbo_id} />
        </InfoSection>

        <InfoSection title="Contact">
          <InfoField label="Primary Email" value={customer.primary_email} />
          <InfoField label="CC Email" value={customer.cc_email} />
          <InfoField label="BCC Email" value={customer.bcc_email} />
          <InfoField label="Phone" value={customer.phone_number} />
          <InfoField label="Mobile" value={customer.mobile} />
          <InfoField label="Fax" value={customer.fax} />
          <InfoField label="Website" value={customer.website} />
          <InfoField label="Other Contact" value={customer.other_contact} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-0.5">Attachment in Mail</p>
            <span className={`text-sm font-semibold ${customer.add_attachment_in_mail ? "text-emerald-700" : "text-gray-400"}`}>
              {customer.add_attachment_in_mail ? "Yes" : "No"}
            </span>
          </div>
        </InfoSection>

        <InfoSection title="Billing Address">
          <InfoField label="Line 1" value={customer.billing_line1} />
          <InfoField label="Line 2" value={customer.billing_line2} />
          <InfoField label="City" value={customer.billing_city} />
          <InfoField label="State" value={customer.billing_state} />
          <InfoField label="ZIP" value={customer.billing_zip} />
          <InfoField label="Country" value={customer.billing_country} />
        </InfoSection>

        {!customer.ship_same_as_billing && (
          <InfoSection title="Shipping Address">
            <InfoField label="Line 1" value={customer.shipping_line1} />
            <InfoField label="Line 2" value={customer.shipping_line2} />
            <InfoField label="City" value={customer.shipping_city} />
            <InfoField label="State" value={customer.shipping_state} />
            <InfoField label="ZIP" value={customer.shipping_zip} />
            <InfoField label="Country" value={customer.shipping_country} />
          </InfoSection>
        )}

        {customer.notes && (
          <InfoSection title="Notes">
            <div className="col-span-full">
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{customer.notes}</p>
            </div>
          </InfoSection>
        )}

        <InfoSection title="Timestamps">
          <InfoField label="Created" value={fmt(customer.created_at)} />
          <InfoField label="Updated" value={fmt(customer.updated_at)} />
          <InfoField label="QBO Last Updated" value={customer.qbo_last_updated ? fmt(customer.qbo_last_updated) : null} />
          <InfoField label="Last Pushed to QBO" value={customer.last_pushed_to_qbo_at ? fmt(customer.last_pushed_to_qbo_at) : null} />
        </InfoSection>
      </div>
    </div>
  );
}
