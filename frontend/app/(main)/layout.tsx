import Sidebar from "@/app/components/Sidebar";
import Navbar from "@/app/components/Navbar";
import AppFooter from "@/app/components/AppFooter";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: "var(--bg-deep)" }}>
      <Navbar />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 overflow-y-auto dot-grid">
          <div className="p-8">{children}</div>
        </main>
      </div>

      <AppFooter />
    </div>
  );
}
