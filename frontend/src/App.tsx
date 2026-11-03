import { useEffect } from "react";
import {
  BrowserRouter,
  Outlet,
  Route,
  Routes,
  useParams,
} from "react-router-dom";
import { CaseProvider, useCaseContext } from "@/context/CaseContext";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/pages/DashboardPage";
import { CasesPage } from "@/pages/CasesPage";
import { CaseOverviewPage } from "@/pages/CaseOverviewPage";
import { EvidenceVaultPage } from "@/pages/EvidenceVaultPage";
import { EvidenceIntakePage } from "@/pages/EvidenceIntakePage";
import { AuthAnalysisPage } from "@/pages/AuthAnalysisPage";
import { TimelinePage } from "@/pages/TimelinePage";
import { GraphPage } from "@/pages/GraphPage";
import { FindingsPage } from "@/pages/FindingsPage";
import { AiAssistantPage } from "@/pages/AiAssistantPage";
import { ReportsPage } from "@/pages/ReportsPage";

function CaseRouteLayout() {
  const { caseId } = useParams<{ caseId: string }>();
  const { setSelectedCaseId } = useCaseContext();

  useEffect(() => {
    if (caseId) setSelectedCaseId(caseId);
  }, [caseId, setSelectedCaseId]);

  return <Outlet />;
}

export function App() {
  return (
    <BrowserRouter>
      <CaseProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="cases" element={<CasesPage />} />
            <Route path="cases/:caseId" element={<CaseRouteLayout />}>
              <Route index element={<CaseOverviewPage />} />
              <Route path="evidence" element={<EvidenceVaultPage />} />
              <Route path="evidence/intake" element={<EvidenceIntakePage />} />
              <Route path="auth" element={<AuthAnalysisPage />} />
              <Route path="timeline" element={<TimelinePage />} />
              <Route path="graph" element={<GraphPage />} />
              <Route path="findings" element={<FindingsPage />} />
              <Route path="ai" element={<AiAssistantPage />} />
              <Route path="reports" element={<ReportsPage />} />
            </Route>
            <Route path="*" element={<DashboardPage />} />
          </Route>
        </Routes>
      </CaseProvider>
    </BrowserRouter>
  );
}
