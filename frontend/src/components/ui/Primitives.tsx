import type { ReactNode } from "react";
import { Info } from "lucide-react";

export function Tooltip({
  text,
  children,
}: {
  text: string;
  children: ReactNode;
}) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1.5 w-56 -translate-x-1/2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[11px] leading-snug text-secondary opacity-0 shadow-card transition group-focus-within:opacity-100 group-hover:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}

export function InfoHint({ text }: { text: string }) {
  return (
    <Tooltip text={text}>
      <button
        type="button"
        aria-label={text}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted transition hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
      >
        <Info size={12} />
      </button>
    </Tooltip>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: { value: T; label: string; count?: number }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-1.5">
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(tab.value)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
              active
                ? "border-accent/50 bg-accent/10 text-accent"
                : "border-line bg-surface-2/60 text-secondary hover:border-accent/30 hover:text-accent"
            }`}
          >
            {tab.label}
            {tab.count !== undefined ? (
              <span className="font-mono text-[10px] opacity-70">{tab.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; icon?: ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex rounded-full border border-line bg-surface-2/60 p-0.5"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition ${
              active ? "bg-accent/15 text-accent" : "text-muted hover:text-secondary"
            }`}
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-lg bg-surface-2 ${className}`}
    />
  );
}

export function PageIntro({
  what,
  why,
  next,
}: {
  what: string;
  why: string;
  next: string;
}) {
  return (
    <div className="mb-4 grid gap-2 rounded-xl border border-line bg-surface-2/40 px-4 py-3 text-xs leading-relaxed text-muted sm:grid-cols-3">
      <p>
        <span className="font-semibold text-secondary">What this is: </span>
        {what}
      </p>
      <p>
        <span className="font-semibold text-secondary">Why it matters: </span>
        {why}
      </p>
      <p>
        <span className="font-semibold text-secondary">What to do: </span>
        {next}
      </p>
    </div>
  );
}
