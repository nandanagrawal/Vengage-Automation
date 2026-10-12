"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmTwoFactorSetup, loginRequest, saveToken, verifyTwoFactor } from "@/lib/auth";

type Step =
  | { name: "credentials" }
  | { name: "setup"; pendingToken: string; qrCodeDataUri: string; manualEntryKey: string }
  | { name: "setup-backup-codes"; accessToken: string; backupCodes: string[] }
  | { name: "verify"; pendingToken: string };

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<Step>({ name: "credentials" });
  const [code, setCode] = useState("");
  const [rememberDevice, setRememberDevice] = useState(false);

  const handleCredentialsSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await loginRequest(email, password);
      if (result.status === "success") {
        saveToken(result.access_token);
        router.replace("/dashboard");
        return;
      }
      if (result.status === "setup_required") {
        setStep({
          name: "setup",
          pendingToken: result.pending_token,
          qrCodeDataUri: result.qr_code_data_uri,
          manualEntryKey: result.manual_entry_key,
        });
        return;
      }
      setStep({ name: "verify", pendingToken: result.pending_token });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSetupConfirm = async (e: FormEvent) => {
    e.preventDefault();
    if (step.name !== "setup") return;
    setError(null);
    setLoading(true);
    try {
      const result = await confirmTwoFactorSetup(step.pendingToken, code, rememberDevice);
      setStep({
        name: "setup-backup-codes",
        accessToken: result.access_token,
        backupCodes: result.backup_codes ?? [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Incorrect code");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    if (step.name !== "verify") return;
    setError(null);
    setLoading(true);
    try {
      const result = await verifyTwoFactor(step.pendingToken, code, rememberDevice);
      saveToken(result.access_token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Incorrect code");
    } finally {
      setLoading(false);
    }
  };

  const finishSetup = () => {
    if (step.name !== "setup-backup-codes") return;
    saveToken(step.accessToken);
    router.replace("/dashboard");
  };

  return (
    <div className="login-card anim-fade-up">
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: 32 }}>
        <div style={{ width: 52, height: 52, borderRadius: 16, marginBottom: 14, overflow: "hidden" }}>
          <img src="https://vengage.ai/frontend_assets/images/vlogo.png" alt="Vengage" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
        </div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text-1)", letterSpacing: "-0.5px" }}>Vengage</div>
        <div style={{ fontSize: 14, color: "var(--text-3)", marginTop: 4 }}>
          {step.name === "credentials" && "Sign in to your workspace"}
          {step.name === "setup" && "Set up two-factor authentication"}
          {step.name === "setup-backup-codes" && "Save your backup codes"}
          {step.name === "verify" && "Enter your authentication code"}
        </div>
      </div>

      <div className="card" style={{ padding: "28px 32px" }}>
        {step.name === "credentials" && (
          <form onSubmit={(e) => void handleCredentialsSubmit(e)}>
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
        )}

        {step.name === "setup" && (
          <form onSubmit={(e) => void handleSetupConfirm(e)}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <p style={{ fontSize: 13, color: "var(--text-3)", margin: 0 }}>
                Scan this QR code with an authenticator app (Google Authenticator, Authy, 1Password, etc.), then enter the 6-digit code it shows.
              </p>
              <div style={{ display: "flex", justifyContent: "center" }}>
                <img src={step.qrCodeDataUri} alt="2FA QR code" style={{ width: 200, height: 200, borderRadius: 8, border: "1px solid var(--border)" }} />
              </div>
              <div>
                <label className="input-label">Can&apos;t scan it? Enter this key manually</label>
                <code style={{
                  display: "block", padding: "8px 10px", background: "var(--bg-2)", borderRadius: 6,
                  fontSize: 13, letterSpacing: "0.5px", wordBreak: "break-all",
                }}>
                  {step.manualEntryKey}
                </code>
              </div>

              <div>
                <label className="input-label">6-digit code</label>
                <input
                  className="input"
                  type="text"
                  required
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  style={{ textAlign: "center", fontSize: 18, letterSpacing: "4px" }}
                />
              </div>

              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-2)" }}>
                <input type="checkbox" checked={rememberDevice} onChange={(e) => setRememberDevice(e.target.checked)} />
                Remember this device for 7 days
              </label>

              {error && (
                <div className="notice-banner notice-error" style={{ marginBottom: 0 }}>
                  <span style={{ fontSize: 13 }}>{error}</span>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary btn-lg"
                style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
                disabled={loading || code.length < 6}
              >
                {loading ? "Verifying…" : "Confirm and finish setup"}
              </button>
            </div>
          </form>
        )}

        {step.name === "setup-backup-codes" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <p style={{ fontSize: 13, color: "var(--text-3)", margin: 0 }}>
              Save these backup codes somewhere safe. Each one can be used once to sign in if you lose access to your authenticator app. They won&apos;t be shown again.
            </p>
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8,
              padding: "14px 16px", background: "var(--bg-2)", borderRadius: 8,
            }}>
              {step.backupCodes.map((c) => (
                <code key={c} style={{ fontSize: 14, letterSpacing: "0.5px" }}>{c}</code>
              ))}
            </div>
            <button
              type="button"
              className="btn btn-primary btn-lg"
              style={{ width: "100%", justifyContent: "center" }}
              onClick={finishSetup}
            >
              I&apos;ve saved these codes — continue
            </button>
          </div>
        )}

        {step.name === "verify" && (
          <form onSubmit={(e) => void handleVerify(e)}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label className="input-label">Authentication code</label>
                <input
                  className="input"
                  type="text"
                  required
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="6-digit code, or an 8-character backup code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  style={{ textAlign: "center", fontSize: 18, letterSpacing: "2px" }}
                />
              </div>

              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--text-2)" }}>
                <input type="checkbox" checked={rememberDevice} onChange={(e) => setRememberDevice(e.target.checked)} />
                Remember this device for 7 days
              </label>

              {error && (
                <div className="notice-banner notice-error" style={{ marginBottom: 0 }}>
                  <span style={{ fontSize: 13 }}>{error}</span>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary btn-lg"
                style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
                disabled={loading || code.length < 6}
              >
                {loading ? "Verifying…" : "Verify"}
              </button>
            </div>
          </form>
        )}
      </div>

      {step.name === "credentials" && (
        <p style={{ textAlign: "center", fontSize: 12, color: "var(--text-3)", marginTop: 20 }}>
          New account? <span style={{ color: "var(--text-2)", fontWeight: 500 }}>Ask your admin to create one via the API</span>
        </p>
      )}
    </div>
  );
}
