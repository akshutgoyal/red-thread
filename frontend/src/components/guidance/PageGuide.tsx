import { Link } from "react-router-dom";
import { ArrowRight, Compass } from "lucide-react";
import type { GuidanceResponse } from "@/types";

/**
 * Contextual introduction for a page.
 *
 * The three answers — what this is, when to use it, what to do next — are
 * derived from the case's stored state, not written per page as static copy.
 * A page never recommends an action the case cannot support: if there is no
 * evidence, it says so and points at intake instead of at the graph.
 */

type PageKey =
  | "evidence-intake"
  | "evidence"
  | "entities"
  | "events"
  | "timeline"
  | "graph"
  | "spatial"
  | "findings"
  | "ai"
  | "reports";

interface Explainer {
  what: string;
  when: string;
}

const EXPLAINERS: Record<PageKey, Explainer> = {
  "evidence-intake": {
    what: "Where you add the files an investigation is built on. Each file is hashed before it is parsed, so its integrity can be proven later.",
    when: "Start here. Nothing else on the platform can happen until at least one evidence file exists.",
  },
  evidence: {
    what: "The record of every stored file, with its SHA-256 digest, parser and processing status.",
    when: "Use it after uploading to confirm a file parsed correctly, and before relying on any record to verify the file has not changed.",
  },
  entities: {
    what: "The people, phone numbers, devices, accounts and identifiers extracted from the evidence.",
    when: "Use it to check that the right identifiers were found, and to see every record that mentions one.",
  },
  events: {
    what: "Records from different sources converted into a common format, so they can be compared.",
    when: "Review these before the timeline or graph. Their decisions decide what the rest of the investigation is built on.",
  },
  timeline: {
    what: "Every dated event placed in chronological order across all evidence sources.",
    when: "Use it to find sequences, gaps and activity that several sources recorded at the same time.",
  },
  graph: {
    what: "A visual map of the connections between entities identified from the evidence.",
    when: "Use it after the evidence has been reviewed and entities have been extracted, to explore how sources connect.",
  },
  spatial: {
    what: "Recorded locations plotted on a map, taken only from coordinates or place names present in the evidence.",
    when: "Use it when the evidence includes GPS, cell tower or place data, to see where recorded activity happened.",
  },
  findings: {
    what: "Observations about the case, each tied to the evidence that supports it.",
    when: "Use it to review and record a decision on what the analysis surfaced, before generating a report.",
  },
  ai: {
    what: "An assistant that answers questions using only the records in this case, and cites what it used.",
    when: "Use it to summarise or cross-check, then verify every citation yourself before relying on an answer.",
  },
  reports: {
    what: "A draft document assembling the evidence inventory, timeline, findings, review decisions and limitations.",
    when: "Generate one once the findings have been reviewed. Treat the output as a draft for human review.",
  },
};

export function PageGuide({
  page,
  caseId,
  guidance,
}: {
  page: PageKey;
  caseId: string;
  guidance?: GuidanceResponse;
}) {
  const explainer = EXPLAINERS[page];
  const summary = guidance?.summary;
  const casePath = (suffix = "") => `/cases/${caseId}${suffix ? `/${suffix}` : ""}`;

  // Next step comes from the case state. If the case cannot support this page's
  // purpose yet, say so plainly rather than recommending the page's own action.
  let next: { text: string; label: string; href: string } | null = null;

  if (summary) {
    if (summary.evidence === 0) {
      next = {
        text: "This case has no evidence yet, so there is nothing to show here.",
        label: "Upload evidence",
        href: casePath("evidence/intake"),
      };
    } else if (page === "graph" && summary.entities === 0) {
      next = {
        text: "No entity connections have been found yet. Review the extracted events first.",
        label: "Review events",
        href: casePath("events"),
      };
    } else if (page === "reports" && summary.open_findings > 0) {
      next = {
        text: `${summary.open_findings} findings still need a review decision, so the report will list them as unresolved.`,
        label: "Review findings",
        href: casePath("findings"),
      };
    }
  }

  if (!next && guidance?.next_action) {
    const action = guidance.next_action;
    // Only surface the global next action when it belongs to another page.
    if (!action.href.startsWith(casePath(`/${page}`))) {
      next = { text: action.reason, label: action.action_label, href: action.href };
    }
  }

  return (
    <div className="mb-4 rounded-xl border border-line bg-surface-2/40 px-4 py-3 text-xs leading-relaxed">
      <div className="flex items-start gap-2.5">
        <Compass size={14} className="mt-0.5 shrink-0 text-accent" />
        <div className="min-w-0 space-y-1.5">
          <p className="text-secondary">
            <span className="font-semibold text-primary">What this is: </span>
            {explainer.what}
          </p>
          <p className="text-secondary">
            <span className="font-semibold text-primary">When to use it: </span>
            {explainer.when}
          </p>
          {next ? (
            <p className="flex flex-wrap items-baseline gap-1.5 text-secondary">
              <span className="font-semibold text-primary">Next: </span>
              <span>{next.text}</span>
              <Link
                to={next.href}
                className="inline-flex items-center gap-1 font-medium text-accent hover:underline"
              >
                {next.label}
                <ArrowRight size={11} />
              </Link>
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
