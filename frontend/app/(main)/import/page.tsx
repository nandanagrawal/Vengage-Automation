"use client";

import { useState, useRef } from "react";

const recentImports = [
  { name: "customers_may_2025.csv", rows: 142, status: "Done",    time: "Today 09:12"   },
  { name: "invoice_batch_q1.json",  rows: 88,  status: "Done",    time: "Yesterday"     },
  { name: "customers_apr.csv",      rows: 201, status: "Done",    time: "Apr 30"        },
  { name: "batch_test.csv",         rows: 12,  status: "Failed",  time: "Apr 28"        },
];

export default function ImportPage() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File | null) => { if (f) setFile(f); };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8 animate-fadeInUp">
        <h1 className="text-2xl font-bold text-white tracking-tight">Import</h1>
        <p className="text-slate-500 text-sm mt-1">Upload a CSV or JSON file to import customer and invoice data.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        {/* Upload card */}
        <div
          className="rounded-2xl border border-white/[0.07] p-6 animate-fadeInUp delay-100"
          style={{ background: "var(--bg-card)" }}
        >
          <h2 className="text-white font-semibold text-sm mb-4">Upload File</h2>

          {/* Drop zone */}
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
            className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 cursor-pointer transition-all duration-200
              ${dragging
                ? "border-indigo-500/60 bg-indigo-500/10 scale-[1.01]"
                : file
                ? "border-emerald-500/40 bg-emerald-500/5"
                : "border-white/[0.1] hover:border-indigo-500/40 hover:bg-indigo-500/5"
              }`}
          >
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-colors ${
              file ? "bg-emerald-500/20 border border-emerald-500/25" : "bg-white/[0.04] border border-white/[0.08]"
            }`}>
              {file ? (
                <svg className="w-7 h-7 text-emerald-400" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-7 h-7 text-slate-500" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              )}
            </div>

            {file ? (
              <div className="text-center">
                <p className="text-emerald-400 text-sm font-semibold">{file.name}</p>
                <p className="text-slate-500 text-xs mt-1">{(file.size / 1024).toFixed(1)} KB — ready to import</p>
              </div>
            ) : (
              <div className="text-center">
                <p className="text-white text-sm font-medium">Drop your file here</p>
                <p className="text-slate-500 text-xs mt-1">or click to browse · CSV, JSON up to 10 MB</p>
              </div>
            )}

            <input ref={inputRef} id="file-upload" type="file" accept=".csv,.json"
              className="sr-only" onChange={(e) => handleFile(e.target.files?.[0] ?? null)} />
          </div>

          {/* Options */}
          <div className="mt-5 grid grid-cols-2 gap-3">
            {[
              { label: "Skip duplicate rows",  checked: true  },
              { label: "Auto-match customers", checked: true  },
              { label: "Validate emails",       checked: false },
              { label: "Dry run first",         checked: false },
            ].map(({ label, checked }) => (
              <label key={label} className="flex items-center gap-2.5 cursor-pointer group">
                <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                  checked ? "bg-indigo-600 border-indigo-600" : "border-white/20 bg-transparent"
                }`}>
                  {checked && <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7"/></svg>}
                </div>
                <span className="text-slate-400 text-xs group-hover:text-slate-300 transition-colors">{label}</span>
              </label>
            ))}
          </div>

          <button
            disabled={!file}
            className={`mt-6 w-full py-3 rounded-xl text-sm font-semibold transition-all duration-200
              ${file
                ? "shimmer-btn text-white hover:scale-[1.01] active:scale-[0.99]"
                : "bg-white/[0.04] text-slate-600 border border-white/[0.06] cursor-not-allowed"
              }`}
          >
            {file ? "Start Import" : "Select a file to continue"}
          </button>
        </div>

        {/* Recent imports */}
        <div
          className="rounded-2xl border border-white/[0.07] overflow-hidden animate-fadeInUp delay-200"
          style={{ background: "var(--bg-card)" }}
        >
          <div className="px-5 py-4 border-b border-white/[0.06]">
            <h2 className="text-white font-semibold text-sm">Recent Imports</h2>
          </div>

          <div className="divide-y divide-white/[0.04]">
            {recentImports.map(({ name, rows, status, time }) => (
              <div key={name} className="px-5 py-3.5 hover:bg-white/[0.03] transition-colors">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <p className="text-white text-xs font-medium truncate">{name}</p>
                  <span className={`text-xs font-semibold shrink-0 ${status === "Done" ? "text-emerald-400" : "text-red-400"}`}>
                    {status}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 text-xs">{rows} rows</span>
                  <span className="text-slate-700 text-xs">{time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
