import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowRight, Bot, GitBranch, Layers } from "lucide-react";
import { useReconstruction } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { formatDateTime, humanize } from "@/lib/format";

export function ReconstructionPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const reconstructionQuery = useReconstruction(caseId);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(null);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (reconstructionQuery.isLoading) return <LoadingState label="Building reconstruction…" />;
  if (reconstructionQuery.error)
    return (
      <ErrorState
        message={reconstructionQuery.error.message}
        onRetry={() => reconstructionQuery.refetch()}
      />
    );

  const data = reconstructionQuery.data;
  if (!data) return <EmptyState title="No reconstruction available" description="Parse evidence first." />;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reconstruction workspace"
        description="A deterministic, source-linked investigation summary. Correlations are investigative leads, not conclusions."
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/cases/${caseId}/graph`}>
              <Button variant="secondary" icon={<GitBranch size={14} />}>
                Open graph
              </Button>
            </Link>
            <Link to={`/cases/${caseId}/ai`}>
              <Button variant="secondary" icon={<Bot size={14} />}>
                Ask AI
              </Button>
            </Link>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Evidence", data.counts.evidence],
          ["Events", data.counts.events],
          ["Entities", data.counts.entities],
          ["Relationships", data.counts.relationships],
          ["Findings", data.counts.findings],
          ["Open findings", data.counts.open_findings],
          ["Unreviewed relationships", data.counts.unreviewed_relationships],
          ["Spatial observations", data.counts.spatial_observations],
        ].map(([label, value]) => (
          <Card key={label}>
            <CardBody className="p-4">
              <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
              <p className="mt-1 text-xl font-semibold text-primary">{value ?? 0}</p>
            </CardBody>
          </Card>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div className="space-y-5">
          <Card>
            <CardHeader
              title="Relationship summary"
              subtitle="Exact matches, co-mentions, temporal associations and spatial proximity."
              action={<Badge>{data.relationships.length} shown</Badge>}
            />
            <CardBody className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.relationship_types).map(([type, count]) => (
                  <Badge key={type}>
                    {humanize(type)} · {count}
                  </Badge>
                ))}
              </div>
              {data.relationships.length === 0 ? (
                <p className="text-xs text-muted">No relationships generated yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {data.relationships.map((relationship) => (
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
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-xs font-medium text-primary">
                          {humanize(relationship.relationship_type)}
                        </span>
                        <div className="flex gap-1">
                          <Badge>{relationship.classification}</Badge>
                          <Badge>{relationship.review_status}</Badge>
                        </div>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-secondary">
                        {relationship.explanation}
                      </p>
                    </button>
                  ))}
                </div>
              )}
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
              title="Recent event sequence"
              subtitle="Normalized timestamps; original source locators are retained in the timeline and evidence records."
            />
            <CardBody className="space-y-1.5">
              {data.recent_events.slice(0, 20).map((event) => (
                <div
                  key={event.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface-2/40 px-3 py-2"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge>{humanize(event.event_type)}</Badge>
                      <span className="text-[10px] text-muted">{event.source_filename}</span>
                    </div>
                    <p className="mt-1 truncate text-[11px] text-primary">
                      {event.source_snippet || event.source_locator}
                    </p>
                  </div>
                  <span className="text-[10px] text-muted">
                    {formatDateTime(event.timestamp_normalized)}
                  </span>
                </div>
              ))}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader title="Unresolved questions" subtitle="What still needs investigator attention." />
            <CardBody className="space-y-2">
              {data.unresolved.length === 0 ? (
                <p className="text-xs text-muted">No outstanding automated flags.</p>
              ) : (
                data.unresolved.map((item) => (
                  <div key={item} className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[11px] text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                    <span>{item}</span>
                  </div>
                ))
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Conflicting or high-severity findings"
              subtitle="Existing findings remain available in the Findings workspace."
            />
            <CardBody className="space-y-2">
              {data.conflicts.length === 0 ? (
                <p className="text-xs text-muted">No high-severity or conflict findings in this case.</p>
              ) : (
                data.conflicts.slice(0, 10).map((finding) => (
                  <Link
                    key={finding.id}
                    to={`/cases/${caseId}/findings`}
                    className="block rounded-lg border border-line bg-surface-2/40 p-2.5 transition-colors hover:border-accent/30"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Badge>{finding.severity}</Badge>
                      <span className="text-[10px] text-muted">{finding.status}</span>
                    </div>
                    <p className="mt-1 text-[11px] font-medium text-primary">{finding.title}</p>
                  </Link>
                ))
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Spatial observations" subtitle="Documented coordinates only." />
            <CardBody className="space-y-2">
              {data.spatial_observations.length === 0 ? (
                <p className="text-xs text-muted">No documented coordinates in this case.</p>
              ) : (
                <>
                  {data.spatial_observations.slice(0, 6).map((observation) => (
                    <div key={observation.event_id} className="rounded-lg border border-line bg-surface-2/40 p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <Badge>{humanize(observation.event_type)}</Badge>
                        <span className="text-[10px] text-muted">
                          {observation.latitude.toFixed(4)}, {observation.longitude.toFixed(4)}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-primary">{observation.label || observation.source_filename}</p>
                    </div>
                  ))}
                  <Link to={`/cases/${caseId}/spatial`} className="inline-flex items-center gap-1 text-[11px] font-medium text-accent">
                    Open spatial reconstruction <ArrowRight size={12} />
                  </Link>
                </>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Limitations" subtitle="Generated by the deterministic reconstruction service." />
            <CardBody className="space-y-1.5">
              {data.limitations.map((limitation) => (
                <p key={limitation} className="flex gap-2 text-[11px] text-secondary">
                  <Layers size={12} className="mt-0.5 shrink-0 text-muted" />
                  {limitation}
                </p>
              ))}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
