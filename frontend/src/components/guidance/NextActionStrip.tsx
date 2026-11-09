import { useLocation, useParams } from "react-router-dom";
import { useGuidance } from "@/hooks/useApi";
import { NextActionPanel, useSessionDismiss } from "./GuidancePanels";
import { Skeleton } from "@/components/ui/Primitives";

/**
 * Persistent recommendation strip shown above every case page.
 *
 * The dashboard renders its own copy, so this is suppressed there to avoid two
 * identical panels on one screen.
 */
export function NextActionStrip() {
  const { caseId } = useParams<{ caseId: string }>();
  const location = useLocation();
  const { dismissed, dismiss } = useSessionDismiss(
    `red-thread.next-action.dismissed.${caseId ?? "none"}`,
  );
  const guidanceQuery = useGuidance(caseId);

  const onDashboard =
    location.pathname === "/" || location.pathname === `/cases/${caseId ?? ""}`;
  if (!caseId || onDashboard) return null;

  if (guidanceQuery.isLoading) {
    return <Skeleton className="mb-4 h-20 w-full" />;
  }
  if (dismissed || !guidanceQuery.data) return null;

  return (
    <div className="mb-4">
      <NextActionPanel guidance={guidanceQuery.data} onDismiss={dismiss} />
    </div>
  );
}
