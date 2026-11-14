import type { TourDefinition } from "./TourProvider";

/**
 * Guided investigation journey.
 *
 * One ordered tour covering the full investigation, plus five focused tours for
 * returning to a single topic. Every `route` is a real route in the app and
 * every `anchor` matches a `data-tour` attribute on a real element. No step
 * describes UI that does not exist, and no step performs an action on the
 * investigator's behalf.
 *
 * The journey is deliberately ordered so the relationship graph appears only
 * after evidence, entities and events have been explained. A first-time
 * investigator should understand what a connection is made of before seeing a
 * dense connection map.
 */
export const TOURS: TourDefinition[] = [
  {
    id: "investigation-journey",
    name: "Complete investigation journey",
    description:
      "The full workflow, from opening a case to generating a report, in the order an investigation actually runs.",
    steps: [
      // ---------------------------------------------------------- dashboard
      {
        route: "",
        anchor: "case-selector",
        title: "Every investigation is a case",
        body: "A case groups all evidence, extracted events, findings and reports for one investigation. This selector switches between the cases you can open.",
      },
      {
        route: "",
        anchor: "next-action",
        title: "Red Thread tells you the next step",
        body: "This panel is computed from the case's stored records, not written by hand. It names one action and explains why it matters now.",
        hint: "You can dismiss it, but it returns when the case state changes.",
      },
      {
        route: "",
        anchor: "workflow-progress",
        title: "Where this case stands",
        body: "The investigation runs through a fixed sequence. Each stage reports complete, in progress or not started based on real data — opening a page never marks it complete.",
      },

      // ------------------------------------------------------ create a case
      {
        route: "/cases",
        appRoute: true,
        anchor: "cases-create",
        title: "Create an investigation",
        body: "Name the case and record what you are looking into. That title and description become the context for everyone who opens it.",
        hint: "You can return here at any time to start another case.",
      },
      {
        route: "",
        anchor: "narrative",
        title: "The case overview connects everything",
        body: "Evidence is processed into events, events mention entities, entities form relationships, and relationships support findings. Each step inherits from the one before it.",
      },

      // ---------------------------------------------------- evidence intake
      {
        route: "/evidence/intake",
        anchor: "evidence-dropzone",
        title: "Step 1 — Upload evidence",
        body: "Start with the files you were given: logs, exports, images, location data. Each file is hashed with SHA-256 before parsing, so its stored bytes can be verified later.",
        hint: "Nothing you upload is executed. Unsupported files are rejected rather than guessed at.",
      },
      {
        route: "/evidence/intake",
        anchor: "evidence-pipeline",
        title: "What processing did to each file",
        body: "Every file has its own pipeline: uploaded, hashed, parsed, and how many records were extracted or rejected.",
      },
      {
        route: "/evidence/intake",
        anchor: "warning-panel",
        title: "Warnings explain themselves",
        body: "A parser warning states what happened, why it matters, what to do about it, and whether the file is still usable.",
      },
      {
        route: "/evidence",
        anchor: "evidence-table",
        title: "Step 2 — Verify integrity",
        body: "The vault keeps each file's original name, size, SHA-256 digest and upload time. Open a row to verify the stored bytes still match the digest.",
        hint: "Integrity shows the file is unchanged since intake — not that it was authentic when collected.",
      },

      // ------------------------------------------------------------ entities
      {
        route: "/entities",
        anchor: "entities-list",
        title: "Step 3 — Entities",
        body: "An entity is a person, phone number, device, account or identifier found in the evidence. Each one records which records mention it.",
      },
      {
        route: "/entities",
        anchor: "entities-list",
        title: "Follow an entity back to its source",
        body: "Opening an entity lists the events that mention it and the files those events came from, so you can confirm it is the same identifier and not a coincidence.",
      },

      // -------------------------------------------------------------- events
      {
        route: "/events",
        anchor: "events-list",
        title: "Step 4 — Events",
        body: "Information from different sources is converted into a common format called a normalised event, so a chat message and a login record can be compared.",
      },
      {
        route: "/events",
        anchor: "events-list",
        title: "Confirm what was extracted",
        body: "Check the original record beside each extracted event. Marking an event relevant or not relevant is written to the audit trail and never deletes evidence.",
      },

      // ------------------------------------------------------------ timeline
      {
        route: "/timeline",
        anchor: "timeline-view",
        title: "Step 5 — Timeline",
        body: "The timeline orders every dated event across all sources. Chronology is often what turns separate records into a sequence worth investigating.",
      },
      {
        route: "/timeline",
        anchor: "timeline-filters",
        title: "Compare sources",
        body: "Filter by evidence file or date range to compare what different sources recorded at the same time. Filtering happens on the server.",
        hint: "Timestamps carry a confidence value; clock drift between devices is common.",
      },
      {
        route: "/timeline",
        anchor: "timeline-events",
        title: "Records without a timestamp",
        body: "Event cards state their timestamp confidence. Records with no usable timestamp are listed in a separate section below instead of being forced into a position they cannot be proven to hold.",
      },

      // --------------------------------------------------------------- graph
      {
        route: "/graph",
        anchor: "graph-overview",
        title: "Step 6 — What this graph is",
        body: "Only now does the relationship graph make sense. Each node is an entity you have just reviewed; each line is a connection between two of them, backed by stored records.",
      },
      {
        route: "/graph",
        anchor: "graph-counts",
        title: "Read the counts precisely",
        body: "Total relationships counts every stored connection. Unique entity pairs counts each pair once, because several rules can describe the same pair. Inferred leads are hypotheses, not facts.",
        hint: "These numbers are computed from stored rows and match the workspace and dashboard.",
      },
      {
        route: "/graph",
        anchor: "graph-canvas",
        title: "Explore the connections",
        body: "Select an entity to see its mentions and every connection it takes part in. Solid lines are documented matches; dashed lines are heuristic leads.",
      },
      {
        route: "/graph",
        anchor: "graph-selection",
        title: "Always check the supporting evidence",
        body: "Clicking a connection shows its explanation and the exact records behind it. A connection is a lead until you have checked those records — it never proves shared identity or guilt.",
      },
      {
        route: "/graph",
        anchor: "graph-filters",
        title: "Reduce the noise",
        body: "Filter by evidence source, review status or entity visibility. Add temporal leads only when you want candidate connections based on timing.",
      },

      // -------------------------------------------------------------- spatial
      {
        route: "/spatial",
        anchor: "spatial-map",
        title: "Step 7 — Where things happened",
        body: "Locations are taken only from recorded evidence such as GPS, cell towers or place labels. Nothing is inferred to fill a gap.",
        hint: "An empty map means no location data was recorded, not that nothing happened.",
      },

      // ------------------------------------------------------------------ ai
      {
        route: "/ai",
        anchor: "ai-suggestions",
        title: "Step 8 — Ask about the evidence",
        body: "Suggested questions come from this case's actual state. The assistant answers only from stored records and says so when the evidence is insufficient.",
      },
      {
        route: "/ai",
        anchor: "ai-conversation",
        title: "Separate interpretation from fact",
        body: "Answers label themselves as observation, correlation, inference or hypothesis. Only the first two are grounded in records; the rest are hypotheses you must verify.",
        hint: "AI output is never a finding until a human reviews it.",
      },

      // ------------------------------------------------------------ findings
      {
        route: "/findings",
        anchor: "findings-list",
        title: "Step 9 — Findings and review",
        body: "A finding is an observation tied to the evidence that supports it. Severity is a triage signal, not a verdict.",
      },
      {
        route: "/findings",
        anchor: "findings-list",
        title: "Record a human decision",
        body: "Each finding carries a review status and any annotations. Unresolved questions stay visible so they are not lost in the report.",
      },

      // ------------------------------------------------------------- reports
      {
        route: "/reports",
        anchor: "reports-generate",
        title: "Step 10 — Generate the report",
        body: "The report assembles the case, its evidence digests, events, relationships, findings, review decisions and unresolved questions into a draft document.",
      },
      {
        route: "/reports",
        anchor: "reports-list",
        title: "Reports are drafts for human review",
        body: "Provenance and source references are included so every statement can be traced back. The report does not determine guilt and cannot be treated as a court finding without expert review.",
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
        anchor: "graph-counts",
        title: "What the counts mean",
        body: "Relationships are stored connections; unique entity pairs counts each pair once. If both numbers differ, several rules describe the same pair.",
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
        title: "Undated records stay visible",
        body: "Records without a usable timestamp are listed separately below the dated events instead of being forced into a false position.",
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
        title: "Save a hypothesis",
        body: "Save as hypothesis stores the answer as an annotation for human review. It never becomes a finding automatically.",
      },
    ],
  },
];

export const TOUR_INDEX = new Map(TOURS.map((tour) => [tour.id, tour]));
