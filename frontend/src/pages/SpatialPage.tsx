import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { MapPin } from "lucide-react";
import { useEvidence, useSpatial } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { SpatialMap } from "@/components/spatial/SpatialMap";
import { formatDateTime, humanize } from "@/lib/format";

export function SpatialPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const spatialQuery = useSpatial(caseId);
  const evidenceQuery = useEvidence(caseId);
  const [searchParams] = useSearchParams();
  const deepEventId = searchParams.get("event");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("all");
  const [entityFilter, setEntityFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [relationshipId, setRelationshipId] = useState<string | null>(null);

  const evidenceById = useMemo(
    () => new Map((evidenceQuery.data ?? []).map((item) => [item.id, item])),
    [evidenceQuery.data],
  );

  useEffect(() => {
    if (!deepEventId) return;
    const match = (spatialQuery.data?.observations ?? []).find(
      (item) => item.event_id === deepEventId,
    );
    if (match) setSelectedId(match.event_id);
  }, [deepEventId, spatialQuery.data]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (spatialQuery.isLoading) return <LoadingState label="Loading documented locations…" />;
  if (spatialQuery.error)
    return <ErrorState message={spatialQuery.error.message} onRetry={() => spatialQuery.refetch()} />;

  const data = spatialQuery.data;
  const allObservations = data?.observations ?? [];
  const observations = allObservations.filter((item) => {
    if (typeFilter !== "all" && item.event_type !== typeFilter) return false;
    if (entityFilter !== "all" && !item.entity_values.includes(entityFilter)) return false;
    const day = item.timestamp_normalized?.slice(0, 10);
    if (startDate && (!day || day < startDate)) return false;
    if (endDate && (!day || day > endDate)) return false;
    return true;
  });
  const types = Array.from(new Set(allObservations.map((item) => item.event_type))).sort();
  const entityOptions = Array.from(
    new Set(allObservations.flatMap((item) => item.entity_values)),
  ).sort();
  const selected = observations.find((item) => item.event_id === selectedId) ?? null;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Spatial reconstruction"
        description="Documented GPS fixes and CCTV observations only. The map does not infer routes or movement between isolated points."
        actions={<Badge>{data?.observations.length ?? 0} observations</Badge>}
      />

      <p className="text-xs text-muted">
        Map times are normalized to UTC. Original source timestamps and their timezone
        context remain available in the timeline and evidence records. Map tiles load from
        OpenStreetMap by default; set VITE_MAP_TILE_URL to use a local tile server.
      </p>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface p-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
          Filters
        </span>
        <select
          value={entityFilter}
          onChange={(event) => setEntityFilter(event.target.value)}
          className="rounded-lg border border-line-strong bg-surface-2 px-2 py-1.5 text-[11px] text-primary"
        >
          <option value="all">All entities</option>
          {entityOptions.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
          className="rounded-lg border border-line-strong bg-surface-2 px-2 py-1.5 text-[11px] text-primary"
          aria-label="Start date"
        />
        <input
          type="date"
          value={endDate}
          onChange={(event) => setEndDate(event.target.value)}
          className="rounded-lg border border-line-strong bg-surface-2 px-2 py-1.5 text-[11px] text-primary"
          aria-label="End date"
        />
        <span className="text-[10px] text-muted">
          {observations.length} of {allObservations.length} observations shown
        </span>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card>
          <CardHeader
            title="Documented coordinate plot"
            subtitle={`${observations.length} plotted observations · ${data?.relationships.length ?? 0} spatial relationships`}
            action={
              <select
                value={typeFilter}
                onChange={(event) => setTypeFilter(event.target.value)}
                className="rounded-lg border border-line-strong bg-surface-2 px-2 py-1.5 text-[11px] text-primary"
              >
                <option value="all">All source types</option>
                {types.map((type) => (
                  <option key={type} value={type}>
                    {humanize(type)}
                  </option>
                ))}
              </select>
            }
          />
          <CardBody>
            {observations.length === 0 ? (
              <EmptyState
                icon={MapPin}
                title="No documented coordinates"
                description="Upload GPS or CCTV metadata with valid latitude and longitude to populate this view."
              />
            ) : (
              <SpatialMap observations={observations} selectedId={selectedId} onSelect={setSelectedId} />
            )}
          </CardBody>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader title="Observations" subtitle="Select a documented point to inspect its evidence." />
            <CardBody className="max-h-[430px] space-y-1.5 overflow-y-auto pr-1">
              {observations.map((observation) => (
                <button
                  key={observation.event_id}
                  type="button"
                  onClick={() => {
                    setSelectedId(observation.event_id);
                    setRelationshipId(null);
                  }}
                  className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                    selectedId === observation.event_id
                      ? "border-accent/40 bg-accent/10"
                      : "border-line bg-surface-2/40 hover:border-accent/30"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <Badge>{humanize(observation.event_type)}</Badge>
                    <span className="text-[10px] text-muted">
                      {formatDateTime(observation.timestamp_normalized)}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-xs font-medium text-primary">
                    {observation.label || observation.entity_values[0] || "Documented observation"}
                  </p>
                  <p className="mt-0.5 text-[10px] text-muted">
                    {observation.source_filename} · {observation.source_locator}
                  </p>
                </button>
              ))}
            </CardBody>
          </Card>

          {selected ? (
            <Card>
              <CardHeader
                title="Observation detail"
                subtitle={`${selected.latitude.toFixed(5)}, ${selected.longitude.toFixed(5)}`}
              />
              <CardBody className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-line bg-surface-2/60 p-2.5">
                    <p className="text-[10px] uppercase tracking-wider text-muted">Time</p>
                    <p className="mt-1 text-[11px] text-primary">
                      {formatDateTime(selected.timestamp_normalized)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-line bg-surface-2/60 p-2.5">
                    <p className="text-[10px] uppercase tracking-wider text-muted">Evidence</p>
                    <p className="mt-1 truncate text-[11px] text-primary">
                      {evidenceById.get(selected.evidence_id)?.original_filename ?? selected.source_filename}
                    </p>
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted">Entities</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {selected.entity_values.length === 0 ? (
                      <span className="text-[11px] text-muted">No linked entities.</span>
                    ) : (
                      selected.entity_values.map((value) => (
                        <Badge key={value} className="max-w-full truncate">
                          {value}
                        </Badge>
                      ))
                    )}
                  </div>
                </div>
                <p className="text-[10px] leading-relaxed text-muted">
                  This plot shows only the recorded coordinate. It does not establish that a person or
                  device was at the location for the whole interval, nor does proximity prove association.
                </p>
                <div className="flex flex-wrap gap-3 text-[10px] font-medium">
                  <Link
                    className="text-accent hover:underline"
                    to={`/cases/${caseId}/timeline?event=${selected.event_id}`}
                  >
                    View timeline event
                  </Link>
                  <Link
                    className="text-accent hover:underline"
                    to={`/cases/${caseId}/evidence?evidenceId=${selected.evidence_id}`}
                  >
                    Open source evidence
                  </Link>
                  <Link
                    className="text-accent hover:underline"
                    to={`/cases/${caseId}/ai?focusType=event&focusId=${selected.event_id}`}
                  >
                    Ask AI about this observation
                  </Link>
                </div>
              </CardBody>
            </Card>
          ) : null}
        </div>
      </div>

      {(data?.relationships ?? []).length > 0 ? (
        <Card>
          <CardHeader
            title="Spatial relationships"
            subtitle="Cross-source proximity generated from documented coordinates and timestamps."
          />
          <CardBody className="grid gap-2 md:grid-cols-2">
            {(data?.relationships ?? []).map((relationship) => (
              <button
                key={relationship.id}
                type="button"
                onClick={() => setRelationshipId(relationship.id)}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  relationshipId === relationship.id
                    ? "border-accent/40 bg-accent/10"
                    : "border-line bg-surface-2/40 hover:border-accent/30"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <Badge>{humanize(relationship.relationship_type)}</Badge>
                  <span className="text-[10px] text-muted">{relationship.support_count} supports</span>
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] text-secondary">{relationship.explanation}</p>
              </button>
            ))}
          </CardBody>
        </Card>
      ) : null}

      {relationshipId && caseId ? (
        <Card>
          <CardBody>
            <RelationshipEvidencePanel
              caseId={caseId}
              relationshipId={relationshipId}
              onClose={() => setRelationshipId(null)}
            />
          </CardBody>
        </Card>
      ) : null}
    </div>
  );
}
