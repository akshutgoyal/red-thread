import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Compass, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export interface WalkthroughStep {
  title: string;
  body: string;
  hint?: string;
  /** Path suffix under /cases/{id}. Empty string means the case overview. */
  route: string;
  /** Label shown on the button that opens the page, when it differs from Next. */
  openLabel?: string;
}

export const WALKTHROUGH_STEPS: WalkthroughStep[] = [
  {
    title: "Start with a case",
    route: "",
    body: "A case groups every file, event and finding for one investigation. The demo already has a case open so you can focus on the workflow.",
    hint: "Each case has its own evidence, timeline and report.",
  },
  {
    title: "Upload and preserve evidence",
    route: "/evidence/intake",
    body: "Evidence files are stored unchanged and hashed with SHA-256. That digest proves a later download matches what was originally received.",
    hint: "Open Evidence intake to see per-file processing status and warnings.",
  },
  {
    title: "Understand processing results",
    route: "/evidence",
    body: "Every file shows its own stages: uploaded, hashed, parsed, and whether records were skipped. Warnings explain what went wrong and whether the file is still usable.",
    hint: "A partially parsed file is still usable unless a warning says otherwise.",
  },
  {
    title: "Review extracted events",
    route: "/events",
    body: "Parsers turn files into readable events. On the Extracted events page you can search, inspect the original record, and mark each event relevant or not.",
    hint: "Review decisions are kept with an audit trail; evidence is never deleted.",
  },
  {
    title: "Explore the timeline",
    route: "/timeline",
    body: "The timeline orders events in time and groups those with a documented relationship. Proximity alone is a lead, never proof of causation.",
    hint: "Use the Correlated and Flagged toggles to narrow the view.",
  },
  {
    title: "Understand the relationship graph",
    route: "/graph",
    body: "Nodes are entities such as phone numbers, devices and accounts. Each line explains how two things are connected and which evidence supports it.",
    hint: "Simple mode is the default. Click a line to read its explanation.",
  },
  {
    title: "Review suspicious patterns",
    route: "/findings",
    body: "Findings describe what was observed, how confident the tooling is, and what alternative explanations exist. Nothing is presented as proven.",
    hint: "Open Findings to accept, dispute or annotate each one.",
  },
  {
    title: "Ask the AI copilot",
    route: "/ai",
    body: "The copilot answers only from this case's stored records. Every factual statement should point at evidence you can open.",
    hint: "Answers separate what was observed from interpretation and next steps.",
  },
  {
    title: "Generate the report",
    route: "/reports",
    body: "The report assembles evidence inventory, parsing results, timeline, relationships, findings, annotations and limitations into a draft for human review.",
    hint: "It is a draft, not a court-admissible document.",
  },
];

const STORAGE_KEY = "red-thread-walkthrough-step";

export function WalkthroughOverlay({
  open,
  onClose,
  step,
  onStepChange,
  caseId,
}: {
  open: boolean;
  onClose: () => void;
  step: number;
  onStepChange: (step: number) => void;
  caseId: string | null;
}) {
  const navigate = useNavigate();

  if (!open) return null;
  const current = WALKTHROUGH_STEPS[step];
  if (!current) return null;
  const last = step === WALKTHROUGH_STEPS.length - 1;

  /** Move to a step and open the page it describes, once a case is active. */
  function goTo(index: number) {
    const target = WALKTHROUGH_STEPS[index];
    if (!target) return;
    onStepChange(index);
    if (caseId) navigate(`/cases/${caseId}${target.route}`);
  }

  return (
    <div className="fixed inset-x-0 bottom-4 z-50 mx-auto w-[min(680px,calc(100vw-2rem))]">
      <div className="rounded-2xl border border-accent/30 bg-app/95 p-4 shadow-2xl backdrop-blur">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-accent/15 p-1.5 text-accent">
              <Compass size={15} />
            </span>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                Guided walkthrough · step {step + 1} of {WALKTHROUGH_STEPS.length}
              </p>
              <p className="text-sm font-semibold text-primary">{current.title}</p>
              {caseId ? (
                <p className="mt-0.5 text-[10px] text-muted">
                  Opens: {current.route || "case overview"}
                </p>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close walkthrough"
            className="rounded-md p-1 text-muted transition hover:text-secondary"
          >
            <X size={15} />
          </button>
        </div>

        <p className="mt-2.5 text-xs leading-relaxed text-secondary">{current.body}</p>
        {current.hint ? (
          <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{current.hint}</p>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            {WALKTHROUGH_STEPS.map((item, index) => (
              <button
                key={item.title}
                type="button"
                onClick={() => goTo(index)}
                aria-label={`Go to step ${index + 1}: ${item.title}`}
                className={cn(
                  "h-1.5 rounded-full transition",
                  index === step
                    ? "w-6 bg-accent"
                    : index < step
                      ? "w-1.5 bg-accent/50"
                      : "w-1.5 bg-line-strong",
                )}
              />
            ))}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              icon={<ArrowLeft size={12} />}
              onClick={() => goTo(Math.max(0, step - 1))}
              disabled={step === 0}
            >
              Back
            </Button>
            <Button
              size="sm"
              variant="primary"
              icon={last ? <Check size={12} /> : <ArrowRight size={12} />}
              onClick={() => {
                if (last) onClose();
                else goTo(step + 1);
              }}
            >
              {last ? "Finish" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Walkthrough state is per browser session so it can be restarted at any time. */
export function useWalkthrough(enabled: boolean) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(() => {
    if (!enabled) return false;
    try {
      return sessionStorage.getItem(STORAGE_KEY) === null;
    } catch {
      return false;
    }
  });
  const [step, setStep] = useState(() => {
    try {
      return Number(sessionStorage.getItem(STORAGE_KEY) ?? 0) || 0;
    } catch {
      return 0;
    }
  });

  useEffect(() => {
    if (!open) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, String(step));
    } catch {
      // ignore storage failures
    }
  }, [open, step]);

  /** Restart from the first step and open the page it describes. */
  const restart = (caseId: string | null) => {
    setStep(0);
    setOpen(true);
    if (caseId) navigate(`/cases/${caseId}${WALKTHROUGH_STEPS[0].route}`);
  };

  const close = () => {
    setOpen(false);
    try {
      sessionStorage.setItem(STORAGE_KEY, String(WALKTHROUGH_STEPS.length - 1));
    } catch {
      // ignore storage failures
    }
  };

  return { open, step, setStep, restart, close };
}
