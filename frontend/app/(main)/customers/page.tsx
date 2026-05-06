const customers = [
  { id: 1, name: "Acme Corp",       email: "billing@acme.com",     status: "Active",   invoices: 24 },
  { id: 2, name: "Globex Ltd",      email: "ap@globex.io",         status: "Active",   invoices: 18 },
  { id: 3, name: "Initech Inc",     email: "finance@initech.com",  status: "Inactive", invoices: 7  },
  { id: 4, name: "Umbrella Corp",   email: "accounts@umbrella.co", status: "Active",   invoices: 41 },
  { id: 5, name: "Massive Dynamic", email: "info@massive.dev",     status: "Active",   invoices: 33 },
  { id: 6, name: "Soylent Corp",    email: "ar@soylent.io",        status: "Inactive", invoices: 2  },
];

export default function CustomersPage() {
  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 animate-fadeInUp">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Customers</h1>
          <p className="text-slate-500 text-sm mt-1">Manage and review customer records.</p>
        </div>
        <button className="shimmer-btn inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-white text-sm font-semibold hover:scale-105 active:scale-95 transition-transform">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add Customer
        </button>
      </div>

      {/* Table */}
      <div
        className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp delay-100"
        style={{ background: "var(--bg-card)" }}
      >
        {/* Table header */}
        <div className="grid grid-cols-[1fr_1fr_auto_auto] gap-4 px-6 py-3 border-b border-white/[0.06]">
          {["Customer", "Email", "Invoices", "Status"].map((h) => (
            <span key={h} className="text-xs font-semibold uppercase tracking-wider text-slate-600">{h}</span>
          ))}
        </div>

        <div className="divide-y divide-white/[0.04]">
          {customers.map(({ id, name, email, status, invoices }, i) => (
            <div
              key={id}
              className="grid grid-cols-[1fr_1fr_auto_auto] gap-4 items-center px-6 py-4 hover:bg-white/[0.03] transition-colors animate-fadeInLeft"
              style={{ animationDelay: `${0.05 * i}s` }}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                  {name[0]}
                </div>
                <span className="text-white text-sm font-medium truncate">{name}</span>
              </div>

              <span className="text-slate-500 text-sm truncate">{email}</span>

              <span className="text-slate-400 text-sm font-mono w-12 text-center">{invoices}</span>

              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                status === "Active"
                  ? "bg-emerald-400/10 text-emerald-400 border border-emerald-400/20"
                  : "bg-slate-400/10 text-slate-500 border border-slate-400/10"
              }`}>
                <span className={`w-1 h-1 rounded-full ${status === "Active" ? "bg-emerald-400" : "bg-slate-500"}`} />
                {status}
              </span>
            </div>
          ))}
        </div>

        <div className="px-6 py-3 border-t border-white/[0.06] flex items-center justify-between">
          <span className="text-slate-600 text-xs">{customers.length} customers total</span>
          <div className="flex items-center gap-1">
            {["←", "1", "2", "→"].map((p) => (
              <button key={p} className="w-7 h-7 rounded-lg text-xs text-slate-500 hover:text-white hover:bg-white/[0.07] transition-colors">
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
