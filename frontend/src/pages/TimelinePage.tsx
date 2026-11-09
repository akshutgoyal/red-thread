import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CalendarClock, GitBranch, Search, ShieldQuestion } from "lucide-react";
import { useEvidence, useReviewEvent, useTimeline, useEventReviews } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Field";
import { SegmentedControl } from "@/components/ui/Primitives";
import { formatDateTime, humanize } from "@/lib/format";
import { EVENT_CATEGORIES, describeEvent, eventCategory } from "@/lib/eventDescription";
import type { EventRecord, TimelineGroup, TimelineEventMeta } from "@/types";

const CONFIDENCE_CLASS: Record<string, string> = {
  exact:
    "border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  inferred_year:
    "border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-200",
  ambiguous:
    "border-orange-300 dark:border-orange-500/40 bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-200",
  unknown:
    "border-rose-300 dark:border-rose-500/40 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-200",
};

const REVIEW_CLASS: Record<string, string> = {
  relevant: "border-emerald-300 text-emerald-700 dark:border-emerald-500/40 dark:text-emerald-200",
  not_relevant: "border-line-strong text-muted",
  needs_review:
    "border-amber-300 text-amber-700 dark:border-amber-500/40 dark:text-amber-200",
};

type ViewMode = "all" | "correlated" | "suspicious";

export function TimelinePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [searchParams] = useSearchParams();
  const deepEventId = searchParams.get("event");
  const [search, setSearch] = useState("");
  const [view, setView] = useState<ViewMode>("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [confidenceFilter, setConfidenceFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selected, setSelected] = useState<EventRecord | null>(null);

  // Range/source/type filters are applied by the API so large cases stay responsive.
  const timelineQuery = useTimeline(caseId, {
    start: startDate ? `${startDate}T00:00:00` : undefined,
    end: endDate ? `${endDate}T23:59:59` : undefined,
    evidence_id: sourceFilter === "all" ? undefined : sourceFilter,
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

  const events = useMemo(() => timelineQuery.data?.items ?? [], [timelineQuery.data]);
  const undated = useMemo(() => timelineQuery.data?.undated ?? [], [timelineQuery.data]);
  const meta = useMemo(
    () => timelineQuery.data?.event_meta ?? {},
    [timelineQuery.data],
  );
  const groups = useMemo(() => timelineQuery.data?.groups ?? [], [timelineQuery.data]);

  const correlatedEventIds = useMemo(() => {
    const ids = new Set<string>();
    for (const group of groups) for (const id of group.event_ids) ids.add(id);
    return ids;
  }, [groups]);

  const filtered = useMemo(
    () =>
      events.filter((event) => {
        const text =
          `${event.event_type} ${event.source_filename} ${event.source_snippet} ${describeEvent(event)}`.toLowerCase();
        const matchesSearch = !search || text.includes(search.toLowerCase());
        const matchesCategory =
          categoryFilter === "all" || eventCategory(event.event_type) === categoryFilter;
        const matchesConfidence =
          confidenceFilter === "all" || event.timestamp_confidence === confidenceFilter;
        const metaEntry = meta[event.id];
        const matchesView =
          view === "all"
            ? true
            : view === "correlated"
              ? correlatedEventIds.has(event.id)
              : Boolean(metaEntry?.suspicious);
        return matchesSearch && matchesCategory && matchesConfidence && matchesView;
      }),
    [events, search, categoryFilter, confidenceFilter, view, meta, correlatedEventIds],
  );

  useEffect(() => {
    if (!deepEventId) return;
    const match = events.find((event) => event.id === deepEventId);
    if (match) setSelected(match);
  }, [deepEventId, events]);

  /** Groups are rendered inline with the events they contain, keyed by first event. */
  const groupsByFirstEvent = useMemo(() => {
    const map = new Map<string, TimelineGroup>();
    for (const group of groups) {
      const first = group.event_ids[0];
      if (first) map.set(first, group);
    }
    return map;
  }, [groups]);

  const grouped = useMemo(() => {
    const buckets = new Map<string, EventRecord[]>();
    for (const event of filtered) {
      const day = event.timestamp_normalized
        ? new Date(event.timestamp_normalized).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
          })
        : "Unknown date";
      const list = buckets.get(day) ?? [];
      list.push(event);
      buckets.set(day, list);
    }
    return Array.from(buckets.entries());
  }, [filtered]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) {
      const category = eventCategory(event.event_type);
      counts.set(category, (counts.get(category) ?? 0) + 1);
    }
    return counts;
  }, [events]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (timelineQuery.isLoading) return <LoadingState label="Building timeline…" />;
  if (timelineQuery.error)
    return (
      <ErrorState
        message={timelineQuery.error.message}
        onRetry={() => timelineQuery.refetch()}
      />
    );

  return (
    <div>
      <PageHeader
        eyebrow="Unified timeline"
        title="Investigation timeline"
        description="Every extracted event in time order, with a readable description and the source record behind it. Grouped events share a documented relationship — proximity alone is never presented as causation."
      />

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            label="Timeline view"
            value={view}
            onChange={setView}
            options={[
              { value: "all", label: "All events" },
              { value: "correlated", label: "Correlated", icon: <GitBranch size={12} /> },
              { value: "suspicious", label: "Flagged" },
            ]}
          />
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-2.5 text-muted" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search events or descriptions"
              className="w-52 pl-8 text-xs"
              aria-label="Search events"
            />
          </div>
          <Select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            className="w-40 text-xs"
            aria-label="Event category"
          >
            <option value="all">All categories</option>
            {EVENT_CATEGORIES.map((category) => (
              <option key={category.value} value={category.value}>
                {category.label}
                {categoryCounts.get(category.value)
                  ? ` (${categoryCounts.get(category.value)})`
                  : ""}
              </option>
            ))}
          </Select>
          <Select
            value={confidenceFilter}
            onChange={(event) => setConfidenceFilter(event.target.value)}
            className="w-40 text-xs"
            aria-label="Timestamp confidence"
          >
            <option value="all">All confidence</option>
            <option value="exact">Exact</option>
            <option value="inferred_year">Inferred year</option>
            <option value="ambiguous">Ambiguous</option>
            <option value="unknown">Unknown</option>
          </Select>
          <Select
            value={sourceFilter}
            onChange={(event) => setSourceFilter(event.target.value)}
            className="w-48 text-xs"
            aria-label="Evidence source"
          >
            <option value="all">All evidence sources</option>
            {(evidenceQuery.data ?? []).map((evidence) => (
              <option key={evidence.id} value={evidence.id}>
                {evidence.original_filename}
              </option>
            ))}
          </Select>
          <Input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="w-36 text-xs"
            aria-label="Start date"
          />
          <Input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="w-36 text-xs"
            aria-label="End date"
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Chronological events"
          subtitle={`${filtered.length} shown${
            timelineQuery.data?.total
              ? ` of ${timelineQuery.data.total} dated event(s)`
              : ""
          }${undated.length ? ` · ${undated.length} undated` : ""}`}
        />
        <CardBody>
          {filtered.length === 0 ? (
            <EmptyState
              title="No events match these filters"
              description="Clear the filters, or upload and parse evidence to populate the timeline."
              icon={CalendarClock}
            />
          ) : (
            <div className="space-y-8">
              {grouped.map(([day, dayEvents]) => (
                <div key={day}>
                  <div className="mb-3 flex items-center gap-3">
                    <span className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-accent">
                      {day}
                    </span>
                    <span className="h-px flex-1 bg-surface-2" />
                    <span className="text-[10px] text-muted">
                      {dayEvents.length} event(s)
                    </span>
                  </div>
                  <div className="relative space-y-3 border-l border-line pl-5">
                    {dayEvents.map((event) => {
                      const eventMeta: TimelineEventMeta | undefined = meta[event.id];
                      const group = groupsByFirstEvent.get(event.id);
                      const review = reviews.get(event.id);
                      return (
                        <div key={event.id}>
                          {group ? (
                            <div className="mb-2 rounded-xl border border-accent/25 bg-accent/5 px-3 py-2 text-[11px] leading-relaxed text-secondary">
                              <p className="font-semibold text-accent">{group.title}</p>
                              <p className="mt-0.5 text-muted">{group.explanation}</p>
                            </div>
                          ) : null}
                          <button
                            type="button"
                            onClick={() => setSelected(event)}
                            className="relative block w-full rounded-xl border border-line bg-surface-2/40 p-4 text-left transition hover:border-accent/30 hover:bg-surface/60"
                          >
                            <span className="absolute -left-[25px] top-5 h-2.5 w-2.5 rounded-full border-2 border-accent bg-app" />
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="text-sm font-medium text-primary">
                                    {humanize(event.event_type)}
                                  </p>
                                  <Badge
                                    className={
                                      CONFIDENCE_CLASS[event.timestamp_confidence] ?? ""
                                    }
                                  >
                                    {humanize(event.timestamp_confidence)}
                                  </Badge>
                                  {eventMeta?.suspicious ? (
                                    <Badge className="border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
                                      Flagged
                                    </Badge>
                                  ) : null}
                                  {correlatedEventIds.has(event.id) ? (
                                    <Badge className="border-accent/30 bg-accent/10 text-accent">
                                      Correlated
                                    </Badge>
                                  ) : null}
                                  {review ? (
                                    <Badge className={REVIEW_CLASS[review] ?? ""}>
                                      {humanize(review)}
                                    </Badge>
                                  ) : null}
                                </div>
                                <p className="mt-1 text-xs leading-relaxed text-secondary">
                                  {describeEvent(event)}
                                </p>
                                <p className="mt-1 text-[11px] text-muted">
                                  {event.timestamp_normalized
                                    ? formatDateTime(event.timestamp_normalized)
                                    : "No normalized timestamp"}
                                  {event.timestamp_raw
                                    ? ` · raw: ${event.timestamp_raw}`
                                    : ""}
                                </p>
                              </div>
                              <div className="text-right text-[10px] text-muted">
                                <p>
                                  {evidenceNames.get(event.evidence_id) ??
                                    event.source_filename}
                                </p>
                                <p className="font-mono">{event.source_locator}</p>
                              </div>
                            </div>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {undated.length > 0 ? (
        <Card className="mt-5 border-amber-200 dark:border-amber-500/20">
          <CardHeader
            title="Undated or uncertain events"
            subtitle="Preserved without forcing false chronological precision"
          />
          <CardBody className="space-y-2">
            {undated.map((event) => (
              <button
                type="button"
                key={event.id}
                onClick={() => setSelected(event)}
                className="flex w-full flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-left dark:border-amber-500/20 dark:bg-amber-500/5"
              >
                <div>
                  <p className="text-xs font-medium text-amber-800/90 dark:text-amber-100/90">
                    {describeEvent(event)}
                  </p>
                  <p className="text-[10px] text-amber-700/70 dark:text-amber-200/60">
                    {event.source_filename} · {event.source_locator}
                  </p>
                </div>
                <Badge className="border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                  <ShieldQuestion size={11} /> {humanize(event.timestamp_confidence)}
                </Badge>
              </button>
            ))}
          </CardBody>
        </Card>
      ) : null}

      <EventDrawer
        caseId={caseId}
        event={selected}
        onClose={() => setSelected(null)}
        meta={selected ? meta[selected.id] : undefined}
        review={selected ? reviews.get(selected.id) : undefined}
      />
    </div>
  );
}

function EventDrawer({
  caseId,
  event,
  onClose,
  meta,
  review,
}: {
  caseId: string;
  event: EventRecord | null;
  onClose: () => void;
  meta?: TimelineEventMeta;
  review?: string;
}) {
  const reviewMutation = useReviewEvent(caseId);
  const [note, setNote] = useState("");

  useEffect(() => {
    setNote("");
  }, [event?.id]);

  return (
    <Drawer
      open={Boolean(event)}
      onClose={onClose}
      title="Event detail"
      subtitle={event ? `${event.source_filename} · ${event.source_locator}` : undefined}
      wide
    >
      {event ? (
        <div className="space-y-5">
          <div className="rounded-xl border border-line bg-surface-2/40 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
              What this event shows
            </p>
            <p className="mt-1 text-sm leading-relaxed text-secondary">
              {describeEvent(event)}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <Info label="Event type" value={humanize(event.event_type)} />
            <Info label="Confidence" value={humanize(event.timestamp_confidence)} />
            <Info label="Raw timestamp" value={event.timestamp_raw || "—"} mono />
            <Info
              label="Normalized (UTC)"
              value={event.timestamp_normalized || "Not normalized"}
              mono
            />
            <Info label="Source file" value={event.source_filename} />
            <Info label="Source locator" value={event.source_locator} mono />
            <Info label="Parser" value={`${event.parser_name} ${event.parser_version}`} />
            <Info label="Event ID" value={event.id} mono />
          </div>

          {(meta?.finding_ids.length ?? 0) > 0 || (meta?.relationship_ids.length ?? 0) > 0 ? (
            <div className="flex flex-wrap gap-2 text-[11px]">
              {meta?.finding_ids.length ? (
                <Badge className="border-rose-300 text-rose-700 dark:border-rose-500/40 dark:text-rose-200">
                  {meta.finding_ids.length} linked finding(s)
                </Badge>
              ) : null}
              {meta?.relationship_ids.length ? (
                <Badge className="border-accent/30 text-accent">
                  {meta.relationship_ids.length} correlated relationship(ies)
                </Badge>
              ) : null}
            </div>
          ) : null}

          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Original source record
            </p>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[11px] leading-relaxed text-accent">
              {event.source_snippet || "No source snippet stored."}
            </pre>
          </div>

          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Extracted fields
            </p>
            <pre className="max-h-64 overflow-auto rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[10px] leading-relaxed text-muted">
              {JSON.stringify(event.attributes_json, null, 2)}
            </pre>
          </div>

          {event.warnings_json.length > 0 ? (
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-500/80">
                Parser warnings for this record
              </p>
              {event.warnings_json.map((warning, index) => (
                <p
                  key={index}
                  className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-[11px] text-amber-800/80 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80"
                >
                  {warning}
                </p>
              ))}
            </div>
          ) : null}

          <div className="rounded-xl border border-line bg-surface-2/40 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
              Is this event relevant?
            </p>
            <p className="mt-1 text-[11px] leading-relaxed text-muted">
              Review decisions are stored with an audit trail. Marking an event not
              relevant never deletes the original evidence.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={review === "relevant" ? "primary" : "secondary"}
                onClick={() =>
                  reviewMutation.mutate({
                    eventId: event.id,
                    payload: { decision: "relevant", note },
                  })
                }
              >
                Relevant
              </Button>
              <Button
                size="sm"
                variant={review === "needs_review" ? "primary" : "secondary"}
                onClick={() =>
                  reviewMutation.mutate({
                    eventId: event.id,
                    payload: { decision: "needs_review", note },
                  })
                }
              >
                Needs review
              </Button>
              <Button
                size="sm"
                variant={review === "not_relevant" ? "primary" : "secondary"}
                onClick={() =>
                  reviewMutation.mutate({
                    eventId: event.id,
                    payload: { decision: "not_relevant", note },
                  })
                }
              >
                Not relevant
              </Button>
            </div>
            <Input
              value={note}
              onChange={(changeEvent) => setNote(changeEvent.target.value)}
              placeholder="Optional note for the audit trail"
              className="mt-2 w-full text-xs"
            />
            {reviewMutation.isError ? (
              <p className="mt-2 text-[11px] text-rose-600">
                {(reviewMutation.error as Error).message}
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            <Link to={`/cases/${caseId}/graph?focusType=event&focusId=${event.id}`}>
              <Button size="sm" variant="secondary">
                View in graph
              </Button>
            </Link>
            <Link to={`/cases/${caseId}/ai?focusType=event&focusId=${event.id}`}>
              <Button size="sm" variant="secondary">
                Ask AI about this event
              </Button>
            </Link>
            <Link to={`/cases/${caseId}/evidence?evidenceId=${event.evidence_id}`}>
              <Button size="sm" variant="secondary">
                Open evidence
              </Button>
            </Link>
            {Number.isFinite(Number(event.attributes_json?.latitude)) &&
            Number.isFinite(Number(event.attributes_json?.longitude)) ? (
              <Link to={`/cases/${caseId}/spatial?event=${event.id}`}>
                <Button size="sm" variant="secondary">
                  View on map
                </Button>
              </Link>
            ) : null}
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
