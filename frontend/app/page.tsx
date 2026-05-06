import Link from "next/link";
import ConnectButton from "@/app/components/ConnectButton";

const steps = [
  {
    num: "01",
    title: "Connect QuickBooks",
    desc: "OAuth 2.0 handshake with QuickBooks Online. One-click authorization — no credentials stored.",
    gradient: "from-sky-400 to-blue-600",
    glow: "group-hover:shadow-blue-500/20",
  },
  {
    num: "02",
    title: "Upload Customers",
    desc: "Import your customer roster via CSV or JSON. Smart deduplication matches against existing QBO contacts.",
    gradient: "from-blue-500 to-indigo-600",
    glow: "group-hover:shadow-indigo-500/20",
  },
  {
    num: "03",
    title: "Configure Invoice",
    desc: "Set line items, due dates, and VNG prefix. Templates persist across runs — set once, reuse forever.",
    gradient: "from-indigo-500 to-violet-600",
    glow: "group-hover:shadow-violet-500/20",
  },
  {
    num: "04",
    title: "Create Invoices",
    desc: "Batch-create VNG-numbered invoices in QuickBooks with auto-incremented reference numbers.",
    gradient: "from-violet-500 to-purple-600",
    glow: "group-hover:shadow-purple-500/20",
  },
  {
    num: "05",
    title: "Attach & Email",
    desc: "Attach Excel files and fire invoice emails — one API call per customer. Zero manual sending.",
    gradient: "from-purple-500 to-fuchsia-600",
    glow: "group-hover:shadow-fuchsia-500/20",
  },
  {
    num: "06",
    title: "Track Delivery",
    desc: "Live email delivery status for every invoice, refreshed directly from QuickBooks in real time.",
    gradient: "from-emerald-400 to-teal-500",
    glow: "group-hover:shadow-emerald-500/20",
  },
];

const features = [
  { label: "Zero manual data entry", icon: "✦" },
  { label: "Automated email dispatch", icon: "✦" },
  { label: "Real-time delivery tracking", icon: "✦" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg-deep)" }}>

      {/* ── Nav ── */}
      <header className="border-b border-white/[0.06] backdrop-blur-sm sticky top-0 z-50 animate-fadeInUp"
        style={{ background: "rgba(8,11,24,0.85)" }}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="text-white font-bold text-base tracking-tight">Vengage</span>
          </div>
          <nav className="hidden sm:flex items-center gap-6 text-sm text-slate-400">
            <a href="#workflow" className="hover:text-white transition-colors">Workflow</a>
            <a href="#connect" className="hover:text-white transition-colors">Connect</a>
            <Link
              href="/dashboard"
              className="px-4 py-2 rounded-lg bg-white/[0.07] hover:bg-white/[0.12] text-white transition-colors text-sm font-medium"
            >
              Dashboard →
            </Link>
          </nav>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="dot-grid relative overflow-hidden pt-24 pb-20 px-6">
        {/* glow orbs */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -top-32 left-1/3 w-[500px] h-[500px] rounded-full opacity-10 blur-3xl"
            style={{ background: "radial-gradient(circle, #6366f1, transparent 70%)" }} />
          <div className="absolute top-1/2 -right-24 w-[300px] h-[300px] rounded-full opacity-8 blur-3xl"
            style={{ background: "radial-gradient(circle, #8b5cf6, transparent 70%)" }} />
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          <div className="animate-fadeInUp inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 text-xs font-medium mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 pulse-dot" />
            QuickBooks Online · Sandbox POC
          </div>

          <h1 className="animate-fadeInUp delay-100 text-5xl sm:text-6xl font-extrabold text-white leading-[1.08] tracking-tight mb-6">
            Automate Invoice{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              Delivery.
            </span>
            <br />Zero Manual Work.
          </h1>

          <p className="animate-fadeInUp delay-200 text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed mb-10">
            Create invoices, attach Excel files, and track delivery — entirely through the QBO API.
            No spreadsheets. No copy-paste. No human error.
          </p>

          <div className="animate-fadeInUp delay-300 flex flex-wrap justify-center gap-6 mb-12">
            {features.map(({ label, icon }) => (
              <span key={label} className="flex items-center gap-2 text-sm text-slate-300">
                <span className="text-indigo-400 text-xs">{icon}</span>
                {label}
              </span>
            ))}
          </div>

          <div className="animate-fadeInUp delay-400 flex flex-wrap justify-center gap-4">
            <a href="#connect">
              <ConnectButton />
            </a>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl border border-white/10 bg-white/[0.05] text-white text-sm font-semibold hover:bg-white/[0.1] hover:border-white/20 transition-all duration-200"
            >
              Open Dashboard
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Workflow steps ── */}
      <section id="workflow" className="px-6 pb-24 dot-grid">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14 animate-fadeInUp">
            <p className="text-xs font-semibold uppercase tracking-widest text-indigo-400 mb-3">How it works</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              Six steps. Fully automated.
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {steps.map(({ num, title, desc, gradient, glow }, i) => (
              <div
                key={num}
                className={`group relative rounded-2xl border border-white/[0.07] p-6 cursor-default
                  transition-all duration-300 ease-out card-glow
                  hover:-translate-y-1 hover:border-white/[0.14]
                  animate-scaleIn`}
                style={{
                  background: "var(--bg-card)",
                  animationDelay: `${0.05 * i}s`,
                }}
              >
                {/* connector arrow for non-last items */}
                {i < steps.length - 1 && i % 3 !== 2 && (
                  <span className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 text-slate-600 text-lg z-10">
                    →
                  </span>
                )}

                <div className="flex items-start justify-between mb-4">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-lg`}>
                    <span className="text-white text-xs font-bold tracking-wide">{num}</span>
                  </div>
                  <span className={`text-xs text-slate-600 font-mono group-hover:text-slate-400 transition-colors`}>
                    STEP
                  </span>
                </div>

                <h3 className="text-white font-semibold text-base mb-2 tracking-tight">{title}</h3>
                <p className={`text-sm leading-relaxed ${num === "06" ? "text-emerald-400/80" : "text-slate-500 group-hover:text-slate-400"} transition-colors`}>
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── QuickBooks connection banner ── */}
      <section id="connect" className="px-6 pb-24">
        <div className="max-w-4xl mx-auto">
          <div className="rounded-2xl border border-white/[0.08] p-8 flex flex-col sm:flex-row items-center justify-between gap-6 animate-fadeInUp"
            style={{ background: "var(--bg-card)" }}>
            <div className="flex items-center gap-5">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center shrink-0">
                <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <p className="text-white font-semibold text-base">QuickBooks Connection</p>
                <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 pulse-dot inline-block" />
                  Not connected — authorize with QuickBooks to begin
                </p>
              </div>
            </div>
            <ConnectButton />
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="mt-auto border-t border-white/[0.06] py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-slate-600 text-center sm:text-left">
            VENGAGE Invoice Automation POC · QuickBooks Online Sandbox · Realm ID: 9341456994611139
          </p>
          <p className="text-xs text-slate-700 italic">
            Sandbox demo — no real money or emails are exchanged
          </p>
        </div>
      </footer>

    </div>
  );
}
