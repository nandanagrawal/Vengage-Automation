"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
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

  const field = "w-full rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition";

  return (
    <div className="w-full max-w-md animate-fadeInUp">
      {/* Logo */}
      <div className="flex flex-col items-center mb-10">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center mb-4 animate-float">
          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight">Vengage</h1>
        <p className="text-slate-500 text-sm mt-1">Sign in to your account</p>
      </div>

      <div className="rounded-2xl border border-white/[0.08] p-8" style={{ background: "var(--bg-card)" }}>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Email address
            </label>
            <input
              type="email"
              required
              autoComplete="email"
              className={field}
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              autoComplete="current-password"
              className={field}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && (
            <p className="text-rose-400 text-sm rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full shimmer-btn py-3 rounded-xl text-white text-sm font-semibold hover:scale-[1.01] active:scale-[0.99] transition-transform disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>

      <p className="text-center text-slate-600 text-xs mt-6">
        New account?{" "}
        <span className="text-slate-400">Ask your admin to create one via the API</span>
      </p>

      <p className="text-center mt-4">
        <Link href="/" className="text-slate-600 text-xs hover:text-slate-400 transition-colors">
          ← Back to home
        </Link>
      </p>
    </div>
  );
}
