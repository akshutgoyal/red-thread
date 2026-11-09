import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, X } from "lucide-react";
import type { GuidanceAttention, GuidanceResponse } from "@/types";
import { Button } from "@/components/ui/Button";

const TONE_STYLES = {
  info: {
    wrap: "border-accent/30 bg-accent/5",
    icon: "text-accent",
    button: "primary" as const,
  },
  warning: {
    wrap: "border-amber-300/60 bg-amber-50/80 dark:border-amber-500/30 dark:bg-amber-500/5",
    icon: "text-amber-600 dark:text-amber-300",
    button: "secondary" as const,
  },
  critical: {
    wrap: "border-rose-300/60 bg-rose-50/80 dark:border-rose-500/30 dark:bg-rose-500/5",
    icon: "text-rose-600 dark:text-rose-300",
    button: "primary" as const,
  },
};

export function NextActionPanel({
  guidance,
  onDismiss,
}: {
  guidance: GuidanceResponse;
  onDismiss?: () => void;
}) {
  const action = guidance.next_action;
  const tone = TONE_STYLES[action.tone] ?? TONE_STYLES.info;

  return (
    <div className={`rounded-2xl border px-4 py-3.5 ${tone.wrap}`}>
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 ${tone.icon}`}>
          {action.tone === "info" ? (
            <ArrowRight size={18} />
          ) : (
            <AlertTriangle size={18} />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
            Next recommended action
          </p>
          <p className="mt-0.5 text-sm font-semibold text-primary">{action.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-secondary">{action.reason}</p>
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <Link to={action.href}>
              <Button size="sm" variant={tone.button} icon={<ArrowRight size={13} />}>
                {action.action_label}
              </Button>
            </Link>
          </div>
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss recommendation for this session"
            className="rounded-md p-1 text-muted transition hover:text-secondary"
          >
            <X size={14} />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function AttentionList({
  items,
  onSelect,
}: {
  items: GuidanceAttention[];
  onSelect?: (item: GuidanceAttention) => void;
}) {
  if (items.length === 0) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted">
        <CheckCircle2 size={14} className="text-emerald-500" />
        Nothing needs attention right now.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.kind}>
          <button
            type="button"
            onClick={() => onSelect?.(item)}
            className="flex w-full items-start gap-2.5 rounded-xl border border-line bg-surface-2/40 px-3 py-2 text-left transition hover:border-accent/40"
          >
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" />
            <span className="min-w-0">
              <span className="block text-xs font-medium text-primary">
                {item.title}
                {item.count > 0 ? (
                  <span className="ml-1.5 font-mono text-[10px] text-muted">
                    {item.count}
                  </span>
                ) : null}
              </span>
              <span className="mt-0.5 block text-[11px] leading-snug text-muted">
                {item.detail}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function useSessionDismiss(key: string) {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(key) === "1";
    } catch {
      return false;
    }
  });
  const dismiss = () => {
    try {
      sessionStorage.setItem(key, "1");
    } catch {
      // ignore storage failures
    }
    setDismissed(true);
  };
  return { dismissed, dismiss };
}
