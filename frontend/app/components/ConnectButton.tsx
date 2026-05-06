"use client";

import { useState } from "react";

export default function ConnectButton() {
  const [state, setState] = useState<"idle" | "loading" | "connected">("idle");

  const handleClick = () => {
    if (state === "connected") return;
    setState("loading");
    setTimeout(() => setState("connected"), 1800);
  };

  return (
    <button
      onClick={handleClick}
      disabled={state === "loading"}
      className={`
        relative inline-flex items-center gap-2.5 px-7 py-3.5 rounded-xl font-semibold text-sm
        transition-all duration-300 select-none overflow-hidden
        ${state === "connected"
          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 cursor-default"
          : state === "loading"
          ? "shimmer-btn text-white cursor-wait opacity-90"
          : "shimmer-btn text-white hover:scale-105 hover:shadow-xl hover:shadow-indigo-500/25 active:scale-95"
        }
      `}
    >
      {state === "loading" && (
        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {state === "connected" && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      )}
      {state === "idle" && (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      )}
      {state === "idle" && "Connect to QuickBooks"}
      {state === "loading" && "Authorizing…"}
      {state === "connected" && "Connected"}
    </button>
  );
}
