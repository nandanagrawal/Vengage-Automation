"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import type { CenterRow, CustomerRow, CustomerTypeRow, PricingType, ProductAndServiceRow } from "@/lib/api";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";

// ── Shared types ────────────────────────────────────────────────────────────

export type CenterLine = { key: string; id?: number; name: string };

function newCenterLine(): CenterLine {
  const key =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { key, name: "" };
}

export type SlabLine = { key: string; range_start: string; range_end: string; rate: string };

function newSlabLine(): SlabLine {
  const key =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `sl-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { key, range_start: "", range_end: "", rate: "" };
}

export type ServiceRow = {
  key: string;
  product_and_service_id: number | "";
  pricing_type: PricingType;
  rate: string;        // used when pricing_type === "flat"
  slabs: SlabLine[];   // used when pricing_type === "slab"
};

function newServiceRow(): ServiceRow {
  const key =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `sr-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { key, product_and_service_id: "", pricing_type: "flat", rate: "", slabs: [] };
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
  payment_terms_days: string;
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
  notes: "", add_attachment_in_mail: false, payment_terms_days: "15",
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
    payment_terms_days: String(c.payment_terms_days ?? 15),
  };
}

export function fieldCls() {
  return "w-full rounded-lg bg-gray-50 border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-200";
}

export function labelCls() {
  return "block text-[11px] font-semibold uppercase tracking-wide text-gray-400 mb-1";
}

function Section({
  title, icon, open, onToggle, children,
}: {
  title: string; icon: ReactNode; open: boolean; onToggle: () => void; children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden" style={{ background: "var(--bg-card)" }}>
      <button type="button" onClick={onToggle} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50">
        <span className="flex items-center gap-2 text-sm font-semibold text-gray-900">{icon}{title}</span>
        <span className="text-gray-400 text-xs">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="px-4 pb-4 pt-1 border-t border-gray-200">{children}</div>}
    </div>
  );
}

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const validateEmailList = (val: string) =>
  val.split(",").map((e) => e.trim()).filter(Boolean).every((e) => emailRegex.test(e));

// ── Hook: owns all form state + submit logic ─────────────────────────────────

export function useCustomerForm(mode: "create" | "edit", customer: CustomerRow | undefined, active: boolean) {
  const [form, setForm] = useState<CustomerFormValues>(emptyForm);
  const [openName, setOpenName] = useState(true);
  const [openAddr, setOpenAddr] = useState(true);
  const [openNotes, setOpenNotes] = useState(true);
  const [openExtra, setOpenExtra] = useState(true);
  const [openCenters, setOpenCenters] = useState(true);
  const [centerLines, setCenterLines] = useState<CenterLine[]>([]);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<number[]>([]);
  const [centersLoadError, setCentersLoadError] = useState<string | null>(null);

  const [serviceRows, setServiceRows] = useState<ServiceRow[]>([]);
  const [productOptions, setProductOptions] = useState<ProductAndServiceRow[]>([]);
  const [serviceError, setServiceError] = useState<string | null>(null);

  const [customerTypeOptions, setCustomerTypeOptions] = useState<CustomerTypeRow[]>([]);
  const [selectedCustomerTypeIds, setSelectedCustomerTypeIds] = useState<number[]>([]);
  const [newTypeName, setNewTypeName] = useState("");
  const [creatingType, setCreatingType] = useState(false);
  const [createTypeError, setCreateTypeError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return;
    if (mode === "edit" && customer) {
      setForm(customerToForm(customer));
      setSelectedCustomerTypeIds(customer.customer_type_ids ?? []);
      setServiceRows(
        (customer.customer_services ?? []).map((cs) => ({
          key: `cs-${cs.id}`,
          product_and_service_id: cs.product_and_service_id,
          pricing_type: cs.pricing_type,
          rate: cs.rate != null ? parseFloat(String(cs.rate)).toFixed(2) : "",
          slabs: (cs.slabs ?? []).map((s) => ({
            key: `slab-${s.id}`,
            range_start: String(s.range_start),
            range_end: s.range_end != null ? String(s.range_end) : "",
            rate: parseFloat(String(s.rate)).toFixed(2),
          })),
        })),
      );
    } else {
      setForm(emptyForm());
      setSelectedCustomerTypeIds([]);
      setServiceRows([]);
    }
    setCenterLines([]);
    setPendingDeleteIds([]);
    setCentersLoadError(null);
    setNewTypeName("");
    setCreateTypeError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, mode, customer]);

  useEffect(() => {
    if (!active || mode !== "edit" || !customer?.id) return;
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
  }, [active, mode, customer?.id]);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    void apiGet<ProductAndServiceRow[]>("/product-and-services")
      .then((rows) => { if (!cancelled) setProductOptions(rows); })
      .catch(() => { /* non-fatal */ });
    void apiGet<CustomerTypeRow[]>("/customer-types")
      .then((rows) => { if (!cancelled) setCustomerTypeOptions(rows); })
      .catch(() => { /* non-fatal */ });
    return () => { cancelled = true; };
  }, [active]);

  const displayPreview = useMemo(() => {
    const parts = [form.title, form.given_name, form.middle_name, form.family_name, form.suffix].filter(Boolean);
    return parts.join(" ").trim() || form.company_name || "";
  }, [form]);

  const update = <K extends keyof CustomerFormValues>(key: K, v: CustomerFormValues[K]) =>
    setForm((s) => ({ ...s, [key]: v }));

  const removeCenterLine = (line: CenterLine) => {
    if (line.id) setPendingDeleteIds((p) => [...p, line.id!]);
    setCenterLines((rows) => rows.filter((r) => r.key !== line.key));
  };

  const updateServiceRow = (key: string, patch: Partial<ServiceRow>) => {
    setServiceRows((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));
    setServiceError(null);
  };

  const removeServiceRow = (key: string) => {
    setServiceRows((rows) => rows.filter((r) => r.key !== key));
  };

  const addSlabLine = (rowKey: string) => {
    setServiceRows((rows) =>
      rows.map((r) => (r.key === rowKey ? { ...r, slabs: [...r.slabs, newSlabLine()] } : r)),
    );
    setServiceError(null);
  };

  const updateSlabLine = (rowKey: string, slabKey: string, patch: Partial<SlabLine>) => {
    setServiceRows((rows) =>
      rows.map((r) =>
        r.key === rowKey
          ? { ...r, slabs: r.slabs.map((s) => (s.key === slabKey ? { ...s, ...patch } : s)) }
          : r,
      ),
    );
    setServiceError(null);
  };

  const removeSlabLine = (rowKey: string, slabKey: string) => {
    setServiceRows((rows) =>
      rows.map((r) => (r.key === rowKey ? { ...r, slabs: r.slabs.filter((s) => s.key !== slabKey) } : r)),
    );
  };

  const usedProductIds = useMemo(
    () => new Set(serviceRows.map((r) => r.product_and_service_id).filter((id) => id !== "")),
    [serviceRows],
  );

  const reset = () => {
    setForm(emptyForm());
    setCenterLines([]);
    setPendingDeleteIds([]);
    setCentersLoadError(null);
    setServiceRows([]);
    setServiceError(null);
    setSelectedCustomerTypeIds([]);
    setNewTypeName("");
    setCreateTypeError(null);
  };

  /** Validate, build the payload, call onSubmit, then sync centers.
   * Returns the saved customer on success, or null if validation failed
   * (in which case an error has already been surfaced via state/alert). */
  const submit = async (
    onSubmit: (payload: Record<string, unknown>) => Promise<CustomerRow>,
  ): Promise<CustomerRow | null> => {
    if (!form.display_name.trim()) return null;
    if (form.primary_email && !validateEmailList(form.primary_email)) {
      alert("Invalid email address(es) in Email field. Separate multiple emails with commas.");
      return null;
    }
    if (form.cc_email && !validateEmailList(form.cc_email)) {
      alert("Invalid email address(es) in Cc field. Separate multiple emails with commas.");
      return null;
    }
    if (form.bcc_email && !validateEmailList(form.bcc_email)) {
      alert("Invalid email address(es) in Bcc field. Separate multiple emails with commas.");
      return null;
    }
    const paymentTermsDays = parseInt(form.payment_terms_days, 10);
    if (!Number.isFinite(paymentTermsDays) || paymentTermsDays <= 0) {
      alert("Payment terms (days) must be a whole number greater than 0.");
      return null;
    }

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

    // Validate service rows: flat needs a rate > 0; slab needs >=1 range, each with a positive rate.
    const rowsWithProduct = serviceRows.filter((r) => r.product_and_service_id !== "");
    const badFlat = rowsWithProduct.find(
      (r) => r.pricing_type === "flat" && !(parseFloat(r.rate) > 0),
    );
    if (badFlat) {
      setServiceError("Rate cannot be blank — enter a rate greater than 0 for each flat-priced service.");
      return null;
    }
    const badSlab = rowsWithProduct.find((r) => {
      if (r.pricing_type !== "slab") return false;
      if (r.slabs.length === 0) return true;
      return r.slabs.some((s) => !(parseFloat(s.range_start) >= 1) || !(parseFloat(s.rate) > 0));
    });
    if (badSlab) {
      setServiceError("Each slab service needs at least one range — Start (≥1) and Rate (>0) are required for every range.");
      return null;
    }
    // Overlap check per slab-priced row.
    for (const r of rowsWithProduct) {
      if (r.pricing_type !== "slab") continue;
      const tiers = [...r.slabs]
        .map((s) => ({ start: parseFloat(s.range_start), end: s.range_end ? parseFloat(s.range_end) : null }))
        .sort((a, b) => a.start - b.start);
      for (let i = 1; i < tiers.length; i++) {
        const prev = tiers[i - 1];
        const cur = tiers[i];
        if (prev.end === null || cur.start <= prev.end) {
          setServiceError("Slab ranges overlap — check the Start/End values for this service.");
          return null;
        }
      }
    }
    setServiceError(null);

    const validServices = rowsWithProduct.map((r) =>
      r.pricing_type === "flat"
        ? { product_and_service_id: r.product_and_service_id as number, pricing_type: "flat", rate: r.rate }
        : {
            product_and_service_id: r.product_and_service_id as number,
            pricing_type: "slab",
            slabs: r.slabs.map((s) => ({
              range_start: Math.trunc(parseFloat(s.range_start)),
              range_end: s.range_end ? Math.trunc(parseFloat(s.range_end)) : null,
              rate: s.rate,
            })),
          },
    );

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
      payment_terms_days: paymentTermsDays,
      customer_services: validServices,
      customer_type_ids: selectedCustomerTypeIds,
    };

    const savedCustomer = await onSubmit(payload);
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
      return null;
    }
    return savedCustomer;
  };

  return {
    form, update, displayPreview,
    openName, setOpenName, openAddr, setOpenAddr, openNotes, setOpenNotes,
    openExtra, setOpenExtra, openCenters, setOpenCenters,
    centerLines, setCenterLines, removeCenterLine, centersLoadError,
    serviceRows, setServiceRows, productOptions, serviceError,
    updateServiceRow, removeServiceRow, addSlabLine, updateSlabLine, removeSlabLine,
    usedProductIds,
    customerTypeOptions, setCustomerTypeOptions,
    selectedCustomerTypeIds, setSelectedCustomerTypeIds,
    newTypeName, setNewTypeName, creatingType, setCreatingType, createTypeError, setCreateTypeError,
    reset, submit,
  };
}

export type CustomerFormApi = ReturnType<typeof useCustomerForm>;

// ── Presentational fields (shared by the modal and the edit page) ────────────

export function CustomerFormFields({ api, mode }: { api: CustomerFormApi; mode: "create" | "edit" }) {
  const {
    form, update, displayPreview,
    openName, setOpenName, openAddr, setOpenAddr, openNotes, setOpenNotes,
    openExtra, setOpenExtra, openCenters, setOpenCenters,
    centerLines, setCenterLines, removeCenterLine, centersLoadError,
    serviceRows, productOptions, serviceError,
    updateServiceRow, removeServiceRow, addSlabLine, updateSlabLine, removeSlabLine,
    usedProductIds,
    customerTypeOptions, setCustomerTypeOptions,
    selectedCustomerTypeIds, setSelectedCustomerTypeIds,
    newTypeName, setNewTypeName, creatingType, setCreatingType, createTypeError, setCreateTypeError,
  } = api;

  const activeProducts = productOptions.filter((p) => p.active);

  const createType = async () => {
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
  };

  return (
    <>
      {/* ── Name and contact ── */}
      <Section title="Name and contact" open={openName} onToggle={() => setOpenName(!openName)} icon={<span className="text-indigo-600">◎</span>}>
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
            <label className={labelCls()}>Customer display name <span className="text-red-600">*</span></label>
            <input required className={fieldCls()} value={form.display_name} onChange={(e) => update("display_name", e.target.value)} placeholder={displayPreview || "Required"} />
          </div>
        </div>
        <div className="grid md:grid-cols-2 gap-3 mb-3">
          <div>
            <label className={labelCls()}>Email</label>
            <input type="text" className={fieldCls()} value={form.primary_email} onChange={(e) => update("primary_email", e.target.value)} placeholder="e.g. a@example.com, b@example.com" />
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
        title="Centers"
        open={openCenters}
        onToggle={() => setOpenCenters(!openCenters)}
        icon={<span className="text-sky-400">⌁</span>}
      >
        <p className="text-[11px] text-gray-400 mb-2">
          Add one or more centers for this company. They are saved with the customer and can be combined on invoices.
        </p>
        {centersLoadError && <p className="text-xs text-red-600 mb-2">{centersLoadError}</p>}
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
                className="shrink-0 text-gray-400 hover:text-red-600 px-2 text-sm"
                aria-label="Remove center"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="mt-3 text-sm font-semibold text-indigo-600 hover:text-indigo-600"
          onClick={() => setCenterLines((rows) => [...rows, newCenterLine()])}
        >
          Add Center
        </button>
      </Section>

      {/* ── Addresses ── */}
      <Section title="Addresses" open={openAddr} onToggle={() => setOpenAddr(!openAddr)} icon={<span className="text-emerald-700">📍</span>}>
        <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Billing address</p>
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

        <label className="flex items-center gap-2 text-sm text-gray-600 mt-4 mb-2 cursor-pointer">
          <input type="checkbox" className="rounded border-white/20" checked={form.ship_same_as_billing} onChange={(e) => update("ship_same_as_billing", e.target.checked)} />
          Same as billing address
        </label>

        {!form.ship_same_as_billing && (
          <div className="grid md:grid-cols-2 gap-3">
            <p className="md:col-span-2 text-xs font-bold text-gray-400 uppercase tracking-wider">Shipping address</p>
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

      {/* ── Notes ── */}
      <Section title="Notes" open={openNotes} onToggle={() => setOpenNotes(!openNotes)} icon={<span className="text-amber-700">✎</span>}>
        <label className={labelCls()}>Notes</label>
        <textarea rows={3} className={`${fieldCls()} resize-y`} value={form.notes} onChange={(e) => update("notes", e.target.value)} />
      </Section>

      {/* ── App fields ── */}
      <Section title="App fields" open={openExtra} onToggle={() => setOpenExtra(!openExtra)} icon={<span className="text-violet-400">⚙</span>}>

        {/* Services table */}
        <div className="mb-5">
          <label className={labelCls()}>Services &amp; rates</label>
          <p className="text-[11px] text-gray-400 mb-2">
            Select a product/service, then choose Flat (one rate) or Slab (multiple ranges, each with its own rate).
            Each service can only appear once.
          </p>

          {serviceRows.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-gray-50 overflow-hidden mb-2 divide-y divide-gray-100">
              {serviceRows.map((row) => {
                const selectedProduct = productOptions.find((p) => p.id === row.product_and_service_id);
                return (
                  <div key={row.key} className="px-3 py-2.5">
                    <div className="grid grid-cols-[minmax(0,2fr)_6.5rem_minmax(0,2fr)_2rem] gap-2 items-center">
                      {/* Product dropdown */}
                      <select
                        value={row.product_and_service_id === "" ? "" : String(row.product_and_service_id)}
                        onChange={(e) => {
                          const v = e.target.value;
                          updateServiceRow(row.key, { product_and_service_id: v === "" ? "" : Number(v) });
                        }}
                        className="rounded-lg bg-white border border-gray-200 px-2 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200 appearance-none"
                      >
                        <option value="" style={{ background: "white", color: "var(--text-4)" }}>Select…</option>
                        {activeProducts.map((p) => {
                          const isUsedElsewhere = usedProductIds.has(p.id) && row.product_and_service_id !== p.id;
                          return (
                            <option
                              key={p.id}
                              value={p.id}
                              disabled={isUsedElsewhere}
                              style={{ background: "white", color: "var(--text-2)" }}
                            >
                              {p.name}
                            </option>
                          );
                        })}
                      </select>

                      {/* Flat / Slab */}
                      <select
                        value={row.pricing_type}
                        onChange={(e) => updateServiceRow(row.key, { pricing_type: e.target.value as "flat" | "slab" })}
                        className="rounded-lg bg-white border border-gray-200 px-2 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200 appearance-none"
                      >
                        <option value="flat" style={{ background: "white", color: "var(--text-2)" }}>Flat</option>
                        <option value="slab" style={{ background: "white", color: "var(--text-2)" }}>Slab</option>
                      </select>

                      {row.pricing_type === "flat" ? (
                        <input
                          type="number"
                          min="0.01"
                          step="0.01"
                          placeholder="Rate"
                          value={row.rate}
                          onChange={(e) => {
                            const v = e.target.value;
                            const rounded = v && !isNaN(parseFloat(v))
                              ? parseFloat(parseFloat(v).toFixed(2)).toString()
                              : v;
                            updateServiceRow(row.key, { rate: rounded });
                          }}
                          className="rounded-lg bg-white border border-gray-200 px-2 py-1.5 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                        />
                      ) : (
                        <span className="text-xs text-gray-500 truncate px-1">
                          {selectedProduct?.description ?? "—"}
                        </span>
                      )}

                      {/* Remove */}
                      <button
                        type="button"
                        onClick={() => removeServiceRow(row.key)}
                        className="text-gray-400 hover:text-red-600 text-sm transition-colors"
                        aria-label="Remove service row"
                      >
                        ✕
                      </button>
                    </div>

                    {row.pricing_type === "slab" && (
                      <div className="mt-2 ml-1 pl-3 border-l-2 border-gray-200">
                        {row.slabs.length > 0 && (
                          <div className="grid grid-cols-[5rem_5rem_6rem_1.5rem] gap-2 mb-1">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Start</span>
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">End</span>
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Rate</span>
                            <span />
                          </div>
                        )}
                        <div className="space-y-1.5">
                          {row.slabs.map((slab) => (
                            <div key={slab.key} className="grid grid-cols-[5rem_5rem_6rem_1.5rem] gap-2 items-center">
                              <input
                                type="number" min="1" step="1" placeholder="1"
                                value={slab.range_start}
                                onChange={(e) => updateSlabLine(row.key, slab.key, { range_start: e.target.value })}
                                className="rounded-lg bg-white border border-gray-200 px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                              />
                              <input
                                type="number" min="1" step="1" placeholder="∞"
                                value={slab.range_end}
                                onChange={(e) => updateSlabLine(row.key, slab.key, { range_end: e.target.value })}
                                className="rounded-lg bg-white border border-gray-200 px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                              />
                              <input
                                type="number" min="0.01" step="0.01" placeholder="Rate"
                                value={slab.rate}
                                onChange={(e) => updateSlabLine(row.key, slab.key, { rate: e.target.value })}
                                className="rounded-lg bg-white border border-gray-200 px-2 py-1 text-xs text-gray-900 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                              />
                              <button
                                type="button"
                                onClick={() => removeSlabLine(row.key, slab.key)}
                                className="text-gray-400 hover:text-red-600 text-xs transition-colors"
                                aria-label="Remove range"
                              >
                                ✕
                              </button>
                            </div>
                          ))}
                        </div>
                        <button
                          type="button"
                          className="mt-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-600"
                          onClick={() => addSlabLine(row.key)}
                        >
                          + Add range
                        </button>
                        <p className="text-[10px] text-gray-300 mt-1">Leave End blank for an open-ended top tier (e.g. "2501+").</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {serviceError && (
            <p className="text-xs text-red-600 mb-1">{serviceError}</p>
          )}

          <button
            type="button"
            className="text-sm font-semibold text-indigo-600 hover:text-indigo-600"
            onClick={() => api.setServiceRows((rows) => [...rows, newServiceRow()])}
          >
            + Add service
          </button>

          {activeProducts.length === 0 && (
            <p className="text-[11px] text-amber-700/80 mt-1.5">No active products found — run Sync to pull from QuickBooks.</p>
          )}
        </div>

        {/* Customer Types */}
        <div className="mb-4">
          <label className={labelCls()}>Customer types</label>
          {createTypeError && <p className="text-xs text-red-600 mb-1">{createTypeError}</p>}
          {(() => {
            const assignedIds = new Set(selectedCustomerTypeIds);
            const visibleTypes = mode === "edit"
              ? customerTypeOptions.filter((ct) => ct.status || assignedIds.has(ct.id))
              : customerTypeOptions.filter((ct) => ct.status);
            return (
              <>
                {visibleTypes.length === 0 && (
                  <p className="text-xs text-gray-400 py-1">No active customer types. Create one below.</p>
                )}
                {visibleTypes.length > 0 && (
                  <div className="max-h-36 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 space-y-1.5 mb-2">
                    {visibleTypes.map((ct) => (
                      <label
                        key={ct.id}
                        className={`flex items-center gap-2.5 text-sm ${ct.status ? "cursor-pointer text-gray-600" : "cursor-pointer text-gray-400"}`}
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
                          <span className="text-[9px] font-semibold uppercase tracking-wide text-gray-400 border border-gray-200 px-1 py-0.5 rounded">
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
                    className="flex-1 rounded-lg bg-gray-50 border border-gray-200 px-2 py-1.5 text-xs text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                    placeholder="New type name…"
                    value={newTypeName}
                    onChange={(e) => setNewTypeName(e.target.value)}
                    onKeyDown={async (e) => {
                      if (e.key !== "Enter") return;
                      e.preventDefault();
                      await createType();
                    }}
                    maxLength={255}
                  />
                  <button
                    type="button"
                    disabled={!newTypeName.trim() || creatingType}
                    className="text-xs font-semibold text-indigo-600 hover:text-indigo-600 disabled:opacity-40 shrink-0"
                    onClick={() => void createType()}
                  >
                    {creatingType ? "Adding…" : "+ Add"}
                  </button>
                </div>
                <p className="text-[10px] text-gray-300 mt-1">Press Enter or click + Add to create a new type inline.</p>
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
            <span className="text-sm text-gray-600">Add attachment in mail</span>
          </label>
          <p className="text-[11px] text-gray-400 mt-1.5">Auto-attach Excel/PDF when sending invoices.</p>
        </div>

        {/* Payment terms */}
        <div className="mt-4">
          <label className={labelCls()}>Payment terms (days)</label>
          <input
            type="number"
            min="1"
            step="1"
            className={fieldCls()}
            style={{ maxWidth: 140 }}
            value={form.payment_terms_days}
            onChange={(e) => update("payment_terms_days", e.target.value)}
          />
          <p className="text-[11px] text-gray-400 mt-1.5">
            Invoice due date = invoice date + this many days (defaults to 15).
          </p>
        </div>
      </Section>
    </>
  );
}
