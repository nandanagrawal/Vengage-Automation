"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { apiGet, qboConnectUrl, qboAuthDelete, type UploadDetailResponse } from "@/lib/api";
import { useQboStatus } from "@/lib/useQboStatus";
import { useAuth } from "@/lib/useAuth";
import { getJobs, updateJob, markNotified, type BackgroundJob } from "@/lib/jobQueue";

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard",  subtitle: "Overview of your automation activity" },
  "/customers": { title: "Customers",  subtitle: "Manage and review customer records" },
  "/invoices":  { title: "Configuration", subtitle: "Group centers for invoice generation" },
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
  const [showBell, setShowBell] = useState(false);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const { status } = useQboStatus();
  const { user, logout } = useAuth();
  const connected = status?.connected ?? false;
  const envLabel = (status?.environment ?? "sandbox").toLowerCase() === "sandbox" ? "Sandbox" : "Production";

  // Poll background jobs every 4 seconds
  useEffect(() => {
    const poll = async () => {
      const current = getJobs();
      if (current.length === 0) { setJobs([]); return; }
      const updated = [...current];
      await Promise.all(
        current
          .filter((j) => j.status === "processing")
          .map(async (j) => {
            try {
              const detail = await apiGet<UploadDetailResponse>(`/invoice-uploads/${j.uploadId}`);
              if (detail.status !== "processing") {
                updateJob(j.uploadId, detail.status as BackgroundJob["status"]);
                const idx = updated.findIndex((x) => x.uploadId === j.uploadId);
                if (idx !== -1) updated[idx] = { ...updated[idx], status: detail.status as BackgroundJob["status"] };
              }
            } catch { /* keep as processing */ }
          }),
      );
      setJobs(updated);
    };
    void poll();
    const id = setInterval(() => { void poll(); }, 4000);
    return () => clearInterval(id);
  }, []);

  const processing = jobs.filter((j) => j.status === "processing").length;
  const unnotified = jobs.filter((j) => j.status !== "processing" && !j.notified).length;
  const bellBadge = processing > 0 ? processing : unnotified;

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

        {/* Notifications bell */}
        <div className="relative">
          <button
            onClick={() => { setShowBell((v) => !v); jobs.filter((j) => !j.notified && j.status !== "processing").forEach((j) => markNotified(j.uploadId)); }}
            className="relative w-9 h-9 rounded-lg border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.07] text-slate-400 hover:text-white flex items-center justify-center transition-all"
          >
            <BellIcon />
            {bellBadge > 0 && (
              <span className={`absolute top-1 right-1 min-w-[16px] h-4 px-0.5 rounded-full text-[9px] font-bold flex items-center justify-center text-white ${processing > 0 ? "bg-indigo-500" : "bg-emerald-500"}`}>
                {bellBadge}
              </span>
            )}
          </button>

          {showBell && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowBell(false)} />
              <div className="absolute right-0 top-11 w-72 rounded-xl border border-white/[0.08] shadow-2xl z-50 overflow-hidden" style={{ background: "#0F1225" }}>
                <div className="px-4 py-3 border-b border-white/[0.06]">
                  <p className="text-white text-sm font-semibold">Background Jobs</p>
                </div>
                {jobs.length === 0 ? (
                  <p className="px-4 py-6 text-slate-500 text-xs text-center">No background jobs</p>
                ) : (
                  <ul className="divide-y divide-white/[0.05] max-h-72 overflow-y-auto">
                    {jobs.map((j) => (
                      <li key={j.uploadId} className="px-4 py-3 flex items-center gap-3">
                        {j.status === "processing" ? (
                          <svg className="w-4 h-4 animate-spin text-indigo-400 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" /></svg>
                        ) : j.status === "completed" ? (
                          <span className="w-4 h-4 shrink-0 text-emerald-400 text-base">✓</span>
                        ) : j.status === "completed_with_errors" ? (
                          <span className="w-4 h-4 shrink-0 text-amber-400 text-base">⚠</span>
                        ) : (
                          <span className="w-4 h-4 shrink-0 text-rose-400 text-base">✕</span>
                        )}
                        <div className="min-w-0">
                          <p className="text-white text-xs font-medium">Job #{j.uploadId}</p>
                          <p className={`text-[11px] capitalize ${j.status === "processing" ? "text-indigo-400" : j.status === "completed" ? "text-emerald-400" : j.status === "failed" ? "text-rose-400" : "text-amber-400"}`}>
                            {j.status.replace(/_/g, " ")}
                          </p>
                        </div>
                        {j.status !== "processing" && (
                          <Link href="/import" onClick={() => setShowBell(false)} className="ml-auto text-indigo-400 text-[11px] hover:underline shrink-0">View</Link>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>

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
