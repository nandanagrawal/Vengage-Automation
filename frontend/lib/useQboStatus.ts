"use client";

import { useCallback, useEffect, useState } from "react";

import { qboAuthGet, type QboStatus } from "@/lib/api";

export function useQboStatus() {
  const [status, setStatus] = useState<QboStatus | null>(null);
  const [error, setError] = useState(false);

  const refresh = useCallback(() => {
    qboAuthGet<QboStatus>("/status")
      .then((s) => {
        setStatus(s);
        setError(false);
      })
      .catch(() => {
        setError(true);
        setStatus({
          connected: false,
          realmId: null,
          tokenExpiry: null,
          environment: "sandbox",
        });
      });
  }, []);

  useEffect(() => {
    refresh();
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (url.searchParams.get("connected") === "true") {
      url.searchParams.delete("connected");
      const qs = url.searchParams.toString();
      window.history.replaceState({}, "", `${url.pathname}${qs ? `?${qs}` : ""}${url.hash}`);
      refresh();
    }
  }, [refresh]);

  return { status, error, refresh };
}
