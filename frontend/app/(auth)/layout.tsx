export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center dot-grid px-4"
      style={{ background: "var(--bg-deep)" }}>
      {children}
    </div>
  );
}
