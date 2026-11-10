import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { WALKTHROUGH_STEPS, WalkthroughOverlay } from "./Walkthrough";

function LocationProbe() {
  const location = useLocation();
  return <p data-testid="path">{location.pathname}</p>;
}

function renderAt(step: number, caseId: string | null, onStepChange = vi.fn()) {
  render(
    <MemoryRouter initialEntries={["/cases/case-1"]}>
      <Routes>
        <Route
          path="/cases/:caseId/*"
          element={
            <>
              <LocationProbe />
              <WalkthroughOverlay
                open
                onClose={vi.fn()}
                step={step}
                onStepChange={onStepChange}
                caseId={caseId}
              />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
  return { onStepChange };
}

describe("WalkthroughOverlay", () => {
  it("gives every step a route under the active case", () => {
    for (const step of WALKTHROUGH_STEPS) {
      expect(step.route === "" || step.route.startsWith("/")).toBe(true);
    }
    const routes = WALKTHROUGH_STEPS.map((step) => step.route);
    expect(routes).toContain("/timeline");
    expect(routes).toContain("/graph");
    expect(routes).toContain("/findings");
    expect(routes).toContain("/reports");
  });

  it("navigates to the page the next step describes", () => {
    // Step 1 = upload evidence, step 2 = evidence vault.
    const { onStepChange } = renderAt(1, "case-1");

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(onStepChange).toHaveBeenCalledWith(2);
    expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1/evidence");
  });

  it("navigates backwards with the Back button", () => {
    const { onStepChange } = renderAt(4, "case-1");

    fireEvent.click(screen.getByRole("button", { name: "Back" }));

    expect(onStepChange).toHaveBeenCalledWith(3);
    expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1/events");
  });

  it("jumps to a step and its page when a progress dot is clicked", () => {
    const { onStepChange } = renderAt(0, "case-1");

    fireEvent.click(screen.getByRole("button", { name: /Go to step 6/ }));

    expect(onStepChange).toHaveBeenCalledWith(5);
    expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1/graph");
  });

  it("does not navigate when no case is selected", () => {
    const { onStepChange } = renderAt(1, null);

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(onStepChange).toHaveBeenCalledWith(2);
    // Navigation requires a case, so the route is unchanged.
    expect(screen.getByTestId("path")).toHaveTextContent("/cases/case-1");
  });

  it("shows which page each step opens", () => {
    renderAt(3, "case-1");
    expect(screen.getByText("Opens: /events")).toBeInTheDocument();
  });
});
