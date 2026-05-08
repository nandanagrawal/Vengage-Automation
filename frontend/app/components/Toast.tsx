"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type ToastType = "error" | "success" | "info";

export type ToastItem = {
  id: string;
  message: string;
  type: ToastType;
};

function SingleToast({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
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
    error: {
      border: "border-rose-500/30",
      bg: "bg-[#1c0e10]",
      bar: "bg-rose-500",
      icon: "text-rose-400",
    },
    success: {
      border: "border-emerald-500/30",
      bg: "bg-[#0c1a10]",
      bar: "bg-emerald-500",
      icon: "text-emerald-400",
    },
    info: {
      border: "border-indigo-500/30",
      bg: "bg-[#0e1020]",
      bar: "bg-indigo-500",
      icon: "text-indigo-400",
    },
  }[item.type];

  return (
    <div
      className={`
        relative flex items-start gap-3 px-4 pt-3 pb-4 rounded-xl border shadow-2xl w-80 max-w-[calc(100vw-2rem)] overflow-hidden
        ${colors.border} ${colors.bg}
        transition-all duration-300 ease-out
        ${exiting ? "opacity-0 translate-x-6 scale-95" : "opacity-100 translate-x-0 scale-100"}
      `}
    >
      {/* Icon */}
      <span className={`mt-0.5 shrink-0 ${colors.icon}`}>
        {item.type === "success" ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : item.type === "error" ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16v-4m0-4h.01" />
          </svg>
        )}
      </span>

      {/* Message */}
      <p className="flex-1 text-sm text-white leading-snug">{item.message}</p>

      {/* Close */}
      <button
        type="button"
        onClick={dismiss}
        className="shrink-0 mt-0.5 text-slate-500 hover:text-white transition-colors"
        aria-label="Dismiss"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Progress bar */}
      <div
        className={`absolute bottom-0 left-0 h-0.5 ${colors.bar} transition-none`}
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}

export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-20 right-4 z-[200] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
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
