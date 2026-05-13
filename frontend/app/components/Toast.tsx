"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ToastType = "error" | "success" | "info";

export type ToastItem = {
  id: string;
  message: string;
  type: ToastType;
};

function SingleToast({ item, onDismiss }: { item: ToastItem; onDismiss: (id: string) => void }) {
  const [progress, setProgress] = useState(100);
  const [exiting, setExiting] = useState(false);
  const startRef = useRef(Date.now());
  const DURATION = 5000;

  useEffect(() => {
    const raf = () => {
      const elapsed = Date.now() - startRef.current;
      const remaining = Math.max(0, 100 - (elapsed / DURATION) * 100);
      setProgress(remaining);
      if (elapsed >= DURATION) {
        setExiting(true);
      } else {
        frame = requestAnimationFrame(raf);
      }
    };
    let frame = requestAnimationFrame(raf);
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!exiting) return;
    const t = setTimeout(() => onDismiss(item.id), 300);
    return () => clearTimeout(t);
  }, [exiting, item.id, onDismiss]);

  const dismiss = () => setExiting(true);

  const colors = {
    error:   { border: "var(--error-border)",   bg: "var(--error-bg)",   bar: "var(--error)",   icon: "var(--error)",   text: "var(--error-text)"   },
    success: { border: "var(--success-border)", bg: "var(--success-bg)", bar: "var(--success)", icon: "var(--success)", text: "var(--success-text)" },
    info:    { border: "var(--primary-border)", bg: "var(--primary-bg)", bar: "var(--primary)", icon: "var(--primary)", text: "var(--primary-text)" },
  }[item.type];

  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "flex-start",
        gap: 10,
        padding: "12px 14px 16px",
        borderRadius: 10,
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
        width: 320,
        maxWidth: "calc(100vw - 2rem)",
        overflow: "hidden",
        transition: "opacity 0.3s, transform 0.3s",
        opacity: exiting ? 0 : 1,
        transform: exiting ? "translateX(8px) scale(0.97)" : "translateX(0) scale(1)",
      }}
    >
      {/* Icon */}
      <span style={{ color: colors.icon, flexShrink: 0, marginTop: 1 }}>
        {item.type === "success" ? (
          <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : item.type === "error" ? (
          <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01" />
          </svg>
        ) : (
          <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16v-4m0-4h.01" />
          </svg>
        )}
      </span>

      {/* Message */}
      <p style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 1.45 }}>{item.message}</p>

      {/* Close */}
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss"
        style={{ flexShrink: 0, marginTop: 1, color: colors.icon, background: "none", border: "none", cursor: "pointer", opacity: 0.7 }}
      >
        <svg width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Progress bar */}
      <div
        style={{ position: "absolute", bottom: 0, left: 0, height: 3, background: colors.bar, width: `${progress}%`, borderRadius: "0 0 10px 10px" }}
      />
    </div>
  );
}

export function ToastContainer({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
  if (toasts.length === 0) return null;
  return (
    <div style={{ position: "fixed", top: 72, right: 16, zIndex: 200, display: "flex", flexDirection: "column", gap: 8, pointerEvents: "none" }}>
      {toasts.map((t) => (
        <div key={t.id} style={{ pointerEvents: "auto" }}>
          <SingleToast item={t} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}

let _nextId = 0;

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((message: string, type: ToastType = "error") => {
    const id = `toast-${++_nextId}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, push, dismiss };
}
