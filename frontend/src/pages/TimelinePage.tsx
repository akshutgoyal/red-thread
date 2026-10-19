import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { CalendarClock, Search, ShieldQuestion } from "lucide-react";
import { useEvidence, useTimeline } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input, Select } from "@/components/ui/Field";
import { formatDateTime, humanize } from "@/lib/format";
import type { EventRecord } from "@/types";

const CONFIDENCE_CLASS: Record<string, string> = {
  exact: "border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200",
  inferred_year: "border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-200",
  ambiguous: "border-orange-300 dark:border-orange-500/40 bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-200",
  unknown: "border-rose-300 dark:border-rose-500/40 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-200",
};

export function TimelinePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const timelineQuery = useTimeline(caseId);
  const evidenceQuery = useEvidence(caseId);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [confidenceFilter, setConfidenceFilter] = useState("all");
  const [selected, setSelected] = useState<EventRecord | null>(null);

  const evidenceNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of evidenceQuery.data ?? []) map.set(item.id, item.original_filename);
    return map;
  }, [evidenceQuery.data]);

  const events = useMemo(() => timelineQuery.data?.items ?? [], [timelineQuery.data]);
  const undated = useMemo(() => timelineQuery.data?.undated ?? [], [timelineQuery.data]);

  const filtered = useMemo(
    () =>
      events.filter((event) => {
        const text = `${event.event_type} ${event.source_filename} ${event.source_snippet}`.toLowerCase();
        const matchesSearch = !search || text.includes(search.toLowerCase());
        const matchesType = typeFilter === "all" || event.event_type === typeFilter;
        const matchesConfidence =
          confidenceFilter === "all" || event.timestamp_confidence === confidenceFilter;
        return matchesSearch && matchesType && matchesConfidence;
      }),
    [events, search, typeFilter, confidenceFilter],
  );

  const grouped = useMemo(() => {
    const groups = new Map<string, EventRecord[]>();
    for (const event of filtered) {
      const day = event.timestamp_normalized
        ? new Date(event.timestamp_normalized).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
          })
        : "Unknown date";
      const list = groups.get(day) ?? [];
      list.push(event);
      groups.set(day, list);
    }
    return Array.from(groups.entries());
  }, [filtered]);

  const eventTypes = useMemo(
    () => Array.from(new Set(events.map((event) => event.event_type))).sort(),
    [events],
  );

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (timelineQuery.isLoading) return <LoadingState label="Building timeline…" />;
  if (timelineQuery.error)
    return (
      <ErrorState message={timelineQuery.error.message} onRetry={() => timelineQuery.refetch()} />
    );

  return (
    <div>
      <PageHeader
        eyebrow="Unified timeline"
        title="Investigation timeline"
        description="Normalized events ordered chronologically. Raw timestamps and confidence are preserved; undated events are shown separately."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-2.5 text-muted" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search events"
                className="w-52 pl-8 text-xs"
              />
            </div>
            <Select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              className="w-44 text-xs"
            >
              <option value="all">All event types</option>
              {eventTypes.map((type) => (
                <option key={type} value={type}>
                  {humanize(type)}
                </option>
              ))}
            </Select>
            <Select
              value={confidenceFilter}
              onChange={(event) => setConfidenceFilter(event.target.value)}
              className="w-44 text-xs"
            >
              <option value="all">All confidence</option>
              <option value="exact">Exact</option>
              <option value="inferred_year">Inferred year</option>
              <option value="ambiguous">Ambiguous</option>
              <option value="unknown">Unknown</option>
            </Select>
          </div>
        }
      />

      <Card>
        <CardHeader
          title="Chronological events"
          subtitle={`${filtered.length} dated event(s)${undated.length ? ` · ${undated.length} undated` : ""}`}
        />
        <CardBody>
          {filtered.length === 0 ? (
            <EmptyState
              title="No dated events"
              description="Upload and parse evidence to populate the timeline."
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
                      const attributes = event.attributes_json as Record<string, unknown>;
                      return (
                        <button
                          type="button"
                          key={event.id}
                          onClick={() => setSelected(event)}
                          className="relative block w-full rounded-xl border border-line bg-surface-2/40 p-4 text-left transition hover:border-accent/30 hover:bg-surface/60"
                        >
                          <span className="absolute -left-[25px] top-5 h-2.5 w-2.5 rounded-full border-2 border-accent bg-app" />
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-medium text-primary">
                                  {humanize(event.event_type)}
                                </p>
                                <Badge className={CONFIDENCE_CLASS[event.timestamp_confidence] ?? ""}>
                                  {humanize(event.timestamp_confidence)}
                                </Badge>
                              </div>
                              <p className="mt-1 text-[11px] text-muted">
                                {event.timestamp_normalized
                                  ? formatDateTime(event.timestamp_normalized)
                                  : "No normalized timestamp"}
                                {event.timestamp_raw ? ` · raw: ${event.timestamp_raw}` : ""}
                              </p>
                            </div>
                            <div className="text-right text-[10px] text-muted">
                              <p>
                                {evidenceNames.get(event.evidence_id) ?? event.source_filename}
                              </p>
                              <p className="font-mono">{event.source_locator}</p>
                            </div>
                          </div>
                          {Object.keys(attributes).length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {["username", "source_ip", "auth_status", "amount", "utr", "payee_vpa"]
                                .filter((key) => attributes[key] !== undefined && attributes[key] !== null)
                                .map((key) => (
                                  <span
                                    key={key}
                                    className="rounded-md border border-line bg-surface/70 px-2 py-0.5 font-mono text-[10px] text-muted"
                                  >
                                    {key}: {String(attributes[key])}
                                  </span>
                                ))}
                            </div>
                          ) : null}
                        </button>
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
                className="flex w-full flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 px-3 py-2 text-left"
              >
                <div>
                  <p className="text-xs font-medium text-amber-800/90 dark:text-amber-100/90">
                    {humanize(event.event_type)}
                  </p>
                  <p className="text-[10px] text-amber-700/70 dark:text-amber-200/60">
                    {event.source_filename} · {event.source_locator}
                  </p>
                </div>
                <Badge className="border-amber-300 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-200">
                  <ShieldQuestion size={11} /> {humanize(event.timestamp_confidence)}
                </Badge>
              </button>
            ))}
          </CardBody>
        </Card>
      ) : null}

      <Drawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title="Timeline event"
        subtitle={selected ? `${selected.source_filename} · ${selected.source_locator}` : undefined}
        wide
      >
        {selected ? (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <Info label="Event type" value={selected.event_type} />
              <Info label="Confidence" value={humanize(selected.timestamp_confidence)} />
              <Info label="Raw timestamp" value={selected.timestamp_raw || "—"} mono />
              <Info
                label="Normalized (UTC)"
                value={selected.timestamp_normalized || "Not normalized"}
                mono
              />
              <Info label="Source file" value={selected.source_filename} />
              <Info label="Source locator" value={selected.source_locator} mono />
              <Info label="Parser" value={`${selected.parser_name} ${selected.parser_version}`} />
              <Info label="Evidence ID" value={selected.evidence_id} mono />
            </div>
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Source snippet
              </p>
              <pre className="whitespace-pre-wrap break-words rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[11px] leading-relaxed text-accent">
                {selected.source_snippet || "No source snippet stored."}
              </pre>
            </div>
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Attributes
              </p>
              <pre className="max-h-64 overflow-auto rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[10px] leading-relaxed text-muted">
                {JSON.stringify(selected.attributes_json, null, 2)}
              </pre>
            </div>
            {selected.warnings_json.length > 0 ? (
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-500/80">
                  Warnings
                </p>
                {selected.warnings_json.map((warning, index) => (
                  <p
                    key={index}
                    className="mb-1 rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 px-3 py-2 text-[11px] text-amber-800/80 dark:text-amber-100/80"
                  >
                    {warning}
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </Drawer>
    </div>
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
