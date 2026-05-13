import Sidebar from "@/app/components/Sidebar";
import Navbar from "@/app/components/Navbar";
import AppFooter from "@/app/components/AppFooter";
import QboGuard from "@/app/components/QboGuard";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <QboGuard>
      <div className="app-shell">
        <Sidebar />
        <div className="app-main">
          <Navbar />
          <main className="app-content">
            {children}
          </main>
          <AppFooter />
        </div>
      </div>
    </QboGuard>
  );
}
