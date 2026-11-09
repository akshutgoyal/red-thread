import { Link } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Circle,
  CircleDot,
} from "lucide-react";
import type { GuidanceResponse, GuidanceStage } from "@/types";
import { cn } from "@/lib/cn";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

const STATE_STYLES: Record<
  GuidanceStage["status"],
  { dot: string; label: string; badge: string }
> = {
  complete: {
    dot: "border-emerald-400/60 bg-emerald-500/15 text-emerald-500 dark:text-emerald-300",
    label: "Complete",
    badge:
      "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200",
  },
  in_progress: {
    dot: "border-accent/60 bg-accent/15 text-accent",
    label: "In progress",
    badge: "border-accent/30 bg-accent/10 text-accent",
  },
  not_started: {
    dot: "border-line-strong bg-surface-2/60 text-muted",
    label: "Not started",
    badge: "border-line-strong bg-surface-2/60 text-muted",
  },
};

function StateDot({ state }: { state: GuidanceStage["status"] }) {
  if (state === "complete") return <Check size={11} />;
  if (state === "in_progress") return <CircleDot size={11} />;
  return <Circle size={10} />;
}

export function WorkflowTracker({
  guidance,
  compact = false,
}: {
  guidance: GuidanceResponse;
  compact?: boolean;
}) {
  const stages = guidance.stages;
  const completed = stages.filter((stage) => stage.status === "complete").length;

  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        {stages.map((stage) => {
          const style = STATE_STYLES[stage.status] ?? STATE_STYLES.not_started;
          return (
            <Link
              key={stage.key}
              to={stage.href}
              title={`${stage.title} — ${style.label}`}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition hover:opacity-80",
                style.badge,
              )}
            >
              {stage.index}
            </Link>
          );
        })}
        <span className="ml-1 text-[10px] text-muted">
          {completed}/{stages.length} complete
        </span>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Investigation progress"
        subtitle={`${completed} of ${stages.length} stages complete`}
      />
      <CardBody className="space-y-1.5">
        {stages.map((stage) => {
          const style = STATE_STYLES[stage.status] ?? STATE_STYLES.not_started;
          return (
            <Link
              key={stage.key}
              to={stage.href}
              className="group flex items-start gap-3 rounded-xl border border-transparent px-2 py-2 transition hover:border-line hover:bg-surface-2/40"
            >
              <span
                className={cn(
                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold",
                  style.dot,
                )}
              >
                <StateDot state={stage.status} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-medium text-primary">
                    {stage.index}. {stage.title}
                  </span>
                  <Badge className={style.badge}>{style.label}</Badge>
                </span>
                <span className="mt-0.5 block text-[11px] leading-snug text-muted">
                  {stage.description}
                </span>
                {stage.detail ? (
                  <span className="mt-0.5 block text-[10px] leading-snug text-muted/80">
                    {stage.detail}
                  </span>
                ) : null}
              </span>
              <ArrowRight
                size={13}
                className="mt-1 shrink-0 text-muted opacity-0 transition group-hover:opacity-100"
              />
            </Link>
          );
        })}
      </CardBody>
    </Card>
  );
}

export function WorkflowStepGuide({ guidance }: { guidance: GuidanceResponse }) {
  const current =
    guidance.stages.find((stage) => stage.status === "in_progress") ??
    guidance.stages.find((stage) => stage.status === "not_started");
  if (!current) return null;

  return (
    <div className="rounded-xl border border-line bg-surface-2/40 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
            You are on stage {current.index} of {guidance.stages.length}
          </p>
          <p className="mt-0.5 text-sm font-semibold text-primary">{current.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-secondary">{current.description}</p>
          <dl className="mt-2 grid gap-1 text-[11px] leading-relaxed text-muted sm:grid-cols-2">
            <div>
              <dt className="inline font-semibold text-secondary">You need to: </dt>
              <dd className="inline">{current.what_to_do}</dd>
            </div>
            <div>
              <dt className="inline font-semibold text-secondary">Output: </dt>
              <dd className="inline">{current.output}</dd>
            </div>
            {current.next_step ? (
              <div className="sm:col-span-2">
                <dt className="inline font-semibold text-secondary">Then: </dt>
                <dd className="inline">{current.next_step}</dd>
              </div>
            ) : null}
          </dl>
        </div>
        <Link to={current.href}>
          <Button size="sm" variant="secondary" icon={<ArrowRight size={13} />}>
            Go to this step
          </Button>
        </Link>
      </div>
    </div>
  );
}
