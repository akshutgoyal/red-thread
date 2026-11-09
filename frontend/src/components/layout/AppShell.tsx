import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { NextActionStrip } from "@/components/guidance/NextActionStrip";
import { WalkthroughOverlay, useWalkthrough } from "@/components/guidance/Walkthrough";
import { useAuth } from "@/context/AuthContext";

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();
  const walkthrough = useWalkthrough(Boolean(user?.is_demo));

  return (
    <div className="flex h-screen overflow-hidden bg-app text-primary">
      <div className="pointer-events-none fixed inset-0 app-aurora" />
      <div className="relative hidden h-screen shrink-0 lg:block">
        <Sidebar onStartWalkthrough={user?.is_demo ? walkthrough.restart : undefined} />
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm dark:bg-slate-950/80"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div className="relative">
            <Sidebar
              onNavigate={() => setMobileOpen(false)}
              onStartWalkthrough={user?.is_demo ? walkthrough.restart : undefined}
            />
          </div>
        </div>
      ) : null}

      <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <TopBar onMenu={() => setMobileOpen(true)} />
        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-[1500px]">
            <NextActionStrip />
            <Outlet />
          </div>
        </main>
        <footer className="shrink-0 border-t border-line bg-surface/70 px-6 py-3 text-[10px] text-muted backdrop-blur">
          Red Thread · Local-first forensic analysis · Findings require human review
          and are not proof of criminal activity.
        </footer>
      </div>

      {user?.is_demo ? (
        <WalkthroughOverlay
          open={walkthrough.open}
          onClose={walkthrough.close}
          step={walkthrough.step}
          onStepChange={walkthrough.setStep}
        />
      ) : null}
    </div>
  );
}
