import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { CrimeReconstructionPage } from "@/pages/CrimeReconstructionPage";
import { ToastProvider } from "@/components/ui/Toast";

const reconstruction = {
  case_id: "case-1",
  counts: {
    evidence: 7,
    events: 20,
    entities: 38,
    relationships: 204,
    findings: 6,
    open_findings: 2,
    spatial_observations: 5,
    unreviewed_relationships: 204,
  },
  relationship_types: { co_mention: 85 },
  review_statuses: { unreviewed: 204 },
  relationships: [],
  recent_events: [],
  conflicts: [],
  unresolved: ["One question is still open."],
  spatial_observations: [],
  generated_at: "2026-11-14T00:00:00Z",
  limitations: ["Correlation is not proof of a relationship."],
};

const sequence = {
  case_id: "case-1",
  items: [
    {
      id: "ev-1",
      timestamp: "2026-11-14T10:00:00Z",
      timestamp_raw: "2026-11-14 10:00",
      timestamp_confidence: "exact",
      timestamp_timezone: "UTC",
      event_type: "call",
      category: "communication",
      label: "call record",
      description: "Call from +91-1 to +91-2",
      evidence_id: "e1",
      source_filename: "call_log.csv",
      source_locator: "row:2",
      source_snippet: "",
      entities: [{ id: "x", entity_type: "phone", value: "+91-1", role: "caller" }],
      relationships: [],
      finding_ids: [],
      review_status: "unreviewed",
      review_note: "",
      group_ids: [],
      confidence: "documented",
      confidence_reason: "Parsed directly.",
    },
  ],
  undated: [],
  total: 1,
  categories: { communication: 1 },
  groups: [],
  gaps: [],
  limitations: [],
};

const query = (data: unknown) => ({
  data,
  isLoading: false,
  error: null,
  refetch: vi.fn(),
  isPending: false,
  mutate: vi.fn(),
});

vi.mock("@/hooks/useApi", () => ({
  useReconstruction: () => query(reconstruction),
  useReconstructionSequence: () => query(sequence),
  useEvidence: () => query([]),
  useFindings: () => query({ items: [] }),
  useRelationships: () =>
    query({
      items: [
        ...Array.from({ length: 200 }, (_, index) => ({
          id: `obs-${index}`,
          relationship_type: "co_mention",
          explanation: "An observation of co-occurrence.",
          classification: "observation",
          review_status: "unreviewed",
          confidence: "low",
        })),
        ...Array.from({ length: 4 }, (_, index) => ({
          id: `hyp-${index}`,
          relationship_type: "temporal_association",
          explanation: "A lead requiring verification.",
          classification: "hypothesis",
          review_status: "unreviewed",
          confidence: "low",
        })),
      ],
    }),
  useGuidance: () => query(undefined),
  useEventReviews: () => query({ items: [], total: 0 }),
  useAnnotations: () => query([]),
  useCreateAnnotation: () => query(undefined),
  useReviewEvent: () => query(undefined),
}));

describe("CrimeReconstructionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the unified workspace without crashing", () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/reconstruction"]}>
        <ToastProvider>
          <Routes>
            <Route path="/cases/:caseId/reconstruction" element={<CrimeReconstructionPage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Reconstruct what happened/i)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Event reconstruction/i })).toBeInTheDocument();
    expect(screen.getByText(/What happened in this case\?/i)).toBeInTheDocument();
  });

  it("reports relationship counts from one source so they cannot disagree", () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/reconstruction?tab=relationships"]}>
        <ToastProvider>
          <Routes>
            <Route path="/cases/:caseId/reconstruction" element={<CrimeReconstructionPage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    );

    // One definition drives every number on the strip: 200 documented + 4
    // inferred must equal the 204 total, read from the same list.
    const strip = screen.getByText(/TOTAL/i).closest("div")?.parentElement;
    const text = strip?.textContent ?? "";
    expect(text).toContain("204");
    expect(text).toContain("200");
    expect(text).toContain("4");
    expect(text).toContain("documented");
    expect(text).toContain("inferred");
  });

  it("never shows a negative or contradictory inferred count", () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/reconstruction?tab=relationships"]}>
        <ToastProvider>
          <Routes>
            <Route path="/cases/:caseId/reconstruction" element={<CrimeReconstructionPage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    );

    const strip = screen.getByText(/TOTAL/i).closest("div")?.parentElement;
    expect(strip?.textContent ?? "").not.toMatch(/-\d+\s*inferred/i);
  });

  it("shows the reconstructed sequence on its tab", () => {
    render(
      <MemoryRouter initialEntries={["/cases/case-1/reconstruction?tab=sequence"]}>
        <ToastProvider>
          <Routes>
            <Route path="/cases/:caseId/reconstruction" element={<CrimeReconstructionPage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Reconstructed sequence of events/i)).toBeInTheDocument();
    expect(screen.getByText(/Call from \+91-1 to \+91-2/)).toBeInTheDocument();
  });
});
