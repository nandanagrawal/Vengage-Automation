export default function AppFooter() {
  return (
    <footer
      className="h-11 shrink-0 flex items-center justify-between px-6 border-t border-white/[0.05] text-xs"
      style={{ background: "rgba(8,11,24,0.95)" }}
    >
      <div className="flex items-center gap-4 text-slate-600">
        <span>© 2025 Vengage</span>
        <span className="hidden sm:block">·</span>
        <span className="hidden sm:block">Invoice Automation POC</span>
        <span className="hidden md:block">·</span>
        <span className="hidden md:block">Realm ID: 9341456994611139</span>
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden sm:flex items-center gap-1.5 text-slate-700 italic">
          Sandbox — no real money or emails exchanged
        </span>
        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-amber-500/20 bg-amber-500/10 text-amber-400 font-medium">
          <span className="w-1 h-1 rounded-full bg-amber-400" />
          Sandbox
        </span>
      </div>
    </footer>
  );
}
