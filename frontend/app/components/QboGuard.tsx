"use client";

import { qboConnectUrl } from "@/lib/api";
import { useQboStatus } from "@/lib/useQboStatus";

export default function QboGuard({ children }: { children: React.ReactNode }) {
  const { status } = useQboStatus();

  if (status === null) return null;

  if (!status.connected) {
    return (
      <div className="login-wrap">
        <div className="login-card anim-fade-up" style={{ textAlign: "center" }}>
          {/* Logo */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 32 }}>
            <div className="logo-mark" style={{ width: 52, height: 52, borderRadius: 16, marginBottom: 14 }}>
              <svg width="24" height="24" fill="none" stroke="white" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-1)", letterSpacing: "-0.5px" }}>Vengage</div>
          </div>

          <div className="card" style={{ padding: "28px 32px" }}>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-1)", marginBottom: 8 }}>
              Connect QuickBooks
            </h1>
            <p style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.6, marginBottom: 24 }}>
              Vengage requires a QuickBooks Online connection to function. Authorize your account to get started.
            </p>
            <button
              type="button"
              onClick={() => { window.location.href = qboConnectUrl(); }}
              className="btn btn-primary btn-lg"
              style={{ width: "100%", justifyContent: "center" }}
            >
              <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Connect to QuickBooks
            </button>
          </div>

          <p style={{ textAlign: "center", fontSize: 11, color: "var(--text-4)", marginTop: 20 }}>
            OAuth 2.0 — no credentials stored
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
