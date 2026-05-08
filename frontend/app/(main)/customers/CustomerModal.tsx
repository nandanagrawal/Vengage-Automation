"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CenterRow, CustomerAttachmentRow, CustomerRow, CustomerTypeRow, ProductAndServiceRow, ServiceCodeRow } from "@/lib/api";
import { apiDelete, apiDownloadBlob, apiGet, apiPatch, apiPost, downloadBlobAsFile } from "@/lib/api";

type CenterLine = { key: string; id?: number; name: string };

function newCenterLine(): CenterLine {
  const key =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { key, name: "" };
}

type ServiceRow = {
  key: string;
  product_and_service_id: number | "";
  service_code_id: number | "";
  rate: string;
};

function newServiceRow(): ServiceRow {
  const key =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `sr-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { key, product_and_service_id: "", service_code_id: "", rate: "" };
}

export type CustomerFormValues = {
  title: string;
  given_name: string;
  middle_name: string;
  family_name: string;
  suffix: string;
  company_name: string;
  display_name: string;
  primary_email: string;
  phone_number: string;
  cc_email: string;
  bcc_email: string;
  mobile: string;
  fax: string;
  other_contact: string;
  website: string;
  print_on_check_name: string;
  billing_line1: string;
  billing_line2: string;
  billing_line3: string;
  billing_line4: string;
  billing_city: string;
  billing_state: string;
  billing_zip: string;
  billing_country: string;
  ship_same_as_billing: boolean;
  shipping_line1: string;
  shipping_line2: string;
  shipping_line3: string;
  shipping_line4: string;
  shipping_city: string;
  shipping_state: string;
  shipping_zip: string;
  shipping_country: string;
  notes: string;
  add_attachment_in_mail: boolean;
};

const emptyForm = (): CustomerFormValues => ({
  title: "", given_name: "", middle_name: "", family_name: "", suffix: "",
  company_name: "", display_name: "", primary_email: "", phone_number: "",
  cc_email: "", bcc_email: "", mobile: "", fax: "", other_contact: "",
  website: "", print_on_check_name: "",
  billing_line1: "", billing_line2: "", billing_line3: "", billing_line4: "",
  billing_city: "", billing_state: "", billing_zip: "", billing_country: "",
  ship_same_as_billing: true,
  shipping_line1: "", shipping_line2: "", shipping_line3: "", shipping_line4: "",
  shipping_city: "", shipping_state: "", shipping_zip: "", shipping_country: "",
  notes: "", add_attachment_in_mail: false,
});

function customerToForm(c: CustomerRow): CustomerFormValues {
  return {
    title: c.title ?? "",
    given_name: c.given_name ?? "",
    middle_name: c.middle_name ?? "",
    family_name: c.family_name ?? "",
    suffix: c.suffix ?? "",
    company_name: c.company_name ?? "",
    display_name: c.display_name,
    primary_email: c.primary_email ?? "",
    phone_number: c.phone_number ?? "",
    cc_email: c.cc_email ?? "",
    bcc_email: c.bcc_email ?? "",
    mobile: c.mobile ?? "",
    fax: c.fax ?? "",
    other_contact: c.other_contact ?? "",
    website: c.website ?? "",
    print_on_check_name: c.print_on_check_name ?? "",
    billing_line1: c.billing_line1 ?? "",
    billing_line2: c.billing_line2 ?? "",
    billing_line3: c.billing_line3 ?? "",
    billing_line4: c.billing_line4 ?? "",
    billing_city: c.billing_city ?? "",
    billing_state: c.billing_state ?? "",
    billing_zip: c.billing_zip ?? "",
    billing_country: c.billing_country ?? "",
    ship_same_as_billing: c.ship_same_as_billing,
    shipping_line1: c.shipping_line1 ?? "",
    shipping_line2: c.shipping_line2 ?? "",
    shipping_line3: c.shipping_line3 ?? "",
    shipping_line4: c.shipping_line4 ?? "",
    shipping_city: c.shipping_city ?? "",
    shipping_state: c.shipping_state ?? "",
    shipping_zip: c.shipping_zip ?? "",
    shipping_country: c.shipping_country ?? "",
    notes: c.notes ?? "",
    add_attachment_in_mail: c.add_attachment_in_mail,
  };
}

function fieldCls() {
  return "w-full rounded-lg bg-white/[0.04] border border-white/[0.08] px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40";
}

function labelCls() {
  return "block text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1";
}

function Section({
  title, icon, open, onToggle, children,
}: {
  title: string; icon: ReactNode; open: boolean; onToggle: () => void; children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-white/[0.07] overflow-hidden" style={{ background: "var(--bg-card)" }}>
      <button type="button" onClick={onToggle} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.03]">
        <span className="flex items-center gap-2 text-sm font-semibold text-white">{icon}{title}</span>
        <span className="text-slate-500 text-xs">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="px-4 pb-4 pt-1 border-t border-white/[0.06]">{children}</div>}
    </div>
  );
}

function FileIcon() {
  return (
    <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  );
}

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
  onSubmit: (payload: Record<string, unknown>, files: File[]) => Promise<CustomerRow>;
  submitting: boolean;
  mode?: "create" | "edit";
  customer?: CustomerRow;
}) {
  const [form, setForm] = useState<CustomerFormValues>(emptyForm);
  const [files, setFiles] = useState<File[]>([]);
  const [existingAttachments, setExistingAttachments] = useState<CustomerAttachmentRow[]>([]);
  const [attachmentsLoading, setAttachmentsLoading] = useState(false);
  const [attachmentsLoadError, setAttachmentsLoadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [openName, setOpenName] = useState(true);
  const [openAddr, setOpenAddr] = useState(true);
  const [openNotes, setOpenNotes] = useState(true);
  const [openExtra, setOpenExtra] = useState(true);
  const [openCenters, setOpenCenters] = useState(true);
  const [centerLines, setCenterLines] = useState<CenterLine[]>([]);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<number[]>([]);
  const [centersLoadError, setCentersLoadError] = useState<string | null>(null);

  // Service rows
  const [serviceRows, setServiceRows] = useState<ServiceRow[]>([]);
  const [productOptions, setProductOptions] = useState<ProductAndServiceRow[]>([]);
  const [serviceCodeOptions, setServiceCodeOptions] = useState<ServiceCodeRow[]>([]);

  // Customer Types
  const [customerTypeOptions, setCustomerTypeOptions] = useState<CustomerTypeRow[]>([]);
  const [selectedCustomerTypeIds, setSelectedCustomerTypeIds] = useState<number[]>([]);
  const [newTypeName, setNewTypeName] = useState("");
  const [creatingType, setCreatingType] = useState(false);
  const [createTypeError, setCreateTypeError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && customer) {
      setForm(customerToForm(customer));
      setSelectedCustomerTypeIds(customer.customer_type_ids ?? []);
      setServiceRows(
        (customer.customer_services ?? []).map((cs) => ({
          key: `cs-${cs.id}`,
          product_and_service_id: cs.product_and_service_id,
          service_code_id: cs.service_code_id,
          rate: cs.rate,
        })),
      );
    } else {
      setForm(emptyForm());
      setSelectedCustomerTypeIds([]);
      setServiceRows([]);
    }
    setFiles([]);
    setExistingAttachments([]);
    setAttachmentsLoadError(null);
    setCenterLines([]);
    setPendingDeleteIds([]);
    setCentersLoadError(null);
    setNewTypeName("");
    setCreateTypeError(null);
  }, [open, mode, customer]);

  useEffect(() => {
    if (!open || mode !== "edit" || !customer?.id) return;
    let cancelled = false;
    setCentersLoadError(null);
    void apiGet<CenterRow[]>(`/customers/${customer.id}/centers`)
      .then((rows) => {
        if (!cancelled) {
          setCenterLines(rows.map((r) => ({ key: `saved-${r.id}`, id: r.id, name: r.name })));
          setPendingDeleteIds([]);
        }
      })
      .catch((e) => {
        if (!cancelled) setCentersLoadError(e instanceof Error ? e.message : "Failed to load centers");
      });
    return () => { cancelled = true; };
  }, [open, mode, customer?.id]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void apiGet<ProductAndServiceRow[]>("/product-and-services")
      .then((rows) => { if (!cancelled) setProductOptions(rows); })
      .catch(() => { /* non-fatal */ });
    void apiGet<ServiceCodeRow[]>("/service-codes")
      .then((rows) => { if (!cancelled) setServiceCodeOptions(rows); })
      .catch(() => { /* non-fatal */ });
    void apiGet<CustomerTypeRow[]>("/customer-types")
      .then((rows) => { if (!cancelled) setCustomerTypeOptions(rows); })
      .catch(() => { /* non-fatal */ });
    return () => { cancelled = true; };
  }, [open]);

  useEffect(() => {
    if (!open || mode !== "edit" || !customer?.id) {
      setExistingAttachments([]);
      setAttachmentsLoadError(null);
      setAttachmentsLoading(false);
      return;
    }
    let cancelled = false;
    setAttachmentsLoading(true);
    setAttachmentsLoadError(null);
    void apiGet<CustomerAttachmentRow[]>(`/customers/${customer.id}/attachments`)
      .then((rows) => { if (!cancelled) setExistingAttachments(rows); })
      .catch((e) => { if (!cancelled) setAttachmentsLoadError(e instanceof Error ? e.message : "Failed to load attachments"); })
      .finally(() => { if (!cancelled) setAttachmentsLoading(false); });
    return () => { cancelled = true; };
  }, [open, mode, customer?.id]);

  const displayPreview = useMemo(() => {
    const parts = [form.title, form.given_name, form.middle_name, form.family_name, form.suffix].filter(Boolean);
    return parts.join(" ").trim() || form.company_name || "";
  }, [form]);

  const update = <K extends keyof CustomerFormValues>(key: K, v: CustomerFormValues[K]) =>
    setForm((s) => ({ ...s, [key]: v }));

  const addFiles = (incoming: File[]) => {
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      return [...prev, ...incoming.filter((f) => !existing.has(f.name + f.size))];
    });
  };

  const removeFile = (idx: number) => setFiles((fs) => fs.filter((_, i) => i !== idx));

  const removeCenterLine = (line: CenterLine) => {
    if (line.id) setPendingDeleteIds((p) => [...p, line.id!]);
    setCenterLines((rows) => rows.filter((r) => r.key !== line.key));
  };

  const updateServiceRow = (key: string, patch: Partial<ServiceRow>) => {
    setServiceRows((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  };

  const removeServiceRow = (key: string) => {
    setServiceRows((rows) => rows.filter((r) => r.key !== key));
  };

  // Products already selected in other rows (for duplicate prevention)
  const usedProductIds = useMemo(
    () => new Set(serviceRows.map((r) => r.product_and_service_id).filter((id) => id !== "")),
    [serviceRows],
  );

  const resetAndClose = () => {
    setForm(emptyForm());
    setFiles([]);
    setExistingAttachments([]);
    setAttachmentsLoadError(null);
    setCenterLines([]);
    setPendingDeleteIds([]);
    setCentersLoadError(null);
    setServiceRows([]);
    setSelectedCustomerTypeIds([]);
    setNewTypeName("");
    setCreateTypeError(null);
    onClose();
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.display_name.trim()) return;

    const billing: Record<string, string | undefined> = {
      line1: form.billing_line1 || undefined, line2: form.billing_line2 || undefined,
      line3: form.billing_line3 || undefined, line4: form.billing_line4 || undefined,
      city: form.billing_city || undefined, state: form.billing_state || undefined,
      zip: form.billing_zip || undefined, country: form.billing_country || undefined,
    };
    const hasBilling = Object.values(billing).some(Boolean);

    const shipping: Record<string, string | undefined> = {
      line1: form.shipping_line1 || undefined, line2: form.shipping_line2 || undefined,
      line3: form.shipping_line3 || undefined, line4: form.shipping_line4 || undefined,
      city: form.shipping_city || undefined, state: form.shipping_state || undefined,
      zip: form.shipping_zip || undefined, country: form.shipping_country || undefined,
    };
    const hasShip = Object.values(shipping).some(Boolean);

    const validServices = serviceRows
      .filter((r) => r.product_and_service_id !== "" && r.service_code_id !== "" && parseFloat(r.rate) > 0)
      .map((r) => ({
        product_and_service_id: r.product_and_service_id as number,
        service_code_id: r.service_code_id as number,
        rate: r.rate,
      }));

    const payload: Record<string, unknown> = {
      title: form.title || undefined,
      given_name: form.given_name || undefined,
      middle_name: form.middle_name || undefined,
      family_name: form.family_name || undefined,
      suffix: form.suffix || undefined,
      company_name: form.company_name || undefined,
      display_name: form.display_name.trim(),
      primary_email: form.primary_email || undefined,
      phone_number: form.phone_number || undefined,
      cc_email: form.cc_email || undefined,
      bcc_email: form.bcc_email || undefined,
      mobile: form.mobile || undefined,
      fax: form.fax || undefined,
      other_contact: form.other_contact || undefined,
      website: form.website || undefined,
      print_on_check_name: form.print_on_check_name || undefined,
      ship_same_as_billing: form.ship_same_as_billing,
      billing: hasBilling ? billing : undefined,
      shipping: !form.ship_same_as_billing && hasShip ? shipping : undefined,
      notes: form.notes || undefined,
      add_attachment_in_mail: form.add_attachment_in_mail,
      customer_services: validServices,
      customer_type_ids: selectedCustomerTypeIds,
    };

    try {
      const savedCustomer = await onSubmit(payload, files);
      const cid = savedCustomer.id;
      try {
        for (const did of pendingDeleteIds) {
          await apiDelete(`/customers/${cid}/centers/${did}`);
        }
        for (const line of centerLines) {
          const n = line.name.trim();
          if (!n) continue;
          if (line.id) {
            await apiPatch(`/customers/${cid}/centers/${line.id}`, { name: n });
          } else {
            await apiPost(`/customers/${cid}/centers`, { name: n });
          }
        }
      } catch (e) {
        setCentersLoadError(e instanceof Error ? e.message : "Failed to save centers");
        return;
      }
      resetAndClose();
    } catch {
      /* parent surfaces customer save error */
    }
  };

  if (!open) return null;

  const activeProducts = productOptions.filter((p) => p.active);
  const activeServiceCodes = serviceCodeOptions.filter((sc) => sc.status);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeInUp">
      <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl border border-white/[0.1] shadow-2xl" style={{ background: "var(--bg-deep)" }}>
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-[rgba(15,18,32,0.95)]">
          <div>
            <h2 className="text-lg font-bold text-white">{mode === "edit" ? "Edit Customer" : "Add Customer"}</h2>
            <p className="text-xs text-slate-500 mt-0.5">Aligned with QuickBooks Online — Name, addresses, notes, and app extensions.</p>
          </div>
          <button type="button" onClick={resetAndClose} className="text-slate-400 hover:text-white text-sm">Close</button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* ── Name and contact ── */}
          <Section title="Name and contact" open={openName} onToggle={() => setOpenName(!openName)} icon={<span className="text-indigo-400">◎</span>}>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-3">
              {([
                ["Title", "title", form.title],
                ["First name", "given_name", form.given_name],
                ["Middle name", "middle_name", form.middle_name],
                ["Last name", "family_name", form.family_name],
                ["Suffix", "suffix", form.suffix],
              ] as const).map(([lab, key, val]) => (
                <div key={key}>
                  <label className={labelCls()}>{lab}</label>
                  <input className={fieldCls()} value={val} onChange={(e) => update(key, e.target.value)} />
                </div>
              ))}
            </div>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <div>
                <label className={labelCls()}>Company name</label>
                <input className={fieldCls()} value={form.company_name} onChange={(e) => update("company_name", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>Customer display name <span className="text-rose-400">*</span></label>
                <input required className={fieldCls()} value={form.display_name} onChange={(e) => update("display_name", e.target.value)} placeholder={displayPreview || "Required"} />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <div>
                <label className={labelCls()}>Email</label>
                <input type="email" className={fieldCls()} value={form.primary_email} onChange={(e) => update("primary_email", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>Phone number</label>
                <input className={fieldCls()} value={form.phone_number} onChange={(e) => update("phone_number", e.target.value)} />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <div>
                <label className={labelCls()}>Cc</label>
                <input className={fieldCls()} value={form.cc_email} onChange={(e) => update("cc_email", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>Bcc</label>
                <input className={fieldCls()} value={form.bcc_email} onChange={(e) => update("bcc_email", e.target.value)} />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-3 mb-3">
              <div>
                <label className={labelCls()}>Mobile number</label>
                <input className={fieldCls()} value={form.mobile} onChange={(e) => update("mobile", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>Fax</label>
                <input className={fieldCls()} value={form.fax} onChange={(e) => update("fax", e.target.value)} />
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-3">
              <div>
                <label className={labelCls()}>Other</label>
                <input className={fieldCls()} value={form.other_contact} onChange={(e) => update("other_contact", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>Website</label>
                <input className={fieldCls()} value={form.website} onChange={(e) => update("website", e.target.value)} />
              </div>
            </div>
            <div className="mt-3">
              <label className={labelCls()}>Name to print on checks</label>
              <input className={fieldCls()} value={form.print_on_check_name} onChange={(e) => update("print_on_check_name", e.target.value)} />
            </div>
          </Section>

          <Section
            title="Company centers"
            open={openCenters}
            onToggle={() => setOpenCenters(!openCenters)}
            icon={<span className="text-sky-400">⌁</span>}
          >
            <p className="text-[11px] text-slate-600 mb-2">
              Add one or more centers for this company. They are saved with the customer and can be combined on invoices.
            </p>
            {centersLoadError && <p className="text-xs text-rose-400 mb-2">{centersLoadError}</p>}
            <div className="space-y-2">
              {centerLines.map((line) => (
                <div key={line.key} className="flex gap-2 items-center">
                  <input
                    className={fieldCls()}
                    value={line.name}
                    onChange={(e) =>
                      setCenterLines((rows) =>
                        rows.map((r) => (r.key === line.key ? { ...r, name: e.target.value } : r)),
                      )
                    }
                    placeholder="Center name"
                  />
                  <button
                    type="button"
                    onClick={() => removeCenterLine(line)}
                    className="shrink-0 text-slate-500 hover:text-red-400 px-2 text-sm"
                    aria-label="Remove center"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="mt-3 text-sm font-semibold text-indigo-400 hover:text-indigo-300"
              onClick={() => setCenterLines((rows) => [...rows, newCenterLine()])}
            >
              Add Center
            </button>
          </Section>

          {/* ── Addresses ── */}
          <Section title="Addresses" open={openAddr} onToggle={() => setOpenAddr(!openAddr)} icon={<span className="text-emerald-400">📍</span>}>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Billing address</p>
            <div className="grid md:grid-cols-2 gap-3 mb-2">
              <div className="md:col-span-2">
                <label className={labelCls()}>Street address 1</label>
                <input className={fieldCls()} value={form.billing_line1} onChange={(e) => update("billing_line1", e.target.value)} />
              </div>
              <div className="md:col-span-2">
                <label className={labelCls()}>Street address 2</label>
                <input className={fieldCls()} value={form.billing_line2} onChange={(e) => update("billing_line2", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>City</label>
                <input className={fieldCls()} value={form.billing_city} onChange={(e) => update("billing_city", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>State</label>
                <input className={fieldCls()} value={form.billing_state} onChange={(e) => update("billing_state", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>ZIP code</label>
                <input className={fieldCls()} value={form.billing_zip} onChange={(e) => update("billing_zip", e.target.value)} />
              </div>
              <div>
                <label className={labelCls()}>Country</label>
                <input className={fieldCls()} value={form.billing_country} onChange={(e) => update("billing_country", e.target.value)} />
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-300 mt-4 mb-2 cursor-pointer">
              <input type="checkbox" className="rounded border-white/20" checked={form.ship_same_as_billing} onChange={(e) => update("ship_same_as_billing", e.target.checked)} />
              Same as billing address
            </label>

            {!form.ship_same_as_billing && (
              <div className="grid md:grid-cols-2 gap-3">
                <p className="md:col-span-2 text-xs font-bold text-slate-500 uppercase tracking-wider">Shipping address</p>
                <div className="md:col-span-2">
                  <label className={labelCls()}>Street address 1</label>
                  <input className={fieldCls()} value={form.shipping_line1} onChange={(e) => update("shipping_line1", e.target.value)} />
                </div>
                <div className="md:col-span-2">
                  <label className={labelCls()}>Street address 2</label>
                  <input className={fieldCls()} value={form.shipping_line2} onChange={(e) => update("shipping_line2", e.target.value)} />
                </div>
                <div>
                  <label className={labelCls()}>City</label>
                  <input className={fieldCls()} value={form.shipping_city} onChange={(e) => update("shipping_city", e.target.value)} />
                </div>
                <div>
                  <label className={labelCls()}>State</label>
                  <input className={fieldCls()} value={form.shipping_state} onChange={(e) => update("shipping_state", e.target.value)} />
                </div>
                <div>
                  <label className={labelCls()}>ZIP code</label>
                  <input className={fieldCls()} value={form.shipping_zip} onChange={(e) => update("shipping_zip", e.target.value)} />
                </div>
                <div>
                  <label className={labelCls()}>Country</label>
                  <input className={fieldCls()} value={form.shipping_country} onChange={(e) => update("shipping_country", e.target.value)} />
                </div>
              </div>
            )}
          </Section>

          {/* ── Notes & Attachments ── */}
          <Section title="Notes and attachments" open={openNotes} onToggle={() => setOpenNotes(!openNotes)} icon={<span className="text-amber-400">✎</span>}>
            <label className={labelCls()}>Notes</label>
            <textarea rows={3} className={`${fieldCls()} resize-y mb-4`} value={form.notes} onChange={(e) => update("notes", e.target.value)} />

            {mode === "edit" && customer?.id && (
              <div className="mb-4">
                <p className={labelCls()}>Saved on this platform</p>
                {attachmentsLoading && <p className="text-xs text-slate-600 py-2">Loading attachments…</p>}
                {attachmentsLoadError && <p className="text-xs text-rose-400 py-1">{attachmentsLoadError}</p>}
                {!attachmentsLoading && !attachmentsLoadError && (
                  <p className="text-[11px] text-slate-600 mb-2">
                    Deletions in QuickBooks are removed here after you run <span className="text-slate-400">Sync</span> on
                    the customers page.
                  </p>
                )}
                {!attachmentsLoading && !attachmentsLoadError && existingAttachments.length === 0 && (
                  <p className="text-xs text-slate-600 py-1">
                    No files stored yet. Upload below — we keep a copy here and send to QuickBooks.
                  </p>
                )}
                {existingAttachments.length > 0 && (
                  <ul className="mt-2 space-y-1.5">
                    {existingAttachments.map((a) => (
                      <li
                        key={a.id}
                        className="flex items-center justify-between gap-2 py-1.5 px-3 rounded-lg bg-white/[0.04] border border-white/[0.06]"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileIcon />
                          <span className="text-sm text-slate-300 truncate">{a.original_filename}</span>
                          <span className="text-xs text-slate-600 shrink-0">
                            {a.size_bytes < 1024 ? `${a.size_bytes} B` : `${(a.size_bytes / 1024).toFixed(0)} KB`}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="text-xs font-medium text-indigo-400 hover:text-indigo-300 shrink-0"
                          onClick={async () => {
                            try {
                              const blob = await apiDownloadBlob(
                                `/customers/${customer.id}/attachments/${a.id}/file`,
                              );
                              downloadBlobAsFile(blob, a.original_filename);
                            } catch { /* ignore */ }
                          }}
                        >
                          Download
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <p className={labelCls()}>Upload files (QuickBooks + local copy)</p>
            <div
              className={`rounded-xl border-2 border-dashed px-4 py-6 text-center cursor-pointer transition-colors ${dragOver ? "border-indigo-500/60 bg-indigo-500/5" : "border-white/[0.12] hover:border-indigo-500/40 hover:bg-white/[0.02]"}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(Array.from(e.dataTransfer.files)); }}
            >
              <svg className="w-7 h-7 mx-auto mb-2 text-slate-600" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <p className="text-sm text-slate-400">Drag & drop files here, or <span className="text-indigo-400 underline">browse</span></p>
              <p className="text-xs text-slate-600 mt-1">PDFs, images, spreadsheets — stored here and attached in QuickBooks</p>
              {mode === "create" && <p className="text-xs text-slate-700 mt-1">Files upload after customer is approved in QBO</p>}
              <input ref={fileInputRef} type="file" multiple className="hidden" onChange={(e) => { addFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
            </div>

            {files.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-white/[0.04] border border-white/[0.06]">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileIcon />
                      <span className="text-sm text-slate-300 truncate">{f.name}</span>
                      <span className="text-xs text-slate-600 shrink-0">{f.size < 1024 ? `${f.size} B` : `${(f.size / 1024).toFixed(0)} KB`}</span>
                    </div>
                    <button type="button" onClick={() => removeFile(i)} className="text-slate-600 hover:text-red-400 transition-colors ml-2 text-sm">✕</button>
                  </div>
                ))}
              </div>
            )}
          </Section>

          {/* ── App fields ── */}
          <Section title="App fields" open={openExtra} onToggle={() => setOpenExtra(!openExtra)} icon={<span className="text-violet-400">⚙</span>}>

            {/* Services table */}
            <div className="mb-5">
              <label className={labelCls()}>Services &amp; rates</label>
              <p className="text-[11px] text-slate-600 mb-2">
                Select a product/service, set the rate, and pick a service code. Rate must be &gt; 0. Each service can only appear once.
              </p>

              {serviceRows.length > 0 && (
                <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] overflow-hidden mb-2">
                  {/* Header */}
                  <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.5fr)_2rem] gap-2 px-3 py-2 border-b border-white/[0.06]">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Service</span>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Rate</span>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Service Code</span>
                    <span />
                  </div>
                  <div className="divide-y divide-white/[0.04]">
                    {serviceRows.map((row) => (
                      <div key={row.key} className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.5fr)_2rem] gap-2 px-3 py-2 items-center">
                        {/* Product dropdown */}
                        <select
                          value={row.product_and_service_id === "" ? "" : String(row.product_and_service_id)}
                          onChange={(e) => {
                            const v = e.target.value;
                            updateServiceRow(row.key, { product_and_service_id: v === "" ? "" : Number(v) });
                          }}
                          className="rounded-lg bg-[#1a1d2e] border border-white/[0.08] px-2 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/40 appearance-none"
                        >
                          <option value="" style={{ background: "#1a1d2e", color: "#94a3b8" }}>Select…</option>
                          {activeProducts.map((p) => {
                            const isUsedElsewhere = usedProductIds.has(p.id) && row.product_and_service_id !== p.id;
                            return (
                              <option
                                key={p.id}
                                value={p.id}
                                disabled={isUsedElsewhere}
                                style={{ background: "#1a1d2e", color: isUsedElsewhere ? "#64748b" : "#f1f5f9" }}
                              >
                                {p.name}
                              </option>
                            );
                          })}
                        </select>

                        {/* Rate */}
                        <input
                          type="number"
                          min="0.0001"
                          step="0.0001"
                          placeholder="0.00"
                          value={row.rate}
                          onChange={(e) => updateServiceRow(row.key, { rate: e.target.value })}
                          className="rounded-lg bg-[#1a1d2e] border border-white/[0.08] px-2 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/40"
                        />

                        {/* Service code dropdown */}
                        <select
                          value={row.service_code_id === "" ? "" : String(row.service_code_id)}
                          onChange={(e) => {
                            const v = e.target.value;
                            updateServiceRow(row.key, { service_code_id: v === "" ? "" : Number(v) });
                          }}
                          className="rounded-lg bg-[#1a1d2e] border border-white/[0.08] px-2 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500/40 appearance-none"
                        >
                          <option value="" style={{ background: "#1a1d2e", color: "#94a3b8" }}>Select…</option>
                          {activeServiceCodes.map((sc) => (
                            <option key={sc.id} value={sc.id} style={{ background: "#1a1d2e", color: "#f1f5f9" }}>
                              {sc.code}
                            </option>
                          ))}
                        </select>

                        {/* Remove */}
                        <button
                          type="button"
                          onClick={() => removeServiceRow(row.key)}
                          className="text-slate-600 hover:text-red-400 text-sm transition-colors"
                          aria-label="Remove service row"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                type="button"
                className="text-sm font-semibold text-indigo-400 hover:text-indigo-300"
                onClick={() => setServiceRows((rows) => [...rows, newServiceRow()])}
              >
                + Add service
              </button>

              {activeProducts.length === 0 && (
                <p className="text-[11px] text-amber-400/80 mt-1.5">No active products found — run Sync to pull from QuickBooks.</p>
              )}
              {activeServiceCodes.length === 0 && (
                <p className="text-[11px] text-amber-400/80 mt-1">No active service codes — add them in Configuration → Service Code.</p>
              )}
            </div>

            {/* Customer Types */}
            <div className="mb-4">
              <label className={labelCls()}>Customer types</label>
              {createTypeError && <p className="text-xs text-rose-400 mb-1">{createTypeError}</p>}
              {(() => {
                const assignedIds = new Set(selectedCustomerTypeIds);
                const visibleTypes = mode === "edit"
                  ? customerTypeOptions.filter((ct) => ct.status || assignedIds.has(ct.id))
                  : customerTypeOptions.filter((ct) => ct.status);
                return (
                  <>
                    {visibleTypes.length === 0 && (
                      <p className="text-xs text-slate-600 py-1">No active customer types. Create one below.</p>
                    )}
                    {visibleTypes.length > 0 && (
                      <div className="max-h-36 overflow-y-auto rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2 space-y-1.5 mb-2">
                        {visibleTypes.map((ct) => (
                          <label
                            key={ct.id}
                            className={`flex items-center gap-2.5 text-sm ${ct.status ? "cursor-pointer text-slate-300" : "cursor-pointer text-slate-500"}`}
                          >
                            <input
                              type="checkbox"
                              className="rounded border-white/20"
                              checked={selectedCustomerTypeIds.includes(ct.id)}
                              onChange={(e) => {
                                setSelectedCustomerTypeIds((prev) =>
                                  e.target.checked ? [...prev, ct.id] : prev.filter((id) => id !== ct.id),
                                );
                              }}
                            />
                            <span className={ct.status ? "" : "line-through"}>{ct.name}</span>
                            {!ct.status && (
                              <span className="text-[9px] font-semibold uppercase tracking-wide text-slate-600 border border-white/[0.08] px-1 py-0.5 rounded">
                                inactive
                              </span>
                            )}
                          </label>
                        ))}
                      </div>
                    )}
                    {/* Inline create */}
                    <div className="flex gap-2 items-center">
                      <input
                        className="flex-1 rounded-lg bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                        placeholder="New type name…"
                        value={newTypeName}
                        onChange={(e) => setNewTypeName(e.target.value)}
                        onKeyDown={async (e) => {
                          if (e.key !== "Enter") return;
                          e.preventDefault();
                          const name = newTypeName.trim();
                          if (!name || creatingType) return;
                          setCreatingType(true);
                          setCreateTypeError(null);
                          try {
                            const created = await apiPost<CustomerTypeRow>("/customer-types", { name });
                            setCustomerTypeOptions((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
                            setSelectedCustomerTypeIds((prev) => [...prev, created.id]);
                            setNewTypeName("");
                          } catch (err) {
                            setCreateTypeError(err instanceof Error ? err.message : "Failed to create type");
                          } finally {
                            setCreatingType(false);
                          }
                        }}
                        maxLength={255}
                      />
                      <button
                        type="button"
                        disabled={!newTypeName.trim() || creatingType}
                        className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 disabled:opacity-40 shrink-0"
                        onClick={async () => {
                          const name = newTypeName.trim();
                          if (!name || creatingType) return;
                          setCreatingType(true);
                          setCreateTypeError(null);
                          try {
                            const created = await apiPost<CustomerTypeRow>("/customer-types", { name });
                            setCustomerTypeOptions((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
                            setSelectedCustomerTypeIds((prev) => [...prev, created.id]);
                            setNewTypeName("");
                          } catch (err) {
                            setCreateTypeError(err instanceof Error ? err.message : "Failed to create type");
                          } finally {
                            setCreatingType(false);
                          }
                        }}
                      >
                        {creatingType ? "Adding…" : "+ Add"}
                      </button>
                    </div>
                    <p className="text-[10px] text-slate-700 mt-1">Press Enter or click + Add to create a new type inline.</p>
                  </>
                );
              })()}
            </div>

            {/* Mail attachment toggle */}
            <div>
              <label className={labelCls()}>Mail attachment</label>
              <label className="flex items-center gap-2.5 cursor-pointer mt-2">
                <div
                  className={`relative w-10 h-5 rounded-full transition-colors ${form.add_attachment_in_mail ? "bg-indigo-600" : "bg-white/10"}`}
                  onClick={() => update("add_attachment_in_mail", !form.add_attachment_in_mail)}
                >
                  <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${form.add_attachment_in_mail ? "translate-x-5" : "translate-x-0"}`} />
                </div>
                <span className="text-sm text-slate-300">Add attachment in mail</span>
              </label>
              <p className="text-[11px] text-slate-600 mt-1.5">Auto-attach Excel/PDF when sending invoices.</p>
            </div>
          </Section>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={resetAndClose} className="px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white">Cancel</button>
            <button type="submit" disabled={submitting} className="shimmer-btn px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50">
              {submitting ? "Saving…" : mode === "edit" ? "Save changes" : "Save customer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
