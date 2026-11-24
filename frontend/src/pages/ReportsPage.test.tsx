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
          total_relationships: 4,
          documented_relationships: 4,
          inferred_leads: 0,
          unique_connections: 3,
          raw_edges: 1,
          structural_edges: 2,
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

  it("downloads through an authenticated fetch, not a bare cross-site link", async () => {
    // Regression: the download control used to be `<a href target="_blank">`.
    // A cross-site navigation does not reliably carry the session cookie, so
    // the API answered "Authentication required" and no file arrived.
    const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({
        "content-disposition": 'attachment; filename="case-1.pdf"',
      }),
      blob: async () => blob,
    });
    const createObjectURL = vi.fn(() => "blob:report");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });

    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const element = originalCreateElement(tag);
      if (tag === "a") element.click = click;
      return element;
    });

    render(
      <MemoryRouter initialEntries={["/cases/case-1/reports"]}>
        <Routes>
          <Route path="/cases/:caseId/reports" element={<ReportsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    await vi.waitFor(() => expect(click).toHaveBeenCalled());

    // The request carried credentials and the case header, and targeted the API.
    const [, options] = fetchMock.mock.calls[0];
    expect(options.credentials).toBe("include");
    expect(options.headers["X-Case-ID"]).toBe("case-1");
    expect(fetchMock.mock.calls[0][0]).toContain("/reports/report-1/download");
    expect(createObjectURL).toHaveBeenCalledWith(blob);

    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });
});
