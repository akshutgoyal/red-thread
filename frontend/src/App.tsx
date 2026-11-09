import { Fragment, useEffect } from "react";
import {
  BrowserRouter,
  Outlet,
  Route,
  Routes,
  useParams,
} from "react-router-dom";
import { CaseProvider, useCaseContext } from "@/context/CaseContext";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { LoginPage } from "@/pages/LoginPage";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { CasesPage } from "@/pages/CasesPage";
import { CaseOverviewPage } from "@/pages/CaseOverviewPage";
import { EvidenceVaultPage } from "@/pages/EvidenceVaultPage";
import { EvidenceIntakePage } from "@/pages/EvidenceIntakePage";
import { AuthAnalysisPage } from "@/pages/AuthAnalysisPage";
import { TimelinePage } from "@/pages/TimelinePage";
import { EventsPage } from "@/pages/EventsPage";
import { GraphPage } from "@/pages/GraphPage";
import { FindingsPage } from "@/pages/FindingsPage";
import { AiAssistantPage } from "@/pages/AiAssistantPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { EntityExplorerPage } from "@/pages/EntityExplorerPage";
import { SpatialPage } from "@/pages/SpatialPage";
import { ReconstructionPage } from "@/pages/ReconstructionPage";

function AuthenticatedLayout() {
  const { user } = useAuth();
  return (
    <CaseProvider key={user?.id ?? "anonymous"}>
      <AppShell />
    </CaseProvider>
  );
}

function CaseRouteLayout() {
  const { caseId } = useParams<{ caseId: string }>();
  const { setSelectedCaseId } = useCaseContext();

  useEffect(() => {
    if (caseId) setSelectedCaseId(caseId);
  }, [caseId, setSelectedCaseId]);

  return (
    <Fragment key={caseId}>
      <Outlet />
    </Fragment>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AuthenticatedLayout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="cases" element={<CasesPage />} />
            <Route path="cases/:caseId" element={<CaseRouteLayout />}>
              <Route index element={<CaseOverviewPage />} />
              <Route path="evidence" element={<EvidenceVaultPage />} />
              <Route path="evidence/intake" element={<EvidenceIntakePage />} />
              <Route path="entities" element={<EntityExplorerPage />} />
              <Route path="auth" element={<AuthAnalysisPage />} />
              <Route path="events" element={<EventsPage />} />
              <Route path="timeline" element={<TimelinePage />} />
              <Route path="graph" element={<GraphPage />} />
              <Route path="spatial" element={<SpatialPage />} />
              <Route path="findings" element={<FindingsPage />} />
              <Route path="reconstruction" element={<ReconstructionPage />} />
              <Route path="workspace" element={<ReconstructionPage />} />
              <Route path="ai" element={<AiAssistantPage />} />
              <Route path="reports" element={<ReportsPage />} />
            </Route>
            <Route path="*" element={<DashboardPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
