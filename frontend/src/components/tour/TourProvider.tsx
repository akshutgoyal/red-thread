import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";

/**
 * Guided tours.
 *
 * A step points at a real element via a `data-tour` attribute and may require a
 * specific route. The engine navigates first, waits for the anchor to appear,
 * then scrolls it into view and highlights it. Steps never fabricate UI: if an
 * anchor is missing, the step still renders its instruction so the user is
 * never blocked.
 */

export interface TourStep {
  /** Matches `data-tour="<id>"` on a real element. */
  anchor?: string;
  /** Route to open before showing this step. */
  route?: string;
  title: string;
  body: string;
  /** Optional extra guidance shown in a muted line. */
  hint?: string;
}

export interface TourDefinition {
  id: string;
  name: string;
  description: string;
  steps: TourStep[];
}

const STORAGE_PREFIX = "red-thread.tour.";

interface TourContextValue {
  activeTour: TourDefinition | null;
  stepIndex: number;
  start: (tourId: string, caseId: string | null) => void;
  next: () => void;
  back: () => void;
  skip: () => void;
  exit: () => void;
  isAvailable: (tourId: string) => boolean;
}

const TourContext = createContext<TourContextValue | null>(null);

export function TourProvider({
  tours,
  children,
}: {
  tours: TourDefinition[];
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const [tourId, setTourId] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [caseId, setCaseId] = useState<string | null>(null);

  const activeTour = useMemo(
    () => tours.find((tour) => tour.id === tourId) ?? null,
    [tourId, tours],
  );

  const start = useCallback(
    (nextTourId: string, nextCaseId: string | null) => {
      const tour = tours.find((item) => item.id === nextTourId);
      if (!tour) return;
      setTourId(nextTourId);
      setStepIndex(0);
      setCaseId(nextCaseId);
    },
    [tours],
  );

  const finish = useCallback(() => {
    if (tourId) {
      try {
        window.localStorage.setItem(`${STORAGE_PREFIX}${tourId}`, "done");
      } catch {
        // Storage can be unavailable; the tour is simply offered again.
      }
    }
    setTourId(null);
    setStepIndex(0);
  }, [tourId]);

  const next = useCallback(() => {
    if (!activeTour) return;
    if (stepIndex + 1 >= activeTour.steps.length) {
      finish();
      return;
    }
    setStepIndex((current) => current + 1);
  }, [activeTour, stepIndex, finish]);

  const back = useCallback(() => {
    setStepIndex((current) => Math.max(0, current - 1));
  }, []);

  const isAvailable = useCallback((id: string) => {
    try {
      return window.localStorage.getItem(`${STORAGE_PREFIX}${id}`) !== "done";
    } catch {
      return true;
    }
  }, []);

  // Navigate whenever the active step asks for a different route.
  // An empty route means the case overview, so test for `undefined` rather
  // than falsiness — otherwise returning to the case root never happens.
  useEffect(() => {
    const step = activeTour?.steps[stepIndex];
    if (!step || step.route === undefined || !caseId) return;
    const target = `/cases/${caseId}${step.route}`;
    if (window.location.pathname !== target) {
      navigate(target);
    }
  }, [activeTour, stepIndex, caseId, navigate]);

  const value = useMemo(
    () => ({
      activeTour,
      stepIndex,
      start,
      next,
      back,
      skip: finish,
      exit: finish,
      isAvailable,
    }),
    [activeTour, stepIndex, start, next, back, finish, isAvailable],
  );

  return (
    <TourContext.Provider value={value}>
      {children}
      {activeTour ? (
        <TourOverlay
          tour={activeTour}
          stepIndex={stepIndex}
          onNext={next}
          onBack={back}
          onExit={finish}
        />
      ) : null}
    </TourContext.Provider>
  );
}

export function useTour(): TourContextValue {
  const context = useContext(TourContext);
  if (!context) {
    throw new Error("useTour must be used inside a TourProvider");
  }
  return context;
}

/** Element highlighted by the current step, resolved by its data-tour id. */
function useAnchoredElement(anchor: string | undefined) {
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!anchor) {
      setRect(null);
      return;
    }
    let frame = 0;
    let attempts = 0;

    const locate = () => {
      const element = document.querySelector<HTMLElement>(`[data-tour="${anchor}"]`);
      if (element) {
        element.scrollIntoView({ block: "center", behavior: "smooth" });
        setRect(element.getBoundingClientRect());
        element.classList.add("tour-spotlight");
        return () => element.classList.remove("tour-spotlight");
      }
      attempts += 1;
      if (attempts < 40) {
        frame = window.requestAnimationFrame(locate);
      }
      return undefined;
    };

    let cleanup: (() => void) | undefined;
    const timer = window.setTimeout(() => {
      cleanup = locate();
    }, 120);

    const onResize = () => {
      const element = document.querySelector<HTMLElement>(`[data-tour="${anchor}"]`);
      if (element) setRect(element.getBoundingClientRect());
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onResize, true);

    return () => {
      window.clearTimeout(timer);
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onResize, true);
      cleanup?.();
    };
  }, [anchor]);

  return rect;
}

function TourOverlay({
  tour,
  stepIndex,
  onNext,
  onBack,
  onExit,
}: {
  tour: TourDefinition;
  stepIndex: number;
  onNext: () => void;
  onBack: () => void;
  onExit: () => void;
}) {
  const step = tour.steps[stepIndex];
  const rect = useAnchoredElement(step?.anchor);
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardHeight, setCardHeight] = useState(220);
  const total = tour.steps.length;
  const last = stepIndex === total - 1;

  useEffect(() => {
    if (cardRef.current) setCardHeight(cardRef.current.offsetHeight);
  }, [step, rect]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onExit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onExit]);

  // Place the card in the largest free area so it never covers the target.
  const position = useMemo(() => {
    if (!rect) {
      return { left: "50%", top: "50%", transform: "translate(-50%, -50%)" } as const;
    }
    const gap = 16;
    const viewportH = window.innerHeight;
    const viewportW = window.innerWidth;
    const cardWidth = Math.min(360, viewportW - 32);

    const clampLeft = (value: number) =>
      Math.max(16, Math.min(value, viewportW - cardWidth - 16));

    // Sidebar-style targets (tall, narrow, on the left) read best with the
    // card to their right. Everything else prefers below, then above.
    const isSideTarget = rect.left < 300 && rect.height < viewportH * 0.9;
    if (isSideTarget) {
      const left = clampLeft(rect.right + gap);
      const top = Math.max(16, Math.min(rect.top, viewportH - cardHeight - 16));
      return { left, top, transform: "none" } as const;
    }

    const spaceBelow = viewportH - rect.bottom;
    const spaceAbove = rect.top;
    const putBelow = spaceBelow >= cardHeight + gap || spaceBelow >= spaceAbove;
    const top = putBelow
      ? Math.min(rect.bottom + gap, viewportH - cardHeight - 16)
      : Math.max(16, rect.top - cardHeight - gap);
    const centred = clampLeft(rect.left + rect.width / 2 - cardWidth / 2);

    return { left: centred, top, transform: "none" } as const;
  }, [rect, cardHeight]);

  if (!step) return null;

  return (
    <>
      {/*
        Dim everything except the highlighted element. The overlay is exactly
        the target's rect and casts a huge shadow, so the target stays visible
        no matter which stacking context it lives in.
      */}
      <div
        className="fixed z-[55] rounded-xl"
        aria-hidden="true"
        onClick={onExit}
        style={
          rect
            ? {
                left: rect.left - 6,
                top: rect.top - 6,
                width: rect.width + 12,
                height: rect.height + 12,
                boxShadow: "0 0 0 9999px rgba(2, 6, 23, 0.62)",
              }
            : { inset: 0, background: "rgba(2, 6, 23, 0.62)" }
        }
      />
      <div
        ref={cardRef}
        role="dialog"
        aria-label={`${tour.name} step ${stepIndex + 1} of ${total}`}
        className="fixed z-[70] w-[min(360px,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-4 shadow-2xl"
        style={position}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              {tour.name} · {stepIndex + 1} / {total}
            </p>
            <p className="mt-1 text-sm font-semibold text-primary">{step.title}</p>
          </div>
          <button
            type="button"
            onClick={onExit}
            aria-label="Exit tour"
            className="rounded-md p-1 text-muted transition hover:text-primary"
          >
            ✕
          </button>
        </div>

        <p className="mt-2 text-xs leading-relaxed text-secondary">{step.body}</p>
        {step.hint ? (
          <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{step.hint}</p>
        ) : null}

        <div className="mt-3 flex items-center gap-1.5">
          {tour.steps.map((item, index) => (
            <span
              key={item.title}
              className={
                index === stepIndex
                  ? "h-1.5 w-5 rounded-full bg-accent-fill"
                  : index < stepIndex
                    ? "h-1.5 w-1.5 rounded-full bg-accent-fill/50"
                    : "h-1.5 w-1.5 rounded-full bg-line-strong"
              }
            />
          ))}
        </div>

        <div className="mt-3 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={onExit}
            className="text-[11px] font-medium text-muted transition hover:text-secondary"
          >
            Skip tour
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onBack}
              disabled={stepIndex === 0}
              className="rounded-lg border border-line bg-surface-2/80 px-3 py-1.5 text-xs font-medium text-secondary transition hover:text-primary disabled:opacity-40"
            >
              Back
            </button>
            <button
              type="button"
              onClick={onNext}
              className="rounded-lg bg-accent-fill px-3 py-1.5 text-xs font-medium text-white transition hover:bg-accent-fill-hover"
            >
              {last ? "Finish" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
