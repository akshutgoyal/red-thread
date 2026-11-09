import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { InvestigationStepper } from "@/components/ui/Stepper";
import { CaseNarrative } from "@/components/narrative/CaseNarrative";
import type { GuidanceStage, NarrativeResponse } from "@/types";

const stages: GuidanceStage[] = [
  {
    key: "create_case",
    index: 1,
    title: "Create case",
    description: "A case groups evidence.",
    what_to_do: "Name the investigation.",
    output: "An empty case.",
    status: "complete",
    href: "/cases/case-1",
    completed_count: 1,
    total_count: 1,
    next_step: "Next stage: Upload evidence.",
  },
  {
    key: "upload_evidence",
    index: 2,
    title: "Upload evidence",
    description: "Files are hashed and stored unchanged.",
    what_to_do: "Upload the files you were given.",
    output: "Stored files with a SHA-256 digest.",
    status: "in_progress",
    href: "/cases/case-1/evidence/intake",
    completed_count: 0,
    total_count: 1,
    next_step: "Then review extracted events.",
  },
  {
    key: "generate_report",
    index: 9,
    title: "Generate the investigation report",
    description: "Collects everything into one document.",
    what_to_do: "Generate the report.",
    output: "A draft PDF.",
    status: "not_started",
    href: "/cases/case-1/reports",
    completed_count: 0,
    total_count: 1,
    next_step: "",
  },
];

describe("InvestigationStepper", () => {
  it("shows each stage's status, task, output and next step", () => {
    render(
      <MemoryRouter>
        <InvestigationStepper stages={stages} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Create case")).toBeInTheDocument();
    expect(screen.getByText("Upload evidence")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("Not started")).toBeInTheDocument();
    expect(screen.getByText("Upload the files you were given.")).toBeInTheDocument();
    expect(
      screen.getByText("Stored files with a SHA-256 digest."),
    ).toBeInTheDocument();
    expect(screen.getByText("Then review extracted events.")).toBeInTheDocument();

    const uploadLink = screen.getByText("Upload evidence").closest("a");
    expect(uploadLink).toHaveAttribute("href", "/cases/case-1/evidence/intake");
  });

  it("reports overall progress against the number of stages", () => {
    render(
      <MemoryRouter>
        <InvestigationStepper stages={stages} />
      </MemoryRouter>,
    );
    const bars = screen.getAllByRole("progressbar");
    expect(bars[0]).toHaveAttribute("aria-valuenow", "33");
    expect(bars[0]).toHaveAttribute("aria-valuemax", "100");
  });
});

describe("CaseNarrative", () => {
  const narrative: NarrativeResponse = {
    case_id: "case-1",
    generated_at: "2026-11-08T10:00:00Z",
    items: [
      {
        index: 1,
        statement: "A call record was recorded involving +91-90000-11111.",
        kind: "observation",
        timestamp: "2026-10-14T07:55:00Z",
        event_ids: ["event-1"],
        evidence_ids: ["evidence-1"],
        finding_ids: [],
        relationship_ids: [],
        href: "/cases/case-1/timeline?event=event-1",
      },
      {
        index: 2,
        statement: "A high-severity finding still needs review.",
        kind: "finding",
        timestamp: null,
        event_ids: [],
        evidence_ids: [],
        finding_ids: ["finding-1"],
        relationship_ids: [],
        href: "/cases/case-1/findings?finding=finding-1",
      },
    ],
    disclaimer: "These statements are extracted observations, not a proven sequence.",
  };

  it("links every statement back to its underlying record", () => {
    render(
      <MemoryRouter>
        <CaseNarrative caseId="case-1" narrative={narrative} />
      </MemoryRouter>,
    );

    const callLink = screen
      .getByText(/A call record was recorded/)
      .closest("a");
    expect(callLink).toHaveAttribute("href", "/cases/case-1/timeline?event=event-1");

    const findingLink = screen
      .getByText(/A high-severity finding still needs review/)
      .closest("a");
    expect(findingLink).toHaveAttribute("href", "/cases/case-1/findings?finding=finding-1");
    expect(screen.getByText(narrative.disclaimer)).toBeInTheDocument();
  });

  it("explains the empty state instead of showing nothing", () => {
    render(
      <MemoryRouter>
        <CaseNarrative
          caseId="case-1"
          narrative={{ ...narrative, items: [] }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("Nothing to summarise yet")).toBeInTheDocument();
  });
});
