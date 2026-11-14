import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PageGuide } from "./PageGuide";
import { TourProvider, useTour } from "@/components/tour/TourProvider";
import { GLOSSARY } from "@/lib/glossary";
import type { GuidanceResponse, GuidanceSummary } from "@/types";

function summary(overrides: Partial<GuidanceSummary> = {}): GuidanceSummary {
  return {
    evidence: 3,
    parsed: 3,
    needs_attention: 0,
    events: 12,
    entities: 5,
    open_findings: 0,
    unreviewed_relationships: 0,
    reports: 1,
    total_relationships: 10,
    documented_relationships: 8,
    inferred_leads: 2,
    unique_connections: 7,
    raw_edges: 1,
    structural_edges: 4,
    ...overrides,
  };
}

function guidance(overrides: Partial<GuidanceSummary> = {}): GuidanceResponse {
  return {
    case_id: "case-1",
    generated_at: "2026-01-01T00:00:00Z",
    stages: [],
    next_action: {
      id: "review_relationships",
      title: "Review relationships",
      reason: "Relationships have not been reviewed.",
      action_label: "Review relationships",
      href: "/cases/case-1/graph",
      tone: "info",
    },
    attention: [],
    summary: summary(overrides),
    scanned_events: 12,
  };
}

describe("PageGuide", () => {
  it("explains the page and the next step from case state", () => {
    render(
      <MemoryRouter>
        <PageGuide page="graph" caseId="case-1" guidance={guidance()} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/What this is:/)).toBeInTheDocument();
    expect(screen.getByText(/When to use it:/)).toBeInTheDocument();
    expect(screen.getByText(/Next:/)).toBeInTheDocument();
  });

  it("does not recommend the graph when no entities exist", () => {
    render(
      <MemoryRouter>
        <PageGuide page="graph" caseId="case-1" guidance={guidance({ entities: 0 })} />
      </MemoryRouter>,
    );

    // It points at events instead of suggesting the graph itself.
    expect(screen.getByText(/No entity connections have been found yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review events/i })).toHaveAttribute(
      "href",
      "/cases/case-1/events",
    );
  });

  it("sends the investigator to intake when the case is empty", () => {
    render(
      <MemoryRouter>
        <PageGuide page="timeline" caseId="case-1" guidance={guidance({ evidence: 0 })} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/no evidence yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /upload evidence/i })).toHaveAttribute(
      "href",
      "/cases/case-1/evidence/intake",
    );
  });

  it("warns that unreviewed findings will appear unresolved in a report", () => {
    render(
      <MemoryRouter>
        <PageGuide page="reports" caseId="case-1" guidance={guidance({ open_findings: 3 })} />
      </MemoryRouter>,
    );

    expect(screen.getByText(/3 findings still need a review decision/i)).toBeInTheDocument();
  });
});

describe("GLOSSARY", () => {
  it("explains every term in one sentence", () => {
    for (const [term, text] of Object.entries(GLOSSARY)) {
      expect(text.length, term).toBeGreaterThan(20);
      // A single sentence ends with one full stop.
      expect(text.match(/\./g)?.length, term).toBe(1);
    }
  });
});

/** Minimal harness that starts a tour on mount. */
function TourHarness({ anchor }: { anchor: string }) {
  const { start, activeTour } = useTour();
  return (
    <div>
      <button type="button" onClick={() => start("probe", "case-1")}>
        begin
      </button>
      <div data-tour={anchor} style={{ width: 200, height: 40 }} />
      {activeTour ? <span>running</span> : <span>idle</span>}
    </div>
  );
}

const PROBE = [
  {
    id: "probe",
    name: "Probe tour",
    description: "Engine behaviour.",
    steps: [
      { route: "/graph", anchor: "late", title: "Late element", body: "Appears after render, so the engine must wait for it rather than guess." },
    ],
  },
];

describe("TourProvider synchronisation", () => {
  it("waits for an anchor that renders after the step begins", async () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/graph"]}>
        <TourProvider tours={PROBE}>
          <TourHarness anchor="late" />
        </TourProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "begin" }));

    // The card appears once the element is measurable, not before.
    await waitFor(() =>
      expect(screen.getByRole("dialog", { name: /step 1 of 1/i })).toBeInTheDocument(),
    );
    expect(document.querySelector('[data-tour="late"]')?.classList.contains("tour-spotlight")).toBe(
      true,
    );
  });
});
