import type { ReactNode } from "react";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { GuidanceStage, GuidanceStageStatus } from "@/types";

const STATUS_STYLES: Record<GuidanceStageStatus, string> = {
  complete:
    "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200",
  in_progress:
    "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
  not_started: "border-line bg-surface-2 text-muted",
};

const STATUS_LABEL: Record<GuidanceStageStatus, string> = {
  complete: "Complete",
  in_progress: "In progress",
  not_started: "Not started",
};

export function stageStatusStyles(status: GuidanceStageStatus): string {
  return STATUS_STYLES[status];
}

export function stageStatusLabel(status: GuidanceStageStatus): string {
  return STATUS_LABEL[status];
}

function StatusIcon({ status }: { status: GuidanceStageStatus }) {
  if (status === "complete") return <CheckCircle2 size={13} />;
  if (status === "in_progress") return <Loader2 size={13} />;
  return <Circle size={13} />;
}

export function ProgressBar({
  completed,
  total,
  label,
}: {
  completed: number;
  total: number;
  label?: string;
}) {
  const safeTotal = Math.max(total, 1);
  const percent = Math.min(100, Math.round((completed / safeTotal) * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-[11px] text-muted">
        <span>{label ?? "Progress"}</span>
        <span className="font-mono text-secondary">
          {completed} / {total}
        </span>
      </div>
      <div
        className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label={label ?? "Investigation progress"}
      >
        <div
          className="h-full rounded-full bg-accent transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export function InvestigationStepper({
  stages,
  compact = false,
  activeKey,
}: {
  stages: GuidanceStage[];
  compact?: boolean;
  activeKey?: string;
}) {
  const completed = stages.filter((stage) => stage.status === "complete").length;
  return (
    <div>
      <ProgressBar
        completed={completed}
        total={stages.length}
        label="Investigation stages complete"
      />
      <ol className="mt-3 grid gap-2 md:grid-cols-3">
        {stages.map((stage) => {
          const active = stage.key === activeKey;
          return (
            <li key={stage.key}>
              <a
                href={stage.href}
                className={`block rounded-xl border px-3 py-2.5 transition hover:border-accent/40 ${
                  active ? "border-accent/50 bg-accent/5" : "border-line bg-surface/60"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
                    Step {stage.index}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
                      STATUS_STYLES[stage.status]
                    }`}
                  >
                    <StatusIcon status={stage.status} />
                    {STATUS_LABEL[stage.status]}
                  </span>
                </div>
                <p className="mt-1 text-xs font-medium text-primary">{stage.title}</p>
                {!compact ? (
                  <>
                    <p className="mt-0.5 text-[11px] leading-snug text-muted">
                      {stage.description}
                    </p>
                    <dl className="mt-2 space-y-1 text-[10px] leading-snug text-muted">
                      <div>
                        <dt className="inline font-semibold text-secondary">Do this: </dt>
                        <dd className="inline">{stage.what_to_do}</dd>
                      </div>
                      <div>
                        <dt className="inline font-semibold text-secondary">You get: </dt>
                        <dd className="inline">{stage.output}</dd>
                      </div>
                      {stage.next_step ? (
                        <div>
                          <dt className="inline font-semibold text-secondary">Then: </dt>
                          <dd className="inline">{stage.next_step}</dd>
                        </div>
                      ) : null}
                    </dl>
                  </>
                ) : null}
                {stage.total_count > 0 ? (
                  <p className="mt-1.5 font-mono text-[10px] text-muted">
                    {stage.completed_count} / {stage.total_count}
                  </p>
                ) : null}
              </a>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function StageStatusBadge({ status }: { status: GuidanceStageStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
        STATUS_STYLES[status]
      }`}
    >
      <StatusIcon status={status} />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function AttentionDot({ tone }: { tone: "info" | "warning" | "critical" }) {
  const styles =
    tone === "critical"
      ? "text-rose-500"
      : tone === "warning"
        ? "text-amber-500"
        : "text-accent";
  if (tone === "info") return <Circle size={12} className={styles} />;
  return <XCircle size={12} className={styles} />;
}

export function KeyValue({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
        {label}
      </dt>
      <dd className={`mt-0.5 text-sm text-secondary ${mono ? "font-mono text-xs" : ""}`}>
        {children}
      </dd>
    </div>
  );
}
