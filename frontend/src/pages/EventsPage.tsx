import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ListFilter, Search } from "lucide-react";
import { useEvents, useEventReviews, useEvidence, useReviewEvent } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input, Select } from "@/components/ui/Field";
import { Drawer } from "@/components/ui/Drawer";
import { PageIntro, SegmentedControl } from "@/components/ui/Primitives";
import { formatDateTime, humanize } from "@/lib/format";
import { describeEvent } from "@/lib/eventDescription";
import type { EventRecord } from "@/types";

const REVIEW_CLASS: Record<string, string> = {
  relevant:
    "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200",
  not_relevant: "border-line-strong bg-surface-2/70 text-muted",
  needs_review:
    "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
};

const STATUS_LABEL: Record<string, string> = {
  relevant: "Relevant",
  not_relevant: "Not relevant",
  needs_review: "Needs review",
};

type ReviewFilter = "all" | "unreviewed" | "relevant" | "needs_review" | "not_relevant";

export function EventsPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [searchParams] = useSearchParams();
  const initialEvidence = searchParams.get("evidenceId") ?? "all";
  const [search, setSearch] = useState("");
  const [evidenceFilter, setEvidenceFilter] = useState(initialEvidence);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [selected, setSelected] = useState<EventRecord | null>(null);

  const eventsQuery = useEvents(caseId, {
    limit: 1000,
    evidence_id: evidenceFilter === "all" ? undefined : evidenceFilter,
  });
  const evidenceQuery = useEvidence(caseId);
  const reviewsQuery = useEventReviews(caseId);

  const evidenceNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of evidenceQuery.data ?? []) map.set(item.id, item.original_filename);
    return map;
  }, [evidenceQuery.data]);

  const reviews = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of reviewsQuery.data?.items ?? []) map.set(item.event_id, item.decision);
    return map;
  }, [reviewsQuery.data]);

  const events = useMemo(() => {
    const rows = [...(eventsQuery.data?.items ?? [])];
    const text = search.trim().toLowerCase();
    const filtered = rows.filter((event) => {
      if (
        text &&
        !`${event.event_type} ${event.source_snippet} ${describeEvent(event)}`
          .toLowerCase()
          .includes(text)
      ) {
        return false;
      }
      const decision = reviews.get(event.id) ?? "unreviewed";
      if (reviewFilter === "unreviewed") return decision === "unreviewed";
      if (reviewFilter !== "all") return decision === reviewFilter;
      return true;
    });
    filtered.sort((left, right) => {
      const leftTime = left.timestamp_normalized ?? "";
      const rightTime = right.timestamp_normalized ?? "";
      return sort === "newest"
        ? rightTime.localeCompare(leftTime)
        : leftTime.localeCompare(rightTime);
    });
    return filtered;
  }, [eventsQuery.data, search, reviewFilter, reviews, sort]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (eventsQuery.isLoading) return <LoadingState label="Loading extracted events…" />;
  if (eventsQuery.error)
    return (
      <ErrorState message={eventsQuery.error.message} onRetry={() => eventsQuery.refetch()} />
    );

  const total = eventsQuery.data?.total ?? 0;
  const reviewed = reviews.size;

  return (
    <div>
      <PageHeader
        eyebrow="Step 4 · Review events"
        title="Extracted events"
        description="Every row the parsers extracted, in readable form. Mark events relevant, not relevant, or needing review; decisions are stored with an audit trail and never delete the source evidence."
      />

      <PageIntro
        what="A flat, searchable list of every extracted event before it is placed on the timeline."
        why="You can confirm the parser read each record correctly and flag what matters to the case."
        next="Mark events, then open the timeline to see them in time order with correlated activity."
      />

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-2.5 text-muted" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search events"
              className="w-56 pl-8 text-xs"
              aria-label="Search extracted events"
            />
          </div>
          <Select
            value={evidenceFilter}
            onChange={(event) => setEvidenceFilter(event.target.value)}
            className="w-52 text-xs"
            aria-label="Evidence source"
          >
            <option value="all">All evidence sources</option>
            {(evidenceQuery.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.original_filename}
              </option>
            ))}
          </Select>
          <SegmentedControl
            label="Review status"
            value={reviewFilter}
            onChange={setReviewFilter}
            options={[
              { value: "all", label: "All" },
              { value: "unreviewed", label: "Unreviewed" },
              { value: "relevant", label: "Relevant" },
              { value: "needs_review", label: "Needs review" },
              { value: "not_relevant", label: "Not relevant" },
            ]}
          />
          <Select
            value={sort}
            onChange={(event) => setSort(event.target.value as "newest" | "oldest")}
            className="w-36 text-xs"
            aria-label="Sort order"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </Select>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Event records"
          subtitle={`${events.length} shown of ${total}${
            reviewed ? ` · ${reviewed} reviewed` : ""
          }`}
          action={
            <span className="inline-flex items-center gap-1 text-[11px] text-muted">
              <ListFilter size={12} /> Filters apply to stored events
            </span>
          }
        />
        <CardBody className="space-y-2">
          {events.length === 0 ? (
            <EmptyState
              title="No events match"
              description="Parse evidence first, or clear the filters."
            />
          ) : (
            events.map((event) => {
              const decision = reviews.get(event.id);
              return (
                <button
                  key={event.id}
                  type="button"
                  onClick={() => setSelected(event)}
                  className="block w-full rounded-xl border border-line bg-surface-2/30 p-3.5 text-left transition hover:border-accent/30 hover:bg-surface/60"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-primary">
                          {humanize(event.event_type)}
                        </p>
                        {decision ? (
                          <Badge className={REVIEW_CLASS[decision] ?? ""}>
                            {STATUS_LABEL[decision] ?? humanize(decision)}
                          </Badge>
                        ) : null}
                        <Badge className="border-line-strong bg-surface-2/70 text-muted">
                          {humanize(event.timestamp_confidence)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-secondary">
                        {describeEvent(event)}
                      </p>
                      <p className="mt-1 text-[11px] text-muted">
                        {event.timestamp_normalized
                          ? formatDateTime(event.timestamp_normalized)
                          : "No normalized timestamp"}
                        {" · "}
                        {evidenceNames.get(event.evidence_id) ?? event.source_filename}
                        {" · "}
                        <span className="font-mono">{event.source_locator}</span>
                      </p>
                    </div>
                    <span className="font-mono text-[10px] text-muted">
                      {event.id.slice(0, 8)}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </CardBody>
      </Card>

      <EventReviewDrawer
        caseId={caseId}
        event={selected}
        onClose={() => setSelected(null)}
        decision={selected ? reviews.get(selected.id) : undefined}
      />
    </div>
  );
}

function EventReviewDrawer({
  caseId,
  event,
  onClose,
  decision,
}: {
  caseId: string;
  event: EventRecord | null;
  onClose: () => void;
  decision?: string;
}) {
  const review = useReviewEvent(caseId);
  const [note, setNote] = useState("");

  return (
    <Drawer
      open={Boolean(event)}
      onClose={onClose}
      title="Review extracted event"
      subtitle={event ? `${event.source_filename} · ${event.source_locator}` : undefined}
      wide
    >
      {event ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-line bg-surface-2/40 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
              Plain-language description
            </p>
            <p className="mt-1 text-sm leading-relaxed text-secondary">
              {describeEvent(event)}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <Info label="Event ID" value={event.id} mono />
            <Info label="Timestamp (UTC)" value={event.timestamp_normalized || "—"} mono />
            <Info label="Source" value={event.source_filename} />
            <Info label="Locator" value={event.source_locator} mono />
          </div>

          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Original record
            </p>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[11px] leading-relaxed text-accent">
              {event.source_snippet || "No source snippet stored."}
            </pre>
          </div>

          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Extracted fields
            </p>
            <pre className="max-h-56 overflow-auto rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[10px] text-muted">
              {JSON.stringify(event.attributes_json, null, 2)}
            </pre>
          </div>

          <div className="rounded-xl border border-line bg-surface-2/40 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
              Mark for this investigation
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted">
              This decision is stored in the case audit trail. The original evidence is
              preserved either way.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(
                [
                  ["relevant", "Relevant"],
                  ["needs_review", "Needs review"],
                  ["not_relevant", "Not relevant"],
                ] as const
              ).map(([value, label]) => (
                <Button
                  key={value}
                  size="sm"
                  variant={decision === value ? "primary" : "secondary"}
                  onClick={() =>
                    review.mutate({ eventId: event.id, payload: { decision: value, note } })
                  }
                >
                  {label}
                </Button>
              ))}
            </div>
            <Input
              value={note}
              onChange={(inputEvent) => setNote(inputEvent.target.value)}
              placeholder="Optional note"
              className="mt-2 w-full text-xs"
            />
            {review.isError ? (
              <p className="mt-2 text-[11px] text-rose-600">
                {(review.error as Error).message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            <Link to={`/cases/${caseId}/timeline?event=${event.id}`}>
              <Button size="sm" variant="secondary">
                Open in timeline
              </Button>
            </Link>
            <Link to={`/cases/${caseId}/evidence?evidenceId=${event.evidence_id}`}>
              <Button size="sm" variant="ghost">
                Open evidence
              </Button>
            </Link>
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}

function Info({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/40 px-3 py-2">
      <p className="text-[9px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-0.5 break-all text-xs text-secondary ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}
