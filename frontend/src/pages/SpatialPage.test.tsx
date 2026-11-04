import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useSpatial: vi.fn(),
  useEvidence: vi.fn(),
}));

vi.mock("@/hooks/useApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/useApi")>();
  return { ...actual, useSpatial: mocks.useSpatial, useEvidence: mocks.useEvidence };
});
vi.mock("@/components/spatial/SpatialMap", () => ({
  SpatialMap: ({ observations }: { observations: unknown[] }) => (
    <div data-testid="spatial-map">{observations.length} map points</div>
  ),
}));

import { SpatialPage } from "./SpatialPage";

const observations = [
  {
    event_id: "evt-1",
    evidence_id: "evidence-1",
    event_type: "location.fix",
    timestamp_normalized: "2026-11-03T17:00:00Z",
    latitude: 12.9716,
    longitude: 77.5946,
    label: "Central Junction",
    entity_values: ["DEV-DT-01"],
    source_filename: "gps_records.csv",
    source_locator: "row 2",
  },
  {
    event_id: "evt-2",
    evidence_id: "evidence-2",
    event_type: "cctv.segment",
    timestamp_normalized: "2026-11-03T17:05:00Z",
    latitude: 12.972,
    longitude: 77.595,
    label: "CCTV Camera",
    entity_values: ["CAM-DT-01"],
    source_filename: "cctv_metadata.csv",
    source_locator: "row 2",
  },
];

describe("SpatialPage", () => {
  beforeEach(() => {
    mocks.useEvidence.mockReturnValue({ data: [], isLoading: false, error: null });
    mocks.useSpatial.mockReturnValue({
      data: { observations, relationships: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("renders documented points and opens an observation detail", () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/spatial"]}>
        <Routes>
          <Route path="/cases/:caseId/spatial" element={<SpatialPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Spatial reconstruction")).toBeInTheDocument();
    expect(screen.getByTestId("spatial-map")).toHaveTextContent("2 map points");
    fireEvent.click(screen.getByRole("button", { name: /Central Junction/ }));
    expect(screen.getByText("Observation detail")).toBeInTheDocument();
    expect(screen.getByText("12.97160, 77.59460")).toBeInTheDocument();
  });
});
