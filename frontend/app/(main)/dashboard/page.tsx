const stats = [
  { label: "Total Customers", value: "1,284", delta: "+12%", up: true,
    icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>,
    gradient: "from-blue-500 to-indigo-600" },
  { label: "Imports Today", value: "38", delta: "+5", up: true,
    icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
    gradient: "from-violet-500 to-purple-600" },
  { label: "Invoices Sent", value: "847", delta: "+24%", up: true,
    icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>,
    gradient: "from-emerald-400 to-teal-500" },
  { label: "Delivery Failures", value: "3", delta: "-2", up: false,
    icon: <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>,
    gradient: "from-rose-500 to-red-600" },
];

const recentActivity = [
  { customer: "Acme Corp",       invoice: "VNG-1042", status: "Delivered",  time: "2m ago",  color: "text-emerald-400" },
  { customer: "Globex Ltd",      invoice: "VNG-1041", status: "Sent",       time: "18m ago", color: "text-blue-400"    },
  { customer: "Initech Inc",     invoice: "VNG-1040", status: "Failed",     time: "1h ago",  color: "text-red-400"     },
  { customer: "Umbrella Corp",   invoice: "VNG-1039", status: "Delivered",  time: "2h ago",  color: "text-emerald-400" },
  { customer: "Massive Dynamic", invoice: "VNG-1038", status: "Delivered",  time: "3h ago",  color: "text-emerald-400" },
];

export default function DashboardPage() {
  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8 animate-fadeInUp">
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">Welcome back. Here&apos;s your automation overview.</p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, delta, up, icon, gradient }, i) => (
          <div
            key={label}
            className="rounded-2xl border border-white/[0.07] p-5 hover:border-white/[0.14] hover:-translate-y-0.5 transition-all duration-200 card-glow animate-scaleIn"
            style={{ background: "var(--bg-card)", animationDelay: `${i * 0.06}s` }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white`}>
                {icon}
              </div>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${up ? "text-emerald-400 bg-emerald-400/10" : "text-red-400 bg-red-400/10"}`}>
                {delta}
              </span>
            </div>
            <p className="text-3xl font-extrabold text-white tracking-tight">{value}</p>
            <p className="text-slate-500 text-xs mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Recent activity */}
      <div
        className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp delay-300"
        style={{ background: "var(--bg-card)" }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <h2 className="text-white font-semibold text-sm">Recent Activity</h2>
          <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors font-medium">View all →</button>
        </div>

        <div className="divide-y divide-white/[0.04]">
          {recentActivity.map(({ customer, invoice, status, time, color }) => (
            <div key={invoice} className="flex items-center justify-between px-6 py-3.5 hover:bg-white/[0.03] transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-bold shrink-0">
                  {customer[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-sm font-medium truncate">{customer}</p>
                  <p className="text-slate-600 text-xs font-mono">{invoice}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className={`text-xs font-semibold ${color}`}>{status}</span>
                <span className="text-slate-600 text-xs">{time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
