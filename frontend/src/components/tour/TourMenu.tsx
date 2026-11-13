import { useState } from "react";
import { Compass, LifeBuoy, X } from "lucide-react";
import { TOURS, TOUR_INDEX } from "./tours";
import { useTour } from "./TourProvider";
import { useCaseContext } from "@/context/CaseContext";
import { cn } from "@/lib/cn";

const WELCOME_KEY = "red-thread.tour.welcome-seen";

export function hasSeenWelcome(): boolean {
  try {
    return window.localStorage.getItem(WELCOME_KEY) === "1";
  } catch {
    return true;
  }
}

function markWelcomeSeen() {
  try {
    window.localStorage.setItem(WELCOME_KEY, "1");
  } catch {
    // Ignore storage failures; the welcome simply shows again.
  }
}

/** First-login introduction. Offers a guided tour or free exploration. */
export function WelcomeDialog({ caseId }: { caseId: string | null }) {
  const [open, setOpen] = useState(() => !hasSeenWelcome());
  const { start } = useTour();

  if (!open) return null;

  const close = () => {
    markWelcomeSeen();
    setOpen(false);
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm"
        aria-hidden="true"
        onClick={close}
      />
      <div
        role="dialog"
        aria-label="Welcome to Red Thread"
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl"
      >
        <div className="app-aurora absolute inset-0 opacity-60" aria-hidden="true" />
        <div className="relative p-6 sm:p-8">
          <button
            type="button"
            onClick={close}
            aria-label="Close welcome"
            className="absolute right-4 top-4 rounded-md p-1 text-muted transition hover:text-primary"
          >
            <X size={16} />
          </button>

          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-2/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-accent-fill" />
            Welcome
          </p>

          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-primary">
            Every evidence has a connection
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-secondary">
            Red Thread turns fragmented files into a traceable investigation. Take a short
            guided tour of the real interface, or explore on your own — you can restart any
            tour later from Help.
          </p>

          <ol className="mt-5 space-y-2 text-xs text-muted">
            {[
              "Upload evidence and verify its SHA-256 digest.",
              "Review the events the parsers extracted.",
              "Explore relationships and their supporting records.",
              "Ask the assistant, then review every finding yourself.",
            ].map((item, index) => (
              <li key={item} className="flex gap-2.5">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[9px] font-semibold text-accent">
                  {index + 1}
                </span>
                {item}
              </li>
            ))}
          </ol>

          <div className="mt-6 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => {
                markWelcomeSeen();
                setOpen(false);
                start("first-investigation", caseId);
              }}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-accent-fill px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-fill-hover"
            >
              <Compass size={15} />
              Start guided tour
            </button>
            <button
              type="button"
              onClick={close}
              className="inline-flex flex-1 items-center justify-center rounded-lg border border-line bg-surface-2/70 px-4 py-2.5 text-sm font-medium text-secondary transition hover:text-primary"
            >
              Explore on my own
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Persistent Help entry point listing every tour. */
export function TourMenu() {
  const [open, setOpen] = useState(false);
  const { start, activeTour } = useTour();
  const { selectedCaseId } = useCaseContext();

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-label="Help and guided tours"
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-[11px] font-medium transition",
          activeTour
            ? "border-accent/40 bg-accent-soft text-accent"
            : "bg-surface-2/70 text-secondary hover:text-primary",
        )}
      >
        <LifeBuoy size={13} />
        <span className="hidden sm:inline">Help</span>
      </button>

      {open ? (
        <>
          <div
            className="fixed inset-0 z-40"
            aria-hidden="true"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-line bg-surface shadow-2xl">
            <div className="border-b border-line px-3.5 py-2.5">
              <p className="text-xs font-semibold text-primary">Guided tours</p>
              <p className="mt-0.5 text-[10px] leading-relaxed text-muted">
                Each tour walks through real screens and controls.
              </p>
            </div>
            <ul className="max-h-[320px] overflow-auto p-1.5">
              {TOURS.map((tour) => {
                const available = TOUR_INDEX.has(tour.id);
                return (
                  <li key={tour.id}>
                    <button
                      type="button"
                      disabled={!available}
                      onClick={() => {
                        setOpen(false);
                        start(tour.id, selectedCaseId);
                      }}
                      className="w-full rounded-lg px-2.5 py-2 text-left transition hover:bg-surface-2"
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-medium text-primary">
                          {tour.name}
                        </span>
                        <span className="font-mono text-[9px] text-muted">
                          {tour.steps.length} steps
                        </span>
                      </span>
                      <span className="mt-0.5 block text-[10px] leading-relaxed text-muted">
                        {tour.description}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="border-t border-line px-3.5 py-2">
              <p className="text-[10px] leading-relaxed text-muted">
                Press Esc or Skip at any time. Navigation is never blocked after a tour.
              </p>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
