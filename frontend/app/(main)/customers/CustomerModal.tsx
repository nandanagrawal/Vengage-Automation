"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CustomerRow } from "@/lib/api";

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
  rate: string;
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
  notes: "", rate: "0", add_attachment_in_mail: false,
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
    rate: String(c.rate),
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
  onSubmit: (payload: Record<string, unknown>, files: File[]) => Promise<void>;
  submitting: boolean;
  mode?: "create" | "edit";
  customer?: CustomerRow;
}) {
  const [form, setForm] = useState<CustomerFormValues>(emptyForm);
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [openName, setOpenName] = useState(true);
  const [openAddr, setOpenAddr] = useState(true);
  const [openNotes, setOpenNotes] = useState(true);
  const [openExtra, setOpenExtra] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    if (mode === "edit" && customer) {
      setForm(customerToForm(customer));
    } else {
      setForm(emptyForm());
    }
    setFiles([]);
  }, [open, mode, customer]);

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

  const resetAndClose = () => {
    setForm(emptyForm());
    setFiles([]);
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
      rate: form.rate || "0",
      add_attachment_in_mail: form.add_attachment_in_mail,
    };

    try {
      await onSubmit(payload, files);
      resetAndClose();
    } catch {
      /* parent surfaces error */
    }
  };

  if (!open) return null;

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

            <p className={labelCls()}>Upload files to QuickBooks</p>
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
              <p className="text-xs text-slate-600 mt-1">PDFs, images, spreadsheets — saved to QuickBooks</p>
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
            <div className="grid md:grid-cols-2 gap-4 items-start">
              <div>
                <label className={labelCls()}>Rate</label>
                <input type="number" min={0} step="0.0001" className={fieldCls()} value={form.rate} onChange={(e) => update("rate", e.target.value)} />
                <p className="text-[11px] text-slate-600 mt-1">Decimal, minimum 0, no maximum.</p>
              </div>
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
