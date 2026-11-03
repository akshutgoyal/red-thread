import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Crosshair, MapPin } from "lucide-react";
import { useEvidence, useSpatial } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { formatDateTime, humanize } from "@/lib/format";
import type { SpatialObservation } from "@/types";

export function SpatialPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const spatialQuery = useSpatial(caseId);
  const evidenceQuery = useEvidence(caseId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("all");
  const [relationshipId, setRelationshipId] = useState<string | null>(null);

  const evidenceById = useMemo(
    () => new Map((evidenceQuery.data ?? []).map((item) => [item.id, item])),
    [evidenceQuery.data],
  );

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (spatialQuery.isLoading) return <LoadingState label="Loading documented locations…" />;
  if (spatialQuery.error)
    return <ErrorState message={spatialQuery.error.message} onRetry={() => spatialQuery.refetch()} />;

  const data = spatialQuery.data;
  const observations = (data?.observations ?? []).filter(
    (item) => typeFilter === "all" || item.event_type === typeFilter,
  );
  const types = Array.from(new Set((data?.observations ?? []).map((item) => item.event_type))).sort();
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
        context remain available in the timeline and evidence records.
      </p>

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
              <SpatialPlot observations={observations} selectedId={selectedId} onSelect={setSelectedId} />
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

function SpatialPlot({
  observations,
  selectedId,
  onSelect,
}: {
  observations: SpatialObservation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const lats = observations.map((item) => item.latitude);
  const lons = observations.map((item) => item.longitude);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const latSpan = maxLat - minLat || 0.01;
  const lonSpan = maxLon - minLon || 0.01;
  const project = (observation: SpatialObservation) => ({
    x: 10 + ((observation.longitude - minLon) / lonSpan) * 80,
    y: 10 + ((maxLat - observation.latitude) / latSpan) * 80,
  });

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-[radial-gradient(circle_at_center,rgba(56,189,248,0.08),transparent_65%)]">
      <svg viewBox="0 0 100 100" className="h-[360px] w-full">
        {Array.from({ length: 9 }).map((_, index) => (
          <g key={index}>
            <line
              x1={10 + index * 10}
              y1={10}
              x2={10 + index * 10}
              y2={90}
              stroke="currentColor"
              strokeWidth={0.15}
              className="text-line"
            />
            <line
              x1={10}
              y1={10 + index * 10}
              x2={90}
              y2={10 + index * 10}
              stroke="currentColor"
              strokeWidth={0.15}
              className="text-line"
            />
          </g>
        ))}
        {observations.map((observation) => {
          const { x, y } = project(observation);
          const selected = selectedId === observation.event_id;
          return (
            <g
              key={observation.event_id}
              onClick={() => onSelect(observation.event_id)}
              className="cursor-pointer"
            >
              <circle
                cx={x}
                cy={y}
                r={selected ? 3.2 : 2.2}
                className={selected ? "fill-accent" : "fill-sky-500/80"}
              />
              <circle cx={x} cy={y} r={5.5} className="fill-transparent stroke-accent/30" strokeWidth={0.4} />
              <text
                x={x + 3.8}
                y={y + 1}
                className="fill-current text-[2.6px] text-primary"
              >
                {observation.label || humanize(observation.event_type)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="absolute bottom-2 left-3 flex items-center gap-1.5 text-[10px] text-muted">
        <Crosshair size={11} />
        Documented points only — not a route reconstruction
      </div>
    </div>
  );
}
