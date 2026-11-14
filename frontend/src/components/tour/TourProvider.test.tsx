import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { TourProvider, useTour, type TourDefinition } from "./TourProvider";
import { TOURS } from "./tours";

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="path">{location.pathname}</p>;
}

const tours: TourDefinition[] = [
  {
    id: "sample",
    name: "Sample tour",
    description: "Two real steps.",
    steps: [
      { route: "", title: "First step", body: "On the case root." },
      { route: "/timeline", title: "Second step", body: "On the timeline." },
    ],
  },
];

function Harness({ caseId = "case-1" }: { caseId?: string | null }) {
  const { start, activeTour } = useTour();
  return (
    <>
      <button type="button" onClick={() => start("sample", caseId)}>
        begin
      </button>
      <p data-testid="active">{activeTour?.id ?? "none"}</p>
    </>
  );
}

function renderTour() {
  render(
    <MemoryRouter initialEntries={["/cases/case-1"]}>
      <TourProvider tours={tours}>
        <Routes>
          <Route
            path="/cases/:caseId/*"
            element={
              <>
                <LocationProbe />
                <Harness />
              </>
            }
          />
        </Routes>
      </TourProvider>
    </MemoryRouter>,
  );
}

describe("TourProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("starts a tour and shows the first step", async () => {
    renderTour();
    fireEvent.click(screen.getByText("begin"));

    await waitFor(() =>
      expect(screen.getByRole("dialog")).toHaveTextContent("Sample tour"),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("First step");
  });

  it("navigates to the route a step requires", async () => {
    renderTour();
    fireEvent.click(screen.getByText("begin"));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    // Step one is the case root and must not navigate away.
    expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1/timeline"),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("Second step");
  });

  it("goes back without leaving the tour", async () => {
    renderTour();
    fireEvent.click(screen.getByText("begin"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(screen.getByTestId("path")).toHaveTextContent("/timeline"),
    );

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    await waitFor(() =>
      expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1"),
    );
  });

  it("closes on Skip and does not block navigation", async () => {
    renderTour();
    fireEvent.click(screen.getByText("begin"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Skip tour"));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // The route stays usable after exiting.
    expect(screen.getByTestId("path")).toBeInTheDocument();
  });

  it("finishes after the last step", async () => {
    renderTour();
    fireEvent.click(screen.getByText("begin"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Finish" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Finish" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(window.localStorage.getItem("red-thread.tour.sample")).toBe("done");
  });

  it("closes on Escape", async () => {
    renderTour();
    fireEvent.click(screen.getByText("begin"));
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("tour definitions", () => {
  it("points every step at a real route suffix", () => {
    for (const tour of TOURS) {
      for (const step of tour.steps) {
        if (step.route === undefined) continue;
        expect(step.route === "" || step.route.startsWith("/")).toBe(true);
      }
    }
  });

  it("gives every step an instruction and an anchor", () => {
    for (const tour of TOURS) {
      expect(tour.steps.length).toBeGreaterThan(2);
      for (const step of tour.steps) {
        expect(step.title.length).toBeGreaterThan(3);
        expect(step.body.length).toBeGreaterThan(20);
        expect(step.anchor).toBeTruthy();
      }
    }
  });

  it("only references anchors that exist in the source", async () => {
    // A tour step whose anchor does not exist would highlight nothing, so this
    // asserts the definitions against the actual `data-tour` attributes rather
    // than trusting them by eye.
    const modules = import.meta.glob(["/src/**/*.tsx", "!/src/**/*.test.tsx"], {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;

    const present = new Set<string>();
    for (const source of Object.values(modules)) {
      for (const match of source.matchAll(/data-tour="([a-z0-9-]+)"/g)) {
        present.add(match[1]);
      }
    }

    const missing = new Set<string>();
    for (const tour of TOURS) {
      for (const step of tour.steps) {
        if (step.anchor && !present.has(step.anchor)) missing.add(step.anchor);
      }
    }

    expect([...missing]).toEqual([]);
  });

  it("covers the investigation journey and focused tours", () => {
    const ids = TOURS.map((tour) => tour.id);
    expect(ids).toContain("investigation-journey");
    expect(ids).toContain("evidence-integrity");
    expect(ids).toContain("relationship-graph");
    expect(ids).toContain("timeline");
    expect(ids).toContain("ai-assistant");
  });
});
