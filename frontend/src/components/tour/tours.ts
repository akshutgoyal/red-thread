import type { TourDefinition } from "./TourProvider";

/**
 * Guided tours.
 *
 * Every `route` is a real route in the app and every `anchor` matches a
 * `data-tour` attribute on a real element. No step describes UI that does not
 * exist, and no step performs an action on the investigator's behalf.
 */
export const TOURS: TourDefinition[] = [
  {
    id: "first-investigation",
    name: "Create your first investigation",
    description: "Set up a case and learn what the workspace contains.",
    steps: [
      {
        route: "",
        anchor: "case-selector",
        title: "Pick the investigation",
        body: "Everything you do happens inside a case. This selector switches between the investigations you can access.",
        hint: "The demo case is synthetic data you can explore freely.",
      },
      {
        route: "",
        anchor: "next-action",
        title: "Follow the next action",
        body: "Red Thread computes what to do next from the case's stored records. It never guesses — this panel is derived from evidence, review state and reports.",
        hint: "You can dismiss it for the session, and it returns when the state changes.",
      },
      {
        route: "",
        anchor: "workflow-progress",
        title: "Know where you are",
        body: "The investigation runs in nine stages, from evidence intake to the report. Complete, in progress and not started are read from real data.",
      },
      {
        route: "/evidence/intake",
        anchor: "evidence-dropzone",
        title: "Add evidence",
        body: "Upload the files you were given. Each one is hashed with SHA-256 before parsing, so you can prove later that the stored bytes never changed.",
        hint: "Supported types are listed here; nothing you upload is executed.",
      },
      {
        route: "/evidence",
        anchor: "evidence-table",
        title: "See what was processed",
        body: "The vault lists every file with its digest, parser and processing status. Open a row to inspect metadata, map columns, or verify integrity.",
      },
      {
        route: "/events",
        anchor: "events-list",
        title: "Review extracted events",
        body: "Parsers turn files into readable events. Mark each one relevant or not relevant — decisions are audited and never delete the source evidence.",
      },
      {
        route: "",
        anchor: "narrative",
        title: "Read the case summary",
        body: "The narrative lists chronological observations with links back to the record behind each statement. It describes what was recorded, not a proven sequence.",
      },
    ],
  },
  {
    id: "evidence-integrity",
    name: "Upload and verify evidence",
    description: "Hashing, processing status and integrity verification.",
    steps: [
      {
        route: "/evidence/intake",
        anchor: "evidence-dropzone",
        title: "Evidence intake",
        body: "Drop files here or choose them from disk. The upload is stored unchanged and only then parsed.",
      },
      {
        route: "/evidence/intake",
        anchor: "evidence-pipeline",
        title: "Per-file processing",
        body: "Every file shows its own pipeline: uploaded, hashed, parsed, and whether records were skipped.",
        hint: "A partially parsed file is still usable unless a warning says otherwise.",
      },
      {
        route: "/evidence/intake",
        anchor: "warning-panel",
        title: "Warnings explain themselves",
        body: "Each parser warning states what happened, why it matters, what you can do, and whether the file remains usable.",
      },
      {
        route: "/evidence",
        anchor: "evidence-table",
        title: "The evidence vault",
        body: "Every stored file keeps its original name, size, SHA-256 digest and upload time.",
      },
      {
        route: "/evidence",
        anchor: "evidence-detail",
        title: "Verify integrity",
        body: "Open a file and run Verify integrity to re-hash the stored bytes. A mismatch means the file changed after intake.",
        hint: "Verification proves the stored file matches its digest — not that it was authentic before acquisition.",
      },
    ],
  },
  {
    id: "relationship-graph",
    name: "Explore relationship graphs",
    description: "Nodes, connections, provenance and confidence.",
    steps: [
      {
        route: "/graph",
        anchor: "graph-canvas",
        title: "The connection map",
        body: "Entities such as phone numbers, devices and accounts are nodes. A line means a documented connection between them.",
      },
      {
        route: "/graph",
        anchor: "graph-mode",
        title: "Simple and advanced",
        body: "Simple shows only entities with a documented connection. Advanced adds raw events and evidence files.",
      },
      {
        route: "/graph",
        anchor: "graph-connections-list",
        title: "Select an entity",
        body: "Use this list when the canvas is dense. Selecting an entity shows its mentions, evidence sources and every connection.",
      },
      {
        route: "/graph",
        anchor: "graph-legend",
        title: "Read the labels",
        body: "Colour and shape identify entity types. Solid lines are documented matches; dashed lines are heuristic leads.",
      },
      {
        route: "/graph",
        anchor: "graph-selection",
        title: "Ask why",
        body: "Clicking a connection shows the explanation and the supporting records, with source locators you can open.",
        hint: "A connection is a lead, never proof of identity or guilt.",
      },
      {
        route: "/graph",
        anchor: "graph-filters",
        title: "Filter the noise",
        body: "Narrow by evidence source, review status or entity visibility, and include temporal leads only when you want candidates.",
      },
    ],
  },
  {
    id: "timeline",
    name: "Build an investigation timeline",
    description: "Chronology, filters and correlated activity.",
    steps: [
      {
        route: "/timeline",
        anchor: "timeline-view",
        title: "Choose a view",
        body: "All events, correlated events, or flagged events. Correlated groups share a documented relationship.",
      },
      {
        route: "/timeline",
        anchor: "timeline-filters",
        title: "Filter by source and time",
        body: "Restrict to one evidence file or a date range. Filtering happens on the server so large cases stay responsive.",
      },
      {
        route: "/timeline",
        anchor: "timeline-events",
        title: "Read the sequence",
        body: "Each card states what was recorded in plain language, with its timestamp confidence and source locator.",
      },
      {
        route: "/timeline",
        anchor: "timeline-events",
        title: "Open the source record",
        body: "Selecting an event shows the original record, the extracted fields, and any linked findings — plus its review decision.",
      },
      {
        route: "/timeline",
        anchor: "timeline-undated",
        title: "Undated records stay visible",
        body: "Records without a usable timestamp are listed separately instead of being forced into a false position.",
      },
    ],
  },
  {
    id: "ai-assistant",
    name: "Use the AI investigation assistant",
    description: "Grounded questions, citations and hypotheses.",
    steps: [
      {
        route: "/ai",
        anchor: "ai-suggestions",
        title: "Start from a real question",
        body: "Suggested questions are derived from this case — unreviewed findings, shared identifiers, authentication events.",
      },
      {
        route: "/ai",
        anchor: "ai-composer",
        title: "Ask about the evidence",
        body: "The assistant answers only from stored records. If the evidence is insufficient, it says so instead of inventing an answer.",
      },
      {
        route: "/ai",
        anchor: "ai-conversation",
        title: "Check the citations",
        body: "Each answer lists the records it used. Verified citations link straight to the evidence or event.",
        hint: "An unverified citation is a warning sign, not a source.",
      },
      {
        route: "/ai",
        anchor: "ai-conversation",
        title: "Separate observation from interpretation",
        body: "Answers label themselves as observation, correlation, inference or hypothesis, and list limitations separately.",
      },
      {
        route: "/ai",
        anchor: "ai-conversation",
        title: "Save a hypothesis",
        body: "Save as hypothesis stores the answer as an annotation for human review. It never becomes a finding automatically.",
      },
    ],
  },
];

export const TOUR_INDEX = new Map(TOURS.map((tour) => [tour.id, tour]));
