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
  /** Route to open before showing this step, relative to the case. */
  route?: string;
  /**
   * Set when `route` is an application route rather than a case route, e.g.
   * `/cases` for the case list. Case routes are prefixed with `/cases/<id>`.
   */
  appRoute?: boolean;
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
    if (!step || step.route === undefined) return;
    const target = step.appRoute
      ? step.route
      : caseId
        ? `/cases/${caseId}${step.route}`
        : null;
    if (target && window.location.pathname !== target) {
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

/**
 * Resolve the element highlighted by the current step.
 *
 * The target often does not exist yet: a route change has to render, and the
 * page may still be loading its data. Rather than sleeping for an arbitrary
 * amount of time, this observes the document and re-checks whenever the DOM
 * changes, so the highlight appears exactly when the element does. Resolution
 * also waits for the element to be laid out and visible, which prevents the
 * card from positioning itself against a zero-height placeholder.
 */
function useAnchoredElement(anchor: string | undefined) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    setRect(null);
    setResolved(false);
    if (!anchor) {
      setResolved(true);
      return;
    }

    let frame = 0;
    let highlight: HTMLElement | null = null;
    let disposed = false;
    let layoutTicks = 0;

    // The rect is used for positioning, so it is re-measured whenever layout
    // changes. Resolution is a separate question: an element that is present but
    // still has no box (mid-render, or in a non-layout environment) is accepted
    // after two animation frames rather than blocking the step.
    const measure = (element: HTMLElement) => {
      const bounds = element.getBoundingClientRect();
      const hasBox = bounds.width > 0 || bounds.height > 0;
      if (hasBox) {
        setRect(bounds);
        setResolved(true);
        return true;
      }
      return false;
    };

    const clearHighlight = () => {
      highlight?.classList.remove("tour-spotlight");
      highlight = null;
    };

    const acceptWithoutBox = (element: HTMLElement) => {
      layoutTicks += 1;
      if (layoutTicks < 2) {
        frame = window.requestAnimationFrame(() => {
          if (!disposed) acceptWithoutBox(element);
        });
        return;
      }
      setRect(element.getBoundingClientRect());
      setResolved(true);
    };

    const tryResolve = () => {
      if (disposed) return;
      const element = document.querySelector<HTMLElement>(`[data-tour="${anchor}"]`);
      if (!element) return;

      if (highlight !== element) {
        clearHighlight();
        highlight = element;
        highlight.classList.add("tour-spotlight");
        // Centre only once, so re-renders do not fight the user's scrolling.
        // Guarded because non-browser environments do not implement it.
        if (typeof element.scrollIntoView === "function") {
          element.scrollIntoView({ block: "center", behavior: "smooth" });
        }
      }

      if (!measure(element)) {
        acceptWithoutBox(element);
        return;
      }

      // Measure again after scrolling settles so the card is not placed against
      // a stale position.
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        if (!disposed && highlight === element) measure(element);
      });
    };

    tryResolve();

    // Bounded resolution. A step must never be unreadable because its target is
    // missing (an empty case, a page still loading, a permission the account
    // lacks). After this window the instruction is shown even without a target.
    const fallback = window.setTimeout(() => {
      if (!disposed) setResolved(true);
    }, 2500);

    // React to the element appearing (route render, data load) or moving.
    const observer = new MutationObserver(tryResolve);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-tour", "class", "style"],
    });

    const onLayoutChange = () => {
      if (highlight && !disposed) {
        if (!measure(highlight)) setResolved(true);
      } else {
        tryResolve();
      }
    };
    window.addEventListener("resize", onLayoutChange);
    window.addEventListener("scroll", onLayoutChange, true);

    return () => {
      disposed = true;
      window.clearTimeout(fallback);
      observer.disconnect();
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", onLayoutChange);
      window.removeEventListener("scroll", onLayoutChange, true);
      clearHighlight();
    };
  }, [anchor]);

  return { rect, resolved };
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
  const { rect, resolved } = useAnchoredElement(step?.anchor);
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

  // Place the card wherever it fits without covering the target. Each candidate
  // is scored by how much room it actually has, and the best one wins. When the
  // target fills the viewport and nothing fits, the card is clamped to the edge
  // with the most space instead of being dropped on top of the target.
  const position = useMemo(() => {
    if (!rect) {
      return { left: "50%", top: "50%", transform: "translate(-50%, -50%)" } as const;
    }
    const gap = 16;
    const margin = 16;
    const viewportH = window.innerHeight;
    const viewportW = window.innerWidth;
    const cardWidth = Math.min(360, viewportW - 32);
    const height = Math.min(cardHeight, viewportH - margin * 2);

    const clampLeft = (value: number) =>
      Math.max(margin, Math.min(value, viewportW - cardWidth - margin));
    const clampTop = (value: number) =>
      Math.max(margin, Math.min(value, viewportH - height - margin));

    const space = {
      below: viewportH - rect.bottom - gap,
      above: rect.top - gap,
      right: viewportW - rect.right - gap,
      left: rect.left - gap,
    };
    const fits = {
      below: space.below >= height,
      above: space.above >= height,
      right: space.right >= cardWidth,
      left: space.left >= cardWidth,
    };

    // Horizontal placement puts the card beside the target; it needs enough
    // vertical room to sit next to it without being pushed off-screen.
    const besideTop = clampTop(rect.top + rect.height / 2 - height / 2);

    if (fits.below && space.below >= space.above) {
      return { left: clampLeft(rect.left + rect.width / 2 - cardWidth / 2), top: rect.bottom + gap, transform: "none" } as const;
    }
    if (fits.above) {
      return { left: clampLeft(rect.left + rect.width / 2 - cardWidth / 2), top: rect.top - height - gap, transform: "none" } as const;
    }
    if (fits.right && space.right >= space.left) {
      return { left: rect.right + gap, top: besideTop, transform: "none" } as const;
    }
    if (fits.left) {
      return { left: Math.max(margin, rect.left - cardWidth - gap), top: besideTop, transform: "none" } as const;
    }

    // Nothing fits cleanly: use the roomiest edge and accept a small overlap.
    const roomiest = (
      Object.entries(space) as [keyof typeof space, number][]
    ).sort((left, right) => right[1] - left[1])[0][0];
    if (roomiest === "below") {
      return { left: margin, top: clampTop(rect.bottom + gap), transform: "none" } as const;
    }
    if (roomiest === "above") {
      return { left: margin, top: clampTop(rect.top - height - gap), transform: "none" } as const;
    }
    if (roomiest === "right") {
      return { left: clampLeft(rect.right + gap), top: margin, transform: "none" } as const;
    }
    return { left: margin, top: margin, transform: "none" } as const;
  }, [rect, cardHeight]);

  if (!step) return null;

  return (
    <>
      {/*
        Dim everything except the highlighted element. The overlay is exactly
        the target's rect and casts a huge shadow, so the target stays visible
        no matter which stacking context it lives in. While the target is still
        resolving, a plain scrim is shown with no card, so the card never
        appears at a guessed position first.
      */}
      <div
        className="pointer-events-none fixed z-[55] rounded-xl transition-[left,top,width,height] duration-200"
        aria-hidden="true"
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
      {/*
        The card stays mounted across steps so the Next/Back controls are always
        clickable. While a target is still resolving it is hidden rather than
        removed, which avoids the flicker and the dead-click window that came
        from unmounting it mid-transition.
      */}
      <div
        ref={cardRef}
        role="dialog"
        aria-label={`${tour.name} step ${stepIndex + 1} of ${total}`}
        aria-hidden={!resolved}
        data-tour-card=""
        className={
          resolved
            ? "fixed z-[70] w-[min(360px,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-4 shadow-2xl"
            : "pointer-events-none fixed z-[70] w-[min(360px,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-4 opacity-0 shadow-2xl"
        }
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
