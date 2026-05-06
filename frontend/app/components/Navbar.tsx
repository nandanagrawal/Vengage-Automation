"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { qboConnectUrl, qboAuthDelete } from "@/lib/api";
import { useQboStatus } from "@/lib/useQboStatus";
import { useAuth } from "@/lib/useAuth";

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard",  subtitle: "Overview of your automation activity" },
  "/customers": { title: "Customers",  subtitle: "Manage and review customer records" },
  "/import":    { title: "Import",     subtitle: "Upload and process invoice data" },
};

function BellIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const meta = pageMeta[pathname] ?? { title: "Vengage", subtitle: "" };
  const [showDropdown, setShowDropdown] = useState(false);
  const { status } = useQboStatus();
  const { user, logout } = useAuth();
  const connected = status?.connected ?? false;
  const envLabel = (status?.environment ?? "sandbox").toLowerCase() === "sandbox" ? "Sandbox" : "Production";

  async function disconnectQbo() {
    try {
      await qboAuthDelete<{ disconnected?: boolean }>("/disconnect");
      window.location.reload();
    } catch {
      /* ignore */
    }
    setShowDropdown(false);
  }

  return (
    <header
      className="h-16 shrink-0 flex items-center px-6 border-b border-white/[0.06] backdrop-blur-sm z-40"
      style={{ background: "rgba(8,11,24,0.95)" }}
    >
      {/* Left — breadcrumb */}
      <div className="flex items-center gap-2 text-sm min-w-0">
        <Link href="/" className="text-slate-500 hover:text-slate-300 transition-colors shrink-0 text-xs font-medium">
          Vengage
        </Link>
        <svg className="w-3.5 h-3.5 text-slate-700 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-white font-semibold truncate">{meta.title}</span>
        {meta.subtitle && (
          <>
            <span className="hidden md:block text-slate-700 mx-1">·</span>
            <span className="hidden md:block text-slate-500 text-xs truncate">{meta.subtitle}</span>
          </>
        )}
      </div>

      {/* Right — actions */}
      <div className="ml-auto flex items-center gap-2">
        {/* QuickBooks — OAuth sandbox/prod status (matches vengage-poc flow) */}
        <div className="hidden sm:flex items-center gap-2">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs ${
              connected
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400/95"
                : "border-white/[0.07] bg-white/[0.03] text-slate-400"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full shrink-0 ${connected ? "bg-emerald-400" : "bg-red-400 pulse-dot"}`}
            />
            <span className="whitespace-nowrap">
              QBO {envLabel} · {connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          {!connected ? (
            <button
              type="button"
              onClick={() => {
                window.location.href = qboConnectUrl();
              }}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 transition-colors"
            >
              Connect
            </button>
          ) : (
            <button
              type="button"
              onClick={disconnectQbo}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-slate-300 border border-white/[0.08] hover:bg-white/[0.05] transition-colors"
            >
              Disconnect
            </button>
          )}
        </div>

        {/* Notifications */}
        <button className="relative w-9 h-9 rounded-lg border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.07] text-slate-400 hover:text-white flex items-center justify-center transition-all">
          <BellIcon />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-indigo-500" />
        </button>

        {/* Avatar */}
        <div className="relative">
          <button
            onClick={() => setShowDropdown(!showDropdown)}
            className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-sm font-bold hover:opacity-90 transition-opacity"
          >
            {user?.full_name?.[0]?.toUpperCase() ?? "?"}
          </button>

          {showDropdown && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowDropdown(false)} />
              <div
                className="absolute right-0 top-11 w-52 rounded-xl border border-white/[0.08] shadow-2xl z-50 overflow-hidden"
                style={{ background: "#0F1225" }}
              >
                <div className="px-4 py-3 border-b border-white/[0.06]">
                  <p className="text-white text-sm font-semibold">{user?.full_name ?? "User"}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{user?.email ?? ""}</p>
                  <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${user?.role === "admin" ? "text-indigo-400 bg-indigo-400/10 border-indigo-400/20" : "text-sky-400 bg-sky-400/10 border-sky-400/20"}`}>
                    {user?.role ?? ""}
                  </span>
                </div>
                <div className="p-1.5">
                  {[
                    { label: "Settings", icon: "⚙" },
                    { label: "Documentation", icon: "📄" },
                  ].map(({ label, icon }) => (
                    <button
                      key={label}
                      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors text-left"
                      onClick={() => setShowDropdown(false)}
                    >
                      <span className="text-base">{icon}</span> {label}
                    </button>
                  ))}
                  <div className="border-t border-white/[0.06] mt-1 pt-1">
                    <button
                      onClick={logout}
                      className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors text-left"
                    >
                      <span className="text-base">→</span> Sign out
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
