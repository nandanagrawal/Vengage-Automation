"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { loginRequest, saveToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { access_token } = await loginRequest(email, password);
      saveToken(access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-card anim-fade-up">
      {/* Logo */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 32 }}>
        <div style={{ width: 52, height: 52, borderRadius: 16, marginBottom: 14, overflow: "hidden" }}>
          <img src="https://vengage.ai/frontend_assets/images/vlogo.png" alt="Vengage" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
        </div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-1)", letterSpacing: "-0.5px" }}>Vengage</div>
        <div style={{ fontSize: 14, color: "var(--text-3)", marginTop: 4 }}>Sign in to your workspace</div>
      </div>

      <div className="card" style={{ padding: "28px 32px" }}>
        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label className="input-label">Email address</label>
              <input
                className="input"
                type="email"
                required
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <label className="input-label" style={{ marginBottom: 0 }}>Password</label>
              </div>
              <input
                className="input"
                type="password"
                required
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <div className="notice-banner notice-error" style={{ marginBottom: 0 }}>
                <span style={{ fontSize: 13 }}>{error}</span>
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-lg"
              style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
              disabled={loading}
            >
              {loading ? (
                <>
                  <svg className="spinner" width="16" height="16" fill="none" stroke="white" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
                  </svg>
                  Signing in…
                </>
              ) : "Sign in"}
            </button>
          </div>
        </form>
      </div>

      <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-3)", marginTop: 20 }}>
        New account? <span style={{ color: "var(--text-2)", fontWeight: 500 }}>Ask your admin to create one via the API</span>
      </p>
    </div>
  );
}
