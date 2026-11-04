import { Badge } from "@/components/ui/Badge";
import { humanize } from "@/lib/format";
import { cn } from "@/lib/cn";

const STYLES: Record<string, string> = {
  observation: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-500/40 dark:bg-slate-500/10 dark:text-slate-200",
  correlation: "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200",
  inference: "border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-200",
  hypothesis: "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
};

export function ClassificationBadge({ classification }: { classification: string }) {
  return (
    <Badge className={cn("border-line bg-surface-2 text-secondary", STYLES[classification])}>
      {humanize(classification)}
    </Badge>
  );
}
