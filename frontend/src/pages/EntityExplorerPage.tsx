import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Search, Waypoints } from "lucide-react";
import { useEntities, useEntityDetail, useEvidence } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { formatDateTime, humanize } from "@/lib/format";

const TYPE_COLORS: Record<string, string> = {
  phone: "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200",
  email: "border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-200",
  ip: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200",
  device_id: "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
  gps_point: "border-cyan-300 bg-cyan-50 text-cyan-700 dark:border-cyan-500/40 dark:bg-cyan-500/10 dark:text-cyan-200",
};

export function EntityExplorerPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const entitiesQuery = useEntities(caseId);
  const evidenceQuery = useEvidence(caseId ?? "");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(null);
  const detailQuery = useEntityDetail(caseId, selectedEntityId);

  const entities = useMemo(() => entitiesQuery.data ?? [], [entitiesQuery.data]);
  const evidenceNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of evidenceQuery.data ?? []) map.set(item.id, item.original_filename);
    return map;
  }, [evidenceQuery.data]);
  const types = useMemo(
    () => Array.from(new Set(entities.map((entity) => entity.entity_type))).sort(),
    [entities],
  );
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return entities.filter((entity) => {
      if (typeFilter !== "all" && entity.entity_type !== typeFilter) return false;
      if (!term) return true;
      return (
        entity.value_original.toLowerCase().includes(term) ||
        entity.value_normalized.toLowerCase().includes(term) ||
        entity.entity_type.toLowerCase().includes(term)
      );
    });
  }, [entities, search, typeFilter]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (entitiesQuery.isLoading) return <LoadingState label="Loading entities…" />;
  if (entitiesQuery.error)
    return (
      <ErrorState
        message={entitiesQuery.error.message}
        onRetry={() => entitiesQuery.refetch()}
      />
    );

  const detail = detailQuery.data;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Entity explorer"
        description="Identifiers, accounts, devices, IP addresses and documented locations extracted from the evidence."
        actions={<Badge>{entities.length} entities</Badge>}
      />

      <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader
            title="Extracted entities"
            subtitle="Every view is linked to its source evidence and events."
          />
          <CardBody className="space-y-3">
            <div className="relative">
              <Search
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search value or type…"
                className="pl-9"
              />
            </div>
            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              className="w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2 text-xs text-primary"
            >
              <option value="all">All entity types</option>
              {types.map((type) => (
                <option key={type} value={type}>
                  {humanize(type)}
                </option>
              ))}
            </select>
            <div className="max-h-[520px] space-y-1 overflow-y-auto pr-1">
              {filtered.length === 0 ? (
                <EmptyState
                  icon={Waypoints}
                  title="No matching entities"
                  description="Parse evidence to extract identifiers, or change the filter."
                />
              ) : (
                filtered.map((entity) => (
                  <button
                    key={entity.id}
                    type="button"
                    onClick={() => {
                      setSelectedEntityId(entity.id);
                      setSelectedRelationshipId(null);
                    }}
                    className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                      selectedEntityId === entity.id
                        ? "border-accent/40 bg-accent/10"
                        : "border-transparent hover:border-line hover:bg-surface-2"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Badge
                        className={
                          TYPE_COLORS[entity.entity_type] ??
                          "border-line bg-surface-2 text-secondary"
                        }
                      >
                        {humanize(entity.entity_type)}
                      </Badge>
                      <span className="text-[10px] text-muted">{entity.normalization_method}</span>
                    </div>
                    <p className="mt-1.5 truncate text-xs font-medium text-primary">
                      {entity.value_normalized || entity.value_original}
                      <span className="ml-2 text-[10px] text-muted">
                        {entity.event_count ?? 0} events · {entity.evidence_ids?.length ?? 0} sources
                      </span>
                    </p>
                  </button>
                ))
              )}
            </div>
          </CardBody>
        </Card>

        <div className="space-y-5">
          {!selectedEntityId ? (
            <Card>
              <CardBody>
                <EmptyState
                  icon={Waypoints}
                  title="Select an entity"
                  description="Inspect every mention, event and evidence-backed relationship for a phone number, device, account or location."
                />
              </CardBody>
            </Card>
          ) : detailQuery.isLoading ? (
            <LoadingState label="Loading entity detail…" />
          ) : detailQuery.error ? (
            <ErrorState
              message={detailQuery.error.message}
              onRetry={() => detailQuery.refetch()}
            />
          ) : detail ? (
            <>
              <Card>
                <CardHeader
                  title={detail.entity.value_normalized || detail.entity.value_original}
                  subtitle={`${humanize(detail.entity.entity_type)} · ${detail.mention_count} mentions · ${detail.evidence_ids.length} evidence sources`}
                  action={
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        className={
                          TYPE_COLORS[detail.entity.entity_type] ??
                          "border-line bg-surface-2 text-secondary"
                        }
                      >
                        {humanize(detail.entity.entity_type)}
                      </Badge>
                      <Link
                        to={`/cases/${caseId}/graph?focusType=entity&focusId=${detail.entity.id}`}
                      >
                        <Button size="sm" variant="secondary">
                          View in graph
                        </Button>
                      </Link>
                      <Link
                        to={`/cases/${caseId}/ai?focusType=entity&focusId=${detail.entity.id}`}
                      >
                        <Button size="sm" variant="secondary">
                          Ask AI
                        </Button>
                      </Link>
                    </div>
                  }
                />
                <CardBody className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-lg border border-line bg-surface-2/60 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-muted">Original value</p>
                      <p className="mt-1 break-all text-xs font-medium text-primary">
                        {detail.entity.value_original}
                      </p>
                    </div>
                    <div className="rounded-lg border border-line bg-surface-2/60 p-3">
                      <p className="text-[10px] uppercase tracking-wider text-muted">Normalized value</p>
                      <p className="mt-1 break-all text-xs font-medium text-primary">
                        {detail.entity.value_normalized}
                      </p>
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                      Evidence presence
                    </p>
                    {detail.evidence_ids.length === 0 ? (
                      <p className="text-xs text-muted">No evidence sources are linked.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {detail.evidence_ids.map((evidenceId) => {
                          const count = detail.events.filter(
                            (event) => event.evidence_id === evidenceId,
                          ).length;
                          return (
                            <div
                              key={evidenceId}
                              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface-2/40 px-3 py-2"
                            >
                              <Link
                                className="text-xs font-medium text-accent hover:underline"
                                to={`/cases/${caseId}/evidence?evidenceId=${evidenceId}`}
                              >
                                {evidenceNames.get(evidenceId) ?? evidenceId}
                              </Link>
                              <span className="text-[10px] text-muted">{count} events</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div>
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                      Evidence-backed relationships
                    </p>
                    {detail.relationships.length === 0 ? (
                      <p className="text-xs text-muted">No relationships generated for this entity.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {detail.relationships.slice(0, 20).map((relationship) => (
                          <button
                            key={relationship.id}
                            type="button"
                            onClick={() => setSelectedRelationshipId(relationship.id)}
                            className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                              selectedRelationshipId === relationship.id
                                ? "border-accent/40 bg-accent/10"
                                : "border-line bg-surface-2/40 hover:border-accent/30"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-medium text-primary">
                                {humanize(relationship.relationship_type)}
                              </span>
                              <Badge>{relationship.classification}</Badge>
                            </div>
                            <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-secondary">
                              {relationship.explanation}
                            </p>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </CardBody>
              </Card>

              {selectedRelationshipId ? (
                <Card>
                  <CardBody>
                    <RelationshipEvidencePanel
                      caseId={caseId}
                      relationshipId={selectedRelationshipId}
                      onClose={() => setSelectedRelationshipId(null)}
                    />
                  </CardBody>
                </Card>
              ) : null}

              <Card>
                <CardHeader
                  title="Mentioned events"
                  subtitle="Chronological evidence records that reference this entity."
                />
                <CardBody>
                  {detail.events.length === 0 ? (
                    <p className="text-xs text-muted">No events reference this entity.</p>
                  ) : (
                    <div className="space-y-2">
                      {detail.events.slice(0, 40).map((event) => (
                        <div
                          key={event.id}
                          className="rounded-lg border border-line bg-surface-2/40 px-3 py-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <Badge>{humanize(event.event_type)}</Badge>
                            <span className="text-[10px] text-muted">
                              {formatDateTime(event.timestamp_normalized)}
                            </span>
                          </div>
                          <p className="mt-1 text-[11px] text-secondary">
                            {event.source_filename} · {event.source_locator}
                          </p>
                          <div className="mt-1.5 flex flex-wrap gap-3 text-[10px] font-medium">
                            <Link
                              className="text-accent hover:underline"
                              to={`/cases/${caseId}/timeline?event=${event.id}`}
                            >
                              View timeline event
                            </Link>
                            <Link
                              className="text-accent hover:underline"
                              to={`/cases/${caseId}/evidence?evidenceId=${event.evidence_id}`}
                            >
                              Open evidence
                            </Link>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardBody>
              </Card>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
