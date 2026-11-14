import { useState, type HTMLAttributes, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-line bg-surface/80 shadow-card backdrop-blur-sm transition-shadow duration-200",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4",
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-wide text-primary">{title}</h2>
        {subtitle ? (
          <p className="mt-1 text-xs leading-relaxed text-muted">{subtitle}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}

/**
 * A card whose body starts collapsed.
 *
 * Used for secondary detail on long pages so the important information stays
 * near the top. Nothing is removed: the same content is one click away, and the
 * summary stays visible while collapsed.
 */
export function CollapsibleCard({
  title,
  subtitle,
  summary,
  children,
  defaultOpen = false,
  id,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  /** Shown in place of the body while collapsed, usually a count. */
  summary?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  id?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Card id={id}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        className="flex w-full items-start justify-between gap-3 rounded-2xl px-5 py-4 text-left transition hover:bg-surface-2/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      >
        <span className="min-w-0">
          <span className="block text-sm font-semibold tracking-wide text-primary">{title}</span>
          {subtitle ? (
            <span className="mt-1 block text-xs leading-relaxed text-muted">{subtitle}</span>
          ) : null}
          {!open && summary ? (
            <span className="mt-1.5 block text-xs font-medium text-primary">{summary}</span>
          ) : null}
        </span>
        <ChevronDown
          size={15}
          className={cn(
            "mt-0.5 shrink-0 text-muted transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      {open ? <div className="border-t border-line">{children}</div> : null}
    </Card>
  );
}
