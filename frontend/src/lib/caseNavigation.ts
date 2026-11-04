export function casePathForSelection(pathname: string, nextCaseId: string): string | null {
  const match = pathname.match(/^\/cases\/[^/]+(\/.*)?$/);
  if (!match) return null;
  return `/cases/${nextCaseId}${match[1] ?? ""}`;
}

export function hasActiveCase(caseId: string | null | undefined): boolean {
  return Boolean(caseId && caseId.trim());
}
