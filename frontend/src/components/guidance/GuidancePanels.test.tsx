import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { NextActionPanel, AttentionList } from "./GuidancePanels";
import type { GuidanceResponse } from "@/types";

function guidance(overrides: Partial<GuidanceResponse> = {}): GuidanceResponse {
  return {
    case_id: "case-1",
    generated_at: "2026-11-08T10:00:00Z",
    stages: [
      {
        key: "create_case",
        index: 1,
        title: "Create case",
        description: "A case groups all evidence.",
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
        description: "Files are hashed.",
        what_to_do: "Upload the files.",
        output: "Stored files.",
        status: "in_progress",
        href: "/cases/case-1/evidence/intake",
        completed_count: 0,
        total_count: 1,
        next_step: "Then review events.",
      },
    ],
    next_action: {
      id: "review_findings",
      title: "3 high-severity findings await review",
      reason: "Each finding needs a human decision.",
      action_label: "Review findings",
      href: "/cases/case-1/findings",
      tone: "critical",
    },
    attention: [],
    summary: {
      evidence: 2,
      parsed: 2,
      needs_attention: 0,
      events: 10,
      entities: 4,
      open_findings: 3,
      unreviewed_relationships: 1,
      reports: 0,
      total_relationships: 6,
      documented_relationships: 5,
      inferred_leads: 1,
      unique_connections: 4,
      raw_edges: 2,
      structural_edges: 3,
    },
    scanned_events: 10,
    ...overrides,
  };
}

describe("NextActionPanel", () => {
  it("renders the server recommendation and its action link", () => {
    render(
      <MemoryRouter>
        <NextActionPanel guidance={guidance()} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Next recommended action")).toBeInTheDocument();
    expect(
      screen.getByText("3 high-severity findings await review"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Each finding needs a human decision."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Review findings/ })).toHaveAttribute(
      "href",
      "/cases/case-1/findings",
    );
  });

  it("shows a dismiss control when a handler is supplied", () => {
    const onDismiss = vi.fn();
    render(
      <MemoryRouter>
        <NextActionPanel guidance={guidance()} onDismiss={onDismiss} />
      </MemoryRouter>,
    );
    screen.getByLabelText("Dismiss recommendation for this session").click();
    expect(onDismiss).toHaveBeenCalled();
  });
});

describe("AttentionList", () => {
  it("confirms when nothing needs attention", () => {
    render(<AttentionList items={[]} />);
    expect(screen.getByText("Nothing needs attention right now.")).toBeInTheDocument();
  });

  it("lists attention items with counts and invokes the handler", () => {
    const onSelect = vi.fn();
    render(
      <AttentionList
        onSelect={onSelect}
        items={[
          {
            kind: "parse_warnings",
            title: "Parsed with warnings",
            detail: "1 file parsed with warnings.",
            href: "/cases/case-1/evidence",
            count: 1,
          },
        ]}
      />,
    );

    screen.getByText(/Parsed with warnings/).closest("button")!.click();
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "parse_warnings" }),
    );
  });
});
