import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  Clock,
  FileSearch,
  GitBranch,
  PlayCircle,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Users,
} from "lucide-react";
import {
  useAnnotations,
  useCreateAnnotation,
  useEventReviews,
  useEvidence,
  useFindings,
  useGuidance,
  useReconstruction,
  useReconstructionSequence,
  useRelationships,
  useReviewEvent,
} from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Tabs } from "@/components/ui/Primitives";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { PageGuide } from "@/components/guidance/PageGuide";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { FindingsPage } from "@/pages/FindingsPage";
import { SpatialPage } from "@/pages/SpatialPage";
import { TimelinePage } from "@/pages/TimelinePage";
import { formatDateTime, humanize } from "@/lib/format";
import { glossary } from "@/lib/glossary";
import type { SequenceEvent } from "@/types";

type WorkspaceTab =
  | "overview"
  | "timeline"
  | "relationships"
  | "locations"
  | "findings"
  | "sequence";

const TABS: { value: WorkspaceTab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "sequence", label: "Event reconstruction" },
  { value: "timeline", label: "Timeline" },
  { value: "relationships", label: "Relationships" },
  { value: "locations", label: "Locations" },
  { value: "findings", label: "Findings" },
];

const CONFIDENCE_TONE: Record<string, string> = {
  documented:
    "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200",
  supported:
    "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200",
  correlated:
    "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200",
  uncertain:
    "border-line bg-surface-2 text-secondary",
};

const CONFIDENCE_LABEL: Record<string, string> = {
  documented: "Documented",
  supported: "Supported",
  correlated: "Possible correlation",
  uncertain: "Uncertain",
};

const CATEGORY_LABEL: Record<string, string> = {
  communication: "Communication",
  financial: "Financial",
  authentication: "Authentication",
  device: "Device",
  location: "Location",
  visual: "Visual",
  other: "Other",
};

export function CrimeReconstructionPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get("tab") as WorkspaceTab | null;
  const tab: WorkspaceTab = TABS.some((item) => item.value === requested)
    ? (requested as WorkspaceTab)
    : "overview";

  function setTab(next: WorkspaceTab) {
    const params = new URLSearchParams(searchParams);
    if (next === "overview") params.delete("tab");
    else params.set("tab", next);
    setSearchParams(params, { replace: true });
  }
  const [category, setCategory] = useState<string>("all");
  const [openEvent, setOpenEvent] = useState<SequenceEvent | null>(null);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(null);

  const reconstructionQuery = useReconstruction(caseId);
  const sequenceQuery = useReconstructionSequence(caseId, { limit: 500 });
  const evidenceQuery = useEvidence(caseId);
  const findingsQuery = useFindings(caseId);
  const relationshipsQuery = useRelationships(caseId, { limit: 500 });
  const guidanceQuery = useGuidance(caseId);
  const reviewsQuery = useEventReviews(caseId);
  const annotationsQuery = useAnnotations(caseId);
  const createAnnotation = useCreateAnnotation(caseId ?? "");
  const reviewEvent = useReviewEvent(caseId ?? "");
  const toast = useToast();
  const [note, setNote] = useState("");

  const data = reconstructionQuery.data;
  const sequence = sequenceQuery.data;

  const reviewMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const review of reviewsQuery.data?.items ?? []) {
      map[review.event_id] = review.decision;
    }
    return map;
  }, [reviewsQuery.data]);

  const filteredSequence = useMemo(() => {
    if (!sequence) return [];
    if (category === "all") return sequence.items;
    return sequence.items.filter((item) => item.category === category);
  }, [sequence, category]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (reconstructionQuery.isLoading) {
    return <LoadingState label="Building reconstruction…" />;
  }
  if (reconstructionQuery.error) {
    return (
      <ErrorState
        message={reconstructionQuery.error.message}
        onRetry={() => reconstructionQuery.refetch()}
      />
    );
  }

  const allRelationships = relationshipsQuery.data?.items ?? [];

  // Count from the backend's canonical figure, not from a capped page of rows.
  const unreviewedCount = data?.counts.unreviewed_relationships ?? 0;
  const reviewQueue = allRelationships.filter((relationship) =>
    ["unreviewed", "needs_review", "needs_more_evidence"].includes(
      relationship.review_status,
    ),
  );

  // Mirrors the backend's documented classifications ("observation" and
  // "correlation") rather than inventing a new label.
  const documentedRelationships = (relationshipsQuery.data?.items ?? []).filter(
    (relationship) =>
      relationship.classification === "observation" ||
      relationship.classification === "correlation",
  );

  const evidenceCount = evidenceQuery.data?.length ?? data?.counts.evidence ?? 0;

  function addNote() {
    const trimmed = note.trim();
    if (!caseId || !trimmed) return;
    createAnnotation.mutate(
      { target_type: "case", target_id: caseId, author: "Investigator", note: trimmed },
      {
        onSuccess: () => {
          setNote("");
          toast.push("success", "Observation recorded");
        },
        onError: (error) => toast.push("error", "Could not record", error.message),
      },
    );
  }

  function decide(eventId: string, decision: "relevant" | "not_relevant" | "needs_review") {
    reviewEvent.mutate(
      { eventId, payload: { decision } },
      {
        onSuccess: () => toast.push("success", "Review recorded", "Audit-logged."),
        onError: (error) => toast.push("error", "Could not review", error.message),
      },
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Crime reconstruction"
        title={data ? "Reconstruct what happened" : "Crime reconstruction"}
        description="One workspace for the sequence of events, the entities involved, how they connect, where events occurred, and the evidence behind each claim."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/cases/${caseId}/graph`}>
              <Button variant="secondary" icon={<GitBranch size={14} />}>
                Advanced graph
              </Button>
            </Link>
            <Link to={`/cases/${caseId}/reports`}>
              <Button variant="secondary" icon={<ScrollText size={14} />}>
                Reports
              </Button>
            </Link>
          </div>
        }
      />

      <PageGuide page="reconstruction" caseId={caseId} guidance={guidanceQuery.data} />

      <Tabs
        label="Crime reconstruction sections"
        tabs={TABS.map((item) => ({
          ...item,
          count:
            item.value === "sequence"
              ? sequence?.total
              : item.value === "findings"
                ? findingsQuery.data?.items.length
                : undefined,
        }))}
        value={tab}
        onChange={setTab}
      />

      {tab === "overview" && data ? (
        <OverviewTab
          data={data}
          evidenceCount={evidenceCount}
          sequence={sequence}
          reviewQueueCount={unreviewedCount}
          documentedCount={documentedRelationships.length}
          onOpenTab={setTab}
          onSelectEvent={(event) => setOpenEvent(event)}
          findingsCount={findingsQuery.data?.items.length ?? 0}
        />
      ) : null}

      {tab === "sequence" ? (
        <SequenceTab
          sequence={sequence}
          loading={sequenceQuery.isLoading}
          error={sequenceQuery.error?.message}
          retry={() => sequenceQuery.refetch()}
          category={category}
          onCategory={setCategory}
          items={filteredSequence}
          reviewMap={reviewMap}
          onSelect={setOpenEvent}
          onDecide={decide}
          caseId={caseId}
        />
      ) : null}

      {tab === "timeline" ? <TimelinePage embedded /> : null}
      {tab === "locations" ? <SpatialPage embedded /> : null}
      {tab === "findings" ? <FindingsPage embedded /> : null}

      {tab === "relationships" ? (
        <RelationshipsTab
          caseId={caseId}
          relationships={allRelationships}
          documented={documentedRelationships}
          selectedId={selectedRelationshipId}
          onSelect={setSelectedRelationshipId}
          reviewQueue={reviewQueue}
        />
      ) : null}

      {tab === "overview" ? (
        <ObservationsCard
          notes={annotationsQuery.data ?? []}
          value={note}
          onChange={setNote}
          onSubmit={addNote}
          pending={createAnnotation.isPending}
        />
      ) : null}

      <Drawer
        open={Boolean(openEvent)}
        onClose={() => setOpenEvent(null)}
        title={openEvent ? openEvent.label : "Event"}
        subtitle={
          openEvent
            ? `${openEvent.source_filename} · ${openEvent.source_locator}`
            : undefined
        }
        wide
      >
        {openEvent ? (
          <SequenceEventDetail
            caseId={caseId}
            event={openEvent}
            reviewStatus={reviewMap[openEvent.id] ?? openEvent.review_status}
            onDecide={decide}
          />
        ) : null}
      </Drawer>
    </div>
  );
}

function OverviewTab({
  data,
  evidenceCount,
  sequence,
  reviewQueueCount,
  documentedCount,
  findingsCount,
  onOpenTab,
  onSelectEvent,
}: {
  data: NonNullable<ReturnType<typeof useReconstruction>["data"]>;
  evidenceCount: number;
  sequence?: NonNullable<ReturnType<typeof useReconstructionSequence>["data"]>;
  reviewQueueCount: number;
  documentedCount: number;
  findingsCount: number;
  onOpenTab: (tab: WorkspaceTab) => void;
  onSelectEvent: (event: SequenceEvent) => void;
}) {
  const metrics: { label: string; value: number | string; hint: string; tab?: WorkspaceTab }[] = [
    {
      label: "Evidence",
      value: evidenceCount,
      hint: glossary("provenance").explanation,
      tab: "overview",
    },
    {
      label: "Events",
      value: data.counts.events,
      hint: "Records extracted from the uploaded evidence.",
      tab: "sequence",
    },
    {
      label: "Entities",
      value: data.counts.entities,
      hint: glossary("entity").explanation,
      tab: "relationships",
    },
    {
      label: "Relationships",
      value: data.counts.relationships,
      hint: glossary("correlation").explanation,
      tab: "relationships",
    },
    {
      label: "Locations",
      value: data.counts.spatial_observations,
      hint: "Documented coordinates only. No routes are inferred.",
      tab: "locations",
    },
    {
      label: "Findings",
      value: findingsCount,
      hint: "Deterministic findings produced by the reconciliation checks.",
      tab: "findings",
    },
    {
      label: "Awaiting review",
      value: reviewQueueCount,
      hint: glossary("review_status").explanation,
      tab: "relationships",
    },
    {
      label: "Documented links",
      value: documentedCount,
      hint: "Connections backed directly by source evidence, not inference.",
      tab: "relationships",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <button
            key={metric.label}
            type="button"
            onClick={() => metric.tab && onOpenTab(metric.tab)}
            className="rounded-xl border border-line bg-card p-4 text-left transition-colors hover:border-accent/40"
          >
            <p className="text-[10px] uppercase tracking-wider text-muted">
              {metric.label}
            </p>
            <p className="mt-1 text-2xl font-semibold text-primary">{metric.value}</p>
            <p className="mt-1 text-[10px] leading-relaxed text-muted">{metric.hint}</p>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader
          title="What happened in this case?"
          subtitle="Ordered from stored records. Every statement links back to the evidence behind it."
          action={
            sequence ? <Badge>{sequence.total} records</Badge> : null
          }
        />
        <CardBody className="space-y-2">
          {!sequence ? (
            <p className="text-xs text-muted">Building the sequence…</p>
          ) : sequence.items.length === 0 ? (
            <p className="text-xs text-muted">
              No dated events yet. Upload and process evidence to build a sequence.
            </p>
          ) : (
            sequence.items.slice(0, 8).map((event, index) => (
              <button
                key={event.id}
                type="button"
                onClick={() => onSelectEvent(event)}
                className="flex w-full gap-3 rounded-lg border border-line bg-surface-2/40 px-3 py-2 text-left transition-colors hover:border-accent/30"
              >
                <span className="mt-0.5 shrink-0 font-mono text-[10px] text-muted">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <Badge>{CATEGORY_LABEL[event.category] ?? event.category}</Badge>
                    <span className="text-[10px] text-muted">
                      {formatDateTime(event.timestamp)}
                    </span>
                  </span>
                  <span className="mt-1 block text-[11px] leading-relaxed text-primary">
                    {event.description}
                  </span>
                  <span className="mt-1 block text-[10px] text-muted">
                    source: {event.source_filename} · {event.source_locator}
                  </span>
                </span>
              </button>
            ))
          )}
          {sequence && sequence.items.length > 8 ? (
            <Button variant="ghost" size="sm" onClick={() => onOpenTab("sequence")}>
              Open the full reconstructed sequence
            </Button>
          ) : null}
        </CardBody>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Limitations"
            subtitle="Generated by the deterministic reconstruction service."
          />
          <CardBody className="space-y-1.5">
            {(data.limitations ?? []).map((limitation) => (
              <p key={limitation} className="flex gap-2 text-[11px] leading-relaxed text-secondary">
                <ShieldCheck size={12} className="mt-0.5 shrink-0 text-muted" />
                {limitation}
              </p>
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Unresolved questions"
            subtitle="What still needs investigator attention."
            action={<Badge>{data.unresolved.length}</Badge>}
          />
          <CardBody className="space-y-2">
            {data.unresolved.length === 0 ? (
              <p className="text-xs text-muted">No outstanding automated flags.</p>
            ) : (
              (data.unresolved ?? []).map((item) => (
                <div
                  key={item}
                  className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[11px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                >
                  <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                  <span>{item}</span>
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function SequenceTab({
  sequence,
  loading,
  error,
  retry,
  category,
  onCategory,
  items,
  reviewMap,
  onSelect,
  onDecide,
  caseId,
}: {
  sequence?: NonNullable<ReturnType<typeof useReconstructionSequence>["data"]>;
  loading: boolean;
  error?: string;
  retry: () => void;
  category: string;
  onCategory: (value: string) => void;
  items: SequenceEvent[];
  reviewMap: Record<string, string>;
  onSelect: (event: SequenceEvent) => void;
  onDecide: (eventId: string, decision: "relevant" | "not_relevant" | "needs_review") => void;
  caseId: string;
}) {
  if (loading) return <LoadingState label="Reconstructing the sequence…" />;
  if (error) return <ErrorState message={error} onRetry={retry} />;
  if (!sequence) return null;

  const categories = Object.entries(sequence.categories).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Reconstructed sequence of events"
          subtitle="Communication, financial, authentication, device and location records in time order. Each record states how strongly it is supported."
          action={<Badge>{items.length} shown</Badge>}
        />
        <CardBody className="space-y-3">
          <Tabs
            label="Filter by category"
            tabs={[
              { value: "all", label: "All", count: sequence.total },
              ...categories.map(([key, count]) => ({
                value: key,
                label: CATEGORY_LABEL[key] ?? humanize(key),
                count,
              })),
            ]}
            value={category}
            onChange={onCategory}
          />

          {sequence.gaps.length > 0 ? (
            <div className="space-y-1.5">
              {sequence.gaps.map((gap) => (
                <p
                  key={`${gap.start}-${gap.end}`}
                  className="flex gap-2 rounded-lg border border-line bg-surface-2/40 p-2.5 text-[11px] text-secondary"
                >
                  <Clock size={13} className="mt-0.5 shrink-0 text-muted" />
                  {gap.message}
                </p>
              ))}
            </div>
          ) : null}

          {items.length === 0 ? (
            <EmptyState
              title="No records in this category"
              description="Try another category, or upload more evidence."
            />
          ) : (
            <ol className="space-y-2">
              {items.map((event) => (
                <li key={event.id}>
                  <SequenceRow
                    caseId={caseId}
                    event={event}
                    reviewStatus={reviewMap[event.id] ?? event.review_status}
                    onOpen={() => onSelect(event)}
                    onDecide={onDecide}
                  />
                </li>
              ))}
            </ol>
          )}

          {sequence.undated.length > 0 ? (
            <div className="rounded-lg border border-line bg-surface-2/40 p-3">
              <p className="text-[11px] font-medium text-primary">
                {sequence.undated.length} record(s) without a usable timestamp
              </p>
              <p className="mt-1 text-[10px] text-muted">
                These cannot be placed in sequence without inventing an order for them.
              </p>
              <div className="mt-2 space-y-1">
                {sequence.undated.map((event) => (
                  <button
                    key={event.id}
                    type="button"
                    onClick={() => onSelect(event)}
                    className="block w-full truncate text-left text-[11px] text-secondary hover:text-accent"
                  >
                    {event.description}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <p className="text-[10px] leading-relaxed text-muted">
            Ordering reflects the timestamps recorded in each source. It does not by itself
            establish that one event caused another.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}

function SequenceRow({
  caseId,
  event,
  reviewStatus,
  onOpen,
  onDecide,
}: {
  caseId: string;
  event: SequenceEvent;
  reviewStatus: string;
  onOpen: () => void;
  onDecide: (eventId: string, decision: "relevant" | "not_relevant" | "needs_review") => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/40 p-3 transition-colors hover:border-accent/30">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{CATEGORY_LABEL[event.category] ?? event.category}</Badge>
          <span className="text-[10px] text-muted">
            {formatDateTime(event.timestamp)}
          </span>
          {event.timestamp_confidence !== "exact" ? (
            <span className="text-[10px] text-muted">
              ({humanize(event.timestamp_confidence)} timestamp)
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${
              CONFIDENCE_TONE[event.confidence] ?? CONFIDENCE_TONE.uncertain
            }`}
          >
            {CONFIDENCE_LABEL[event.confidence] ?? event.confidence}
          </span>
          {reviewStatus !== "unreviewed" ? (
            <Badge>{humanize(reviewStatus)}</Badge>
          ) : null}
        </div>
      </div>

      <button
        type="button"
        onClick={onOpen}
        className="mt-1.5 block w-full text-left text-[11px] leading-relaxed text-primary hover:text-accent"
      >
        {event.description}
      </button>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {event.entities.slice(0, 5).map((entity) => (
          <span
            key={`${entity.id}-${entity.role}`}
            className="inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-[10px] text-secondary"
          >
            <Users size={9} className="text-muted" />
            {entity.value}
          </span>
        ))}
        {event.entities.length > 5 ? (
          <span className="text-[10px] text-muted">
            +{event.entities.length - 5} more
          </span>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2">
        <Link
          to={`/cases/${caseId}/evidence?evidenceId=${event.evidence_id}`}
          className="inline-flex items-center gap-1 text-[10px] text-muted hover:text-accent"
        >
          <FileSearch size={10} /> {event.source_filename} · {event.source_locator}
        </Link>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => onDecide(event.id, "relevant")}
            className="rounded border border-line px-2 py-0.5 text-[10px] text-muted transition-colors hover:border-emerald-400 hover:text-emerald-600"
          >
            Relevant
          </button>
          <button
            type="button"
            onClick={() => onDecide(event.id, "needs_review")}
            className="rounded border border-line px-2 py-0.5 text-[10px] text-muted transition-colors hover:border-amber-400 hover:text-amber-600"
          >
            Needs review
          </button>
          <button
            type="button"
            onClick={() => onDecide(event.id, "not_relevant")}
            className="rounded border border-line px-2 py-0.5 text-[10px] text-muted transition-colors hover:border-rose-400 hover:text-rose-600"
          >
            Not relevant
          </button>
        </div>
      </div>
    </div>
  );
}

function RelationshipsTab({
  caseId,
  relationships,
  documented,
  selectedId,
  onSelect,
  reviewQueue,
}: {
  caseId: string;
  relationships: { id: string; relationship_type: string; explanation: string; classification: string; review_status: string; confidence: string }[];
  documented: { id: string }[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  reviewQueue: { id: string; relationship_type: string; explanation: string; review_status: string }[];
}) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Relationship analysis"
          subtitle="Connections extracted from evidence. Documented links are supported by a source record; inferred leads are suggestions to check."
          action={<Badge>{relationships.length} total</Badge>}
        />
        <CardBody className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge>{documented.length} documented</Badge>
            <Badge>{relationships.length - documented.length} inferred / observational</Badge>
            <Badge>{reviewQueue.length} awaiting review</Badge>
          </div>

          {relationships.length === 0 ? (
            <EmptyState
              title="No relationships yet"
              description="Process evidence to extract entities and the connections between them."
            />
          ) : (
            <div className="grid gap-2 md:grid-cols-2">
              {relationships.slice(0, 40).map((relationship) => (
                <button
                  key={relationship.id}
                  type="button"
                  onClick={() => onSelect(relationship.id)}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    selectedId === relationship.id
                      ? "border-accent/40 bg-accent/10"
                      : "border-line bg-surface-2/40 hover:border-accent/30"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-primary">
                      {humanize(relationship.relationship_type)}
                    </span>
                    <div className="flex gap-1">
                      <Badge>{relationship.classification}</Badge>
                      <Badge>{relationship.review_status}</Badge>
                    </div>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-secondary">
                    {relationship.explanation}
                  </p>
                </button>
              ))}
            </div>
          )}

          <Link
            to={`/cases/${caseId}/graph`}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-accent"
          >
            Open the full relationship graph for advanced analysis <ArrowRight size={12} />
          </Link>
        </CardBody>
      </Card>

      {selectedId ? (
        <Card>
          <RelationshipEvidencePanel
            caseId={caseId}
            relationshipId={selectedId}
            onClose={() => onSelect(null)}
          />
        </Card>
      ) : null}
    </div>
  );
}

function SequenceEventDetail({
  caseId,
  event,
  reviewStatus,
  onDecide,
}: {
  caseId: string;
  event: SequenceEvent;
  reviewStatus: string;
  onDecide: (eventId: string, decision: "relevant" | "not_relevant" | "needs_review") => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{CATEGORY_LABEL[event.category] ?? event.category}</Badge>
        <span
          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${
            CONFIDENCE_TONE[event.confidence] ?? CONFIDENCE_TONE.uncertain
          }`}
        >
          {CONFIDENCE_LABEL[event.confidence] ?? event.confidence}
        </span>
        <Badge>{humanize(reviewStatus)}</Badge>
      </div>

      <div>
        <p className="text-sm font-medium text-primary">{event.description}</p>
        <p className="mt-1 text-[11px] text-muted">{event.confidence_reason}</p>
      </div>

      <div className="rounded-lg border border-line bg-surface-2/40 p-3">
        <p className="text-[10px] uppercase tracking-wider text-muted">Timestamp</p>
        <p className="mt-1 text-xs text-primary">{formatDateTime(event.timestamp)}</p>
        {event.timestamp_raw ? (
          <p className="mt-1 font-mono text-[10px] text-muted">
            recorded as: {event.timestamp_raw}
            {event.timestamp_timezone ? ` (${event.timestamp_timezone})` : ""}
          </p>
        ) : null}
        <p className="mt-1 text-[10px] text-muted">
          confidence: {event.timestamp_confidence}
        </p>
      </div>

      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted">
          Source evidence
        </p>
        <Link
          to={`/cases/${caseId}/evidence?evidenceId=${event.evidence_id}`}
          className="mt-1 inline-flex items-center gap-1 text-xs text-accent"
        >
          <FileSearch size={12} /> {event.source_filename} · {event.source_locator}
        </Link>
        {event.source_snippet ? (
          <pre className="mt-2 max-h-40 overflow-auto rounded-lg border border-line bg-surface p-2 font-mono text-[10px] text-secondary">
            {event.source_snippet.slice(0, 1200)}
          </pre>
        ) : null}
      </div>

      {event.entities.length > 0 ? (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted">
            Entities involved
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {event.entities.map((entity) => (
              <Link
                key={`${entity.id}-${entity.role}`}
                to={`/cases/${caseId}/graph?focusType=entity&focusId=${entity.id}`}
                className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[10px] text-secondary hover:border-accent/40 hover:text-accent"
              >
                {entity.value}
                <span className="text-muted">({entity.role})</span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      {event.relationships.length > 0 ? (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted">
            Related connections
          </p>
          <div className="mt-1 space-y-1">
            {event.relationships.slice(0, 10).map((relationship) => (
              <Link
                key={relationship.id}
                to={`/cases/${caseId}/graph?focusType=relationship&focusId=${relationship.id}`}
                className="block rounded-lg border border-line bg-surface-2/40 p-2 text-[10px] text-secondary hover:border-accent/30 hover:text-accent"
              >
                <span className="font-medium text-primary">
                  {humanize(relationship.relationship_type)}
                </span>{" "}
                · {relationship.counterpart_value}
                <span className="mt-0.5 block line-clamp-2">{relationship.explanation}</span>
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      {event.finding_ids.length > 0 ? (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-muted">Findings</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {event.finding_ids.map((id) => (
              <Link
                key={id}
                to={`/cases/${caseId}/findings?finding=${id}`}
                className="rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[10px] text-secondary hover:border-accent/40 hover:text-accent"
              >
                View finding
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 border-t border-line pt-3">
        <Button
          size="sm"
          variant="secondary"
          icon={<PlayCircle size={13} />}
          onClick={() => onDecide(event.id, "relevant")}
        >
          Mark relevant
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => onDecide(event.id, "needs_review")}
        >
          Needs review
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onDecide(event.id, "not_relevant")}
        >
          Not relevant
        </Button>
      </div>

      <p className="text-[10px] leading-relaxed text-muted">
        Review decisions are recorded in the audit trail. They record an investigator's
        assessment, not a proven fact.
      </p>
    </div>
  );
}

function ObservationsCard({
  notes,
  value,
  onChange,
  onSubmit,
  pending,
}: {
  notes: { id: string; note: string; author?: string; created_at: string; target_type: string }[];
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  pending: boolean;
}) {
  return (
    <Card>
      <CardHeader
        title="Investigations & reconstruction notes"
        subtitle="Human observations, stored separately from deterministic evidence and included in the audit trail."
        action={<Badge>{notes.length}</Badge>}
      />
      <CardBody className="space-y-3">
        {notes.length === 0 ? (
          <p className="text-xs text-muted">
            No investigator notes yet. Record what you observed and which evidence supports it.
          </p>
        ) : (
          <div className="space-y-2">
            {notes.map((note) => (
              <div key={note.id} className="rounded-lg border border-line bg-surface-2/40 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge>{humanize(note.target_type)}</Badge>
                  <span className="text-[10px] text-muted">
                    {note.author || "Investigator"} · {formatDateTime(note.created_at)}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-line text-[11px] leading-relaxed text-secondary">
                  {note.note}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="rounded-xl border border-line bg-surface-2/40 p-3">
          <Textarea
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Record an observation and which evidence supports it…"
            rows={3}
            className="text-xs"
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <p className="text-[10px] text-muted">
              Notes are attributable and appear in reports.
            </p>
            <Button
              size="sm"
              variant="primary"
              icon={<RefreshCw size={13} />}
              loading={pending}
              disabled={!value.trim()}
              onClick={onSubmit}
            >
              Add note
            </Button>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
