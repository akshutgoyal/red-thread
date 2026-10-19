import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Inbox, RefreshCcw } from "lucide-react";
import { Button } from "./Button";
import { cn } from "@/lib/cn";

export function LoadingState({
  label = "Loading…",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 py-16",
        className,
      )}
    >
      <span className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line-strong bg-surface-2/30 py-16 text-center",
        className,
      )}
    >
      <span className="rounded-full border border-line bg-surface p-3 text-muted">
        <Icon size={22} />
      </span>
      <div>
        <p className="text-sm font-medium text-primary">{title}</p>
        {description ? (
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border border-rose-300 bg-rose-50 py-14 text-center dark:border-rose-500/20 dark:bg-rose-500/5",
        className,
      )}
    >
      <span className="rounded-full border border-rose-300 bg-rose-100 p-3 text-rose-600 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
        <AlertTriangle size={22} />
      </span>
      <div>
        <p className="text-sm font-medium text-rose-800 dark:text-rose-100">{title}</p>
        {message ? (
          <p className="mx-auto mt-1 max-w-lg text-xs leading-relaxed text-rose-700/80 dark:text-rose-200/70">
            {message}
          </p>
        ) : null}
      </div>
      {onRetry ? (
        <Button
          size="sm"
          variant="secondary"
          icon={<RefreshCcw size={14} />}
          onClick={onRetry}
        >
          Try again
        </Button>
      ) : null}
    </div>
  );
}
