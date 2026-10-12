"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken, fetchMe, getToken } from "@/lib/auth";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    // A token being present doesn't mean it's still valid — verify it against
    // the backend so an expired/invalid session is caught here and redirected
    // to login, rather than falling through to QboGuard (which would wrongly
    // report "QuickBooks not connected" on any failed request, auth or not).
    fetchMe()
      .then(() => setChecked(true))
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
  }, [router]);

  if (!checked) return null;

  return <>{children}</>;
}
