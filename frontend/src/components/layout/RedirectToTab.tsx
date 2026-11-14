import { Navigate, useParams } from "react-router-dom";

/**
 * Keeps old bookmarks working after consolidation.
 *
 * The standalone timeline, spatial and findings routes still exist so nothing
 * breaks, but they open the matching tab inside Crime reconstruction rather
 * than presenting a separate workflow. A deep link that targets one record is
 * passed through so it can be inspected in place.
 */
export function RedirectToTab({ tab, keep = [] }: { tab: string; keep?: string[] }) {
  const { caseId } = useParams<{ caseId: string }>();
  const params = new URLSearchParams(window.location.search);
  const forwarded = new URLSearchParams();
  for (const key of keep) {
    const value = params.get(key);
    if (value) forwarded.set(key, value);
  }
  forwarded.set("tab", tab);
  return (
    <Navigate
      to={`/cases/${caseId}/reconstruction?${forwarded.toString()}`}
      replace
    />
  );
}
