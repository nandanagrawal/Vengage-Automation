"use client";

import { qboConnectUrl } from "@/lib/api";
import { useQboStatus } from "@/lib/useQboStatus";

export default function QboGuard({ children }: { children: React.ReactNode }) {
  const { status } = useQboStatus();

  // Still loading — render nothing to avoid flash
  if (status === null) return null;

  if (!status.connected) {
    return (
      <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center p-6" style={{ background: "var(--bg-deep)" }}>
        {/* Glow */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full opacity-10 blur-3xl"
            style={{ background: "radial-gradient(circle, #6366f1, transparent 70%)" }} />
        </div>

        <div className="relative flex flex-col items-center text-center max-w-sm">
          {/* Icon */}
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/25 flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-indigo-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>

          <h1 className="text-2xl font-bold text-white mb-2 tracking-tight">Connect QuickBooks</h1>
          <p className="text-slate-400 text-sm leading-relaxed mb-8">
            Vengage requires a QuickBooks Online connection to function. Authorize your account to get started.
          </p>

          <button
            type="button"
            onClick={() => { window.location.href = qboConnectUrl(); }}
            className="shimmer-btn inline-flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-white text-sm font-semibold hover:scale-105 active:scale-95 transition-transform"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Connect to QuickBooks
          </button>

          <p className="text-slate-600 text-xs mt-6">
            OAuth 2.0 — no credentials stored
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
