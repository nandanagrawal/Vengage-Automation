"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const navItems = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg className="w-[18px] h-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    href: "/customers",
    label: "Customers",
    icon: (
      <svg className="w-[18px] h-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
      </svg>
    ),
  },
  {
    href: "/invoices",
    label: "Configuration",
    icon: (
      <svg className="w-[18px] h-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    href: "/import",
    label: "Import",
    icon: (
      <svg className="w-[18px] h-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const [open, setOpen] = useState(true);
  const pathname = usePathname();

  return (
    <aside
      className="flex flex-col shrink-0 border-r border-white/[0.06] transition-all duration-300 ease-in-out"
      style={{
        width: open ? "220px" : "64px",
        background: "rgba(8,11,24,0.98)",
      }}
    >
      {/* Logo + toggle */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-white/[0.06]">
        {open && (
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="text-white font-bold text-sm tracking-tight truncate">Vengage</span>
          </div>
        )}

        <button
          onClick={() => setOpen(!open)}
          className={`w-8 h-8 rounded-lg border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.08] text-slate-400 hover:text-white flex items-center justify-center transition-all shrink-0 ${!open ? "mx-auto" : ""}`}
          aria-label="Toggle sidebar"
        >
          {open ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7M18 19l-7-7 7-7" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          )}
        </button>
      </div>

      {/* Nav section label */}
      {open && (
        <p className="px-4 pt-5 pb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
          Navigation
        </p>
      )}

      {/* Nav items */}
      <nav className="flex flex-col gap-1 px-2 pt-2 flex-1">
        {navItems.map(({ href, label, icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              title={!open ? label : undefined}
              className={`relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group
                ${active
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/25"
                  : "text-slate-500 hover:text-slate-200 hover:bg-white/[0.05] border border-transparent"
                }
                ${!open ? "justify-center" : ""}
              `}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full bg-indigo-500" />
              )}
              <span className={active ? "text-indigo-400" : "text-slate-600 group-hover:text-slate-300 transition-colors"}>
                {icon}
              </span>
              {open && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Bottom user area */}
      <div className="p-3 border-t border-white/[0.06]">
        <div className={`flex items-center gap-3 px-2 py-2 rounded-xl ${open ? "" : "justify-center"}`}>
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
            V
          </div>
          {open && (
            <div className="min-w-0">
              <p className="text-white text-xs font-semibold truncate">Admin</p>
              <p className="text-slate-600 text-[10px] truncate">admin@vengage.io</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
