"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { apiGet, qboConnectUrl, qboAuthDelete, type UploadDetailResponse } from "@/lib/api";
import { useQboStatus } from "@/lib/useQboStatus";
import { useAuth } from "@/lib/useAuth";
import { getJobs, updateJob, markNotified, type BackgroundJob } from "@/lib/jobQueue";

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": { title: "Dashboard",     subtitle: "Overview of your automation activity" },
  "/customers": { title: "Customers",     subtitle: "Manage and review customer records" },
  "/invoices":  { title: "Configuration", subtitle: "Group centers for invoice generation" },
  "/import":    { title: "Import",        subtitle: "Upload and process invoice data" },
  "/settings":  { title: "Settings",      subtitle: "Manage your account and preferences" },
};

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
  const unnotified  = jobs.filter((j) => j.status !== "processing" && !j.notified).length;
  const bellBadge   = processing > 0 ? processing : unnotified;

  async function disconnectQbo() {
    try { await qboAuthDelete<{ disconnected?: boolean }>("/disconnect"); window.location.reload(); }
    catch { /* ignore */ }
    setShowDropdown(false);
  }

  return (
    <header className="navbar">
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 7, flex: 1, minWidth: 0, overflow: "hidden" }}>
        <span style={{ fontSize: 12, color: "var(--text-3)", fontWeight: 500, whiteSpace: "nowrap" }}>Vengage</span>
        <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24" style={{ color: "var(--text-4)", flexShrink: 0 }}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span style={{ fontSize: 15, fontWeight: 700, color: "var(--text-1)", whiteSpace: "nowrap" }}>{meta.title}</span>
        {meta.subtitle && (
          <>
            <span style={{ color: "var(--border)", fontSize: 16 }}>·</span>
            <span style={{ fontSize: 12, color: "var(--text-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{meta.subtitle}</span>
          </>
        )}
      </div>

      {/* Right actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        {/* QBO Status */}
        <div className={`qbo-pill ${connected ? "qbo-connected" : "qbo-disconnected"}`}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: connected ? "var(--success)" : "var(--error)", flexShrink: 0 }} />
          <span>QBO {envLabel} · {connected ? "Connected" : "Disconnected"}</span>
        </div>
        {connected ? (
          <button type="button" onClick={disconnectQbo} className="btn btn-ghost btn-sm">
            Disconnect
          </button>
        ) : (
          <button type="button" onClick={() => { window.location.href = qboConnectUrl(); }} className="btn btn-secondary btn-sm">
            Connect
          </button>
        )}

        {/* Bell */}
        <div style={{ position: "relative" }}>
          <button
            className="icon-btn"
            style={{ position: "relative" }}
            onClick={() => {
              setShowBell((v) => !v);
              setShowDropdown(false);
              jobs.filter((j) => !j.notified && j.status !== "processing").forEach((j) => markNotified(j.uploadId));
            }}
          >
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {bellBadge > 0 && (
              <span
                style={{ position: "absolute", top: 7, right: 7, width: 7, height: 7, borderRadius: "50%", background: processing > 0 ? "var(--primary)" : "var(--success)", border: "2px solid white" }}
              />
            )}
          </button>

          {showBell && (
            <>
              <div style={{ position: "fixed", inset: 0, zIndex: 40 }} onClick={() => setShowBell(false)} />
              <div className="dropdown" style={{ position: "absolute", right: 0, top: 44, width: 290, zIndex: 50 }}>
                <div className="dropdown-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-1)" }}>Background Jobs</span>
                </div>
                <div style={{ padding: "6px 8px" }}>
                  {jobs.length === 0 ? (
                    <p style={{ padding: "20px", textAlign: "center", fontSize: 12, color: "var(--text-3)" }}>No background jobs</p>
                  ) : (
                    <ul style={{ maxHeight: 280, overflowY: "auto" }}>
                      {jobs.map((j) => (
                        <li key={j.uploadId} className="dropdown-item" style={{ borderRadius: 9 }}>
                          {j.status === "processing" ? (
                            <svg className="spinner" width="16" height="16" fill="none" stroke="var(--primary)" strokeWidth="2" viewBox="0 0 24 24">
                              <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                            </svg>
                          ) : j.status === "completed" ? (
                            <span style={{ color: "var(--success)", fontWeight: 700 }}>✓</span>
                          ) : j.status === "completed_with_errors" ? (
                            <span style={{ color: "var(--warning)", fontWeight: 700 }}>⚠</span>
                          ) : (
                            <span style={{ color: "var(--error)", fontWeight: 700 }}>✕</span>
                          )}
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <p style={{ fontSize: 13, fontWeight: 500, color: "var(--text-1)" }}>Job #{j.uploadId}</p>
                            <p style={{ fontSize: 11, color: j.status === "processing" ? "var(--primary)" : j.status === "completed" ? "var(--success)" : j.status === "failed" ? "var(--error)" : "var(--warning)", textTransform: "capitalize" }}>
                              {j.status.replace(/_/g, " ")}
                            </p>
                          </div>
                          {j.status !== "processing" && (
                            <Link href="/import" onClick={() => setShowBell(false)} style={{ fontSize: 12, color: "var(--primary)", fontWeight: 600 }}>View →</Link>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Avatar */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => { setShowDropdown(!showDropdown); setShowBell(false); }}
            className="avatar avatar-brand"
            style={{ border: "none", cursor: "pointer", width: 36, height: 36, fontSize: 14 }}
          >
            {user?.full_name?.[0]?.toUpperCase() ?? "?"}
          </button>

          {showDropdown && (
            <>
              <div style={{ position: "fixed", inset: 0, zIndex: 40 }} onClick={() => setShowDropdown(false)} />
              <div className="dropdown" style={{ position: "absolute", right: 0, top: 44, width: 210, zIndex: 50 }}>
                <div className="dropdown-header">
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-1)" }}>{user?.full_name ?? "User"}</div>
                  <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>{user?.email ?? ""}</div>
                  <span
                    className={user?.role === "admin" ? "badge badge-primary" : "badge badge-neutral"}
                    style={{ marginTop: 6, fontSize: 10 }}
                  >
                    {user?.role ?? ""}
                  </span>
                </div>
                <div style={{ padding: "6px 8px" }}>
                  <Link
                    href="/settings"
                    className="dropdown-item"
                    style={{ borderRadius: 8, display: "flex", alignItems: "center", gap: 8 }}
                    onClick={() => setShowDropdown(false)}
                  >
                    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                    Settings
                  </Link>
                  <div style={{ borderTop: "1px solid var(--border)", marginTop: 4, paddingTop: 4 }}>
                    <button className="dropdown-item dropdown-item-danger" style={{ borderRadius: 8 }} onClick={logout}>
                      Sign out
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
