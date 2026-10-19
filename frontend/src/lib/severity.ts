import type { FindingStatus, Severity } from "@/types";

export const SEVERITY_ORDER: Severity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "info",
];

export function severityStyle(severity: Severity | string): string {
  switch (severity) {
    case "critical":
      return "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200";
    case "high":
      return "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-500/40 dark:bg-orange-500/10 dark:text-orange-200";
    case "medium":
      return "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200";
    case "low":
      return "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200";
    default:
      return "border-line bg-surface-2 text-secondary";
  }
}

export function severityLabel(severity: Severity | string): string {
  return String(severity || "info").toUpperCase();
}

export function statusStyle(status: FindingStatus | string): string {
  switch (status) {
    case "accepted":
      return "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200";
    case "rejected":
      return "border-line bg-surface-2 text-secondary";
    case "needs_review":
      return "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200";
    case "needs_more_evidence":
      return "border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-200";
    default:
      return "border-accent/30 bg-accent/10 text-accent";
  }
}

export function confidenceStyle(confidence: string): string {
  switch (confidence) {
    case "exact":
    case "high":
      return "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200";
    case "ambiguous":
    case "medium":
      return "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200";
    case "inferred_year":
      return "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-500/40 dark:bg-orange-500/10 dark:text-orange-200";
    case "unknown":
    case "low":
      return "border-line bg-surface-2 text-secondary";
    default:
      return "border-line bg-surface-2 text-secondary";
  }
}
