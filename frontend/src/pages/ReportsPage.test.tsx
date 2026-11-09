import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useReports: vi.fn(),
  useGenerateReport: vi.fn(),
  useCase: vi.fn(),
  useGuidance: vi.fn(),
  useToast: vi.fn(),
}));

vi.mock("@/hooks/useApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/useApi")>();
  return {
    ...actual,
    useReports: mocks.useReports,
    useGenerateReport: mocks.useGenerateReport,
    useCase: mocks.useCase,
    useGuidance: mocks.useGuidance,
  };
});
vi.mock("@/components/ui/Toast", () => ({ useToast: mocks.useToast }));

import { ReportsPage } from "./ReportsPage";

describe("ReportsPage", () => {
  const mutate = vi.fn();

  beforeEach(() => {
    mutate.mockReset();
    mocks.useToast.mockReturnValue({ push: vi.fn() });
    mocks.useGenerateReport.mockReturnValue({ mutate, isPending: false });
    mocks.useCase.mockReturnValue({
      data: { title: "Operation Test", status: "open" },
      isLoading: false,
      error: null,
    });
    mocks.useGuidance.mockReturnValue({
      data: {
        summary: {
          evidence: 3,
          parsed: 3,
          needs_attention: 0,
          events: 12,
          entities: 5,
          open_findings: 2,
          unreviewed_relationships: 1,
          reports: 1,
        },
      },
      isLoading: false,
      error: null,
    });
    mocks.useReports.mockReturnValue({
      data: [
        {
          id: "report-1",
          case_id: "case-1",
          report_type: "pdf",
          filename: "case-1.pdf",
          status: "ready",
          generated_at: "2026-11-03T17:00:00Z",
          metadata_json: {},
        },
      ],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("starts PDF generation and shows stored report downloads", () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/reports"]}>
        <Routes>
          <Route path="/cases/:caseId/reports" element={<ReportsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Generate PDF" }));
    expect(mutate).toHaveBeenCalledWith("pdf", expect.any(Object));
    expect(screen.getByText("Pdf report")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });
});
