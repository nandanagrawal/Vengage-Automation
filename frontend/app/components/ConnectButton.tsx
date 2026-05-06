"use client";

import { qboConnectUrl, qboAuthDelete } from "@/lib/api";
import { useQboStatus } from "@/lib/useQboStatus";

export default function ConnectButton() {
  const { status, error } = useQboStatus();
  const connected = status?.connected ?? false;

  const handleClick = async () => {
    if (connected) return;
    window.location.href = qboConnectUrl();
  };

  const handleDisconnect = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await qboAuthDelete<{ disconnected?: boolean }>("/disconnect");
      window.location.reload();
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={connected}
        className={`
        relative inline-flex items-center gap-2.5 px-7 py-3.5 rounded-xl font-semibold text-sm
        transition-all duration-300 select-none overflow-hidden
        ${connected
          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 cursor-default"
          : "shimmer-btn text-white hover:scale-105 hover:shadow-xl hover:shadow-indigo-500/25 active:scale-95"
        }
      `}
      >
        {connected && (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        )}
        {!connected && (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        )}
        {connected ? "Connected to QuickBooks" : "Connect to QuickBooks"}
      </button>
      {connected && (
        <button
          type="button"
          onClick={handleDisconnect}
          className="text-xs text-slate-500 hover:text-slate-300 underline underline-offset-2"
        >
          Disconnect
        </button>
      )}
      {error && (
        <p className="text-xs text-amber-400/90 max-w-xs text-center">
          Could not reach QuickBooks auth API — check NEXT_PUBLIC_API_URL (backend origin) and that uvicorn is running.
        </p>
      )}
    </div>
  );
}
