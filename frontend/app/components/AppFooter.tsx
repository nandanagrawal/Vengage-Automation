export default function AppFooter() {
  return (
    <footer
      style={{ height: 40, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", borderTop: "1px solid var(--border)", background: "var(--surface)", fontSize: 11, color: "var(--text-4)" }}
    >
      <span>© 2025 Vengage · Invoice Automation</span>
      <span
        style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 8px", borderRadius: 12, background: "var(--warning-bg)", border: "1px solid var(--warning-border)", color: "var(--warning-text)", fontWeight: 600, fontSize: 10 }}
      >
        <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--warning)" }} />
        Sandbox
      </span>
    </footer>
  );
}
