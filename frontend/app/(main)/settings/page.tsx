"use client";

import { useEffect, useState } from "react";
import { apiPatch, apiPost } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import { ToastContainer, useToast } from "@/app/components/Toast";

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", alignItems: "start", gap: "12px 24px", padding: "16px 0", borderBottom: "1px solid var(--border)" }}>
      <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-2)", paddingTop: 9 }}>{label}</label>
      <div>{children}</div>
    </div>
  );
}

function SectionCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--border)" }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: "var(--text-1)", margin: 0 }}>{title}</h2>
        <p style={{ fontSize: 12, color: "var(--text-3)", marginTop: 3 }}>{subtitle}</p>
      </div>
      <div style={{ padding: "0 24px" }}>{children}</div>
      <div style={{ height: 8 }} />
    </div>
  );
}

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const { toasts, push, dismiss } = useToast();

  // ── Profile ──────────────────────────────────────────────────────────────────
  const [fullName, setFullName] = useState("");
  const [profileLoading, setProfileLoading] = useState(false);

  useEffect(() => {
    if (user?.full_name) setFullName(user.full_name);
  }, [user?.full_name]);

  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) { push("Name cannot be empty", "error"); return; }
    setProfileLoading(true);
    try {
      await apiPatch("/auth/me", { full_name: fullName.trim() });
      refresh();
      push("Profile updated successfully", "success");
    } catch (err) {
      push(err instanceof Error ? err.message : "Failed to update profile", "error");
    } finally {
      setProfileLoading(false);
    }
  };

  // ── Password ─────────────────────────────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) { push("New password must be at least 8 characters", "error"); return; }
    if (newPassword !== confirmPassword) { push("New passwords do not match", "error"); return; }
    setPasswordLoading(true);
    try {
      await apiPost("/auth/me/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      push("Password changed successfully", "success");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      push(err instanceof Error ? err.message : "Failed to change password", "error");
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto animate-fadeInUp">
      <ToastContainer toasts={toasts} onDismiss={dismiss} />

      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: "var(--text-1)", letterSpacing: "-0.3px" }}>Settings</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)", marginTop: 4 }}>Manage your account details and security.</p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

        {/* ── Profile ────────────────────────────────────────────────────────── */}
        <SectionCard title="Profile" subtitle="Update your display name.">
          <form onSubmit={(e) => void handleProfileSave(e)}>
            <FieldRow label="Full name">
              <input
                className="input"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your full name"
                style={{ width: "100%" }}
              />
            </FieldRow>
            <FieldRow label="Email">
              <input
                className="input"
                type="email"
                value={user?.email ?? ""}
                readOnly
                style={{ width: "100%", opacity: 0.6, cursor: "not-allowed" }}
              />
              <p style={{ fontSize: 11, color: "var(--text-4)", marginTop: 5 }}>Email cannot be changed here.</p>
            </FieldRow>
            <FieldRow label="Role">
              <div style={{ paddingTop: 8 }}>
                <span className={user?.role === "admin" ? "badge badge-primary" : "badge badge-neutral"} style={{ fontSize: 11 }}>
                  {user?.role ?? "—"}
                </span>
              </div>
            </FieldRow>
            <div style={{ padding: "16px 0 8px", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={profileLoading || fullName.trim() === (user?.full_name ?? "")}
              >
                {profileLoading ? "Saving…" : "Save changes"}
              </button>
            </div>
          </form>
        </SectionCard>

        {/* ── Security ───────────────────────────────────────────────────────── */}
        <SectionCard title="Security" subtitle="Change your password. You'll need your current password to confirm.">
          <form onSubmit={(e) => void handlePasswordChange(e)}>
            <FieldRow label="Current password">
              <input
                className="input"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                autoComplete="current-password"
                style={{ width: "100%" }}
              />
            </FieldRow>
            <FieldRow label="New password">
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                style={{ width: "100%" }}
              />
            </FieldRow>
            <FieldRow label="Confirm password">
              <input
                className="input"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat new password"
                autoComplete="new-password"
                style={{ width: "100%" }}
              />
              {newPassword && confirmPassword && newPassword !== confirmPassword && (
                <p style={{ fontSize: 11, color: "var(--error)", marginTop: 5 }}>Passwords do not match.</p>
              )}
            </FieldRow>
            <div style={{ padding: "16px 0 8px", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="submit"
                className="btn btn-primary btn-sm"
                disabled={passwordLoading || !currentPassword || !newPassword || !confirmPassword}
              >
                {passwordLoading ? "Changing…" : "Change password"}
              </button>
            </div>
          </form>
        </SectionCard>

      </div>
    </div>
  );
}
