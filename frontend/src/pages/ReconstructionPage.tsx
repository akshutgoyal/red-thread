import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowRight, Bot, GitBranch, Layers, MessageSquarePlus } from "lucide-react";
import { useAnnotations, useCreateAnnotation, useReconstruction } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader, CollapsibleCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { RelationshipEvidencePanel } from "@/components/relationship/RelationshipEvidencePanel";
import { formatDateTime, humanize } from "@/lib/format";

export function ReconstructionPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const reconstructionQuery = useReconstruction(caseId);
  const annotationsQuery = useAnnotations(caseId);
  const createAnnotation = useCreateAnnotation(caseId ?? "");
  const toast = useToast();
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(null);
  const [note, setNote] = useState("");

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
  const reviewQueue = data.relationships.filter((relationship) =>
    ["unreviewed", "needs_review", "needs_more_evidence"].includes(relationship.review_status),
  );

  function addAnnotation() {
    const trimmed = note.trim();
    if (!caseId || !trimmed) return;
    createAnnotation.mutate(
      {
        target_type: "case",
        target_id: caseId,
        author: "Investigator",
        note: trimmed,
      },
      {
        onSuccess: () => {
          setNote("");
          toast.push("success", "Annotation added");
        },
        onError: (error) =>
          toast.push("error", "Could not add annotation", error.message),
      },
    );
  }

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

          <CollapsibleCard
            title="Recent event sequence"
            subtitle="Normalized timestamps; original source locators are retained in the timeline and evidence records."
            summary={`${data.recent_events.length} events`}
          >
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
          </CollapsibleCard>
        </div>

        <div className="space-y-5">
          <CollapsibleCard
            title="Review queue"
            subtitle="Relationships that still need an investigator decision."
            summary={`${reviewQueue.length} waiting`}
          >
            <CardBody className="space-y-2">
              {reviewQueue.length === 0 ? (
                <p className="text-xs text-muted">No relationships are waiting for review.</p>
              ) : (
                reviewQueue.slice(0, 12).map((relationship) => (
                  <button
                    key={relationship.id}
                    type="button"
                    onClick={() => setSelectedRelationshipId(relationship.id)}
                    className="w-full rounded-lg border border-line bg-surface-2/40 px-3 py-2 text-left transition-colors hover:border-accent/30"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-[11px] font-medium text-primary">
                        {humanize(relationship.relationship_type)}
                      </span>
                      <Badge>{humanize(relationship.review_status)}</Badge>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[10px] text-secondary">
                      {relationship.explanation}
                    </p>
                  </button>
                ))
              )}
            </CardBody>
          </CollapsibleCard>

          <CollapsibleCard
            title="Unresolved questions"
            subtitle="What still needs investigator attention."
            summary={`${data.unresolved.length} open`}
          >
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
          </CollapsibleCard>

          <CollapsibleCard
            title="Conflicting or high-severity findings"
            subtitle="Existing findings remain available in the Findings workspace."
            summary={`${data.conflicts.length} highlighted`}
          >
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
          </CollapsibleCard>

          <CollapsibleCard
            title="Spatial observations"
            subtitle="Documented coordinates only."
            summary={`${data.spatial_observations.length} plotted`}
          >
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
          </CollapsibleCard>

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

      <Card className="mt-5">
        <CardHeader
          title="Investigator annotations"
          subtitle="Human notes are stored separately from deterministic evidence and audit-logged."
          action={<Badge>{annotationsQuery.data?.length ?? 0}</Badge>}
        />
        <CardBody className="space-y-4">
          {annotationsQuery.isLoading ? (
            <LoadingState label="Loading annotations…" />
          ) : annotationsQuery.data?.length ? (
            <div className="space-y-2">
              {annotationsQuery.data.map((annotation) => (
                <div
                  key={annotation.id}
                  className="rounded-lg border border-line bg-surface-2/40 p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge>{humanize(annotation.target_type)}</Badge>
                      <span className="text-[10px] text-muted">
                        {annotation.author || "Investigator"}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted">
                      {formatDateTime(annotation.created_at)}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-line text-[11px] leading-relaxed text-secondary">
                    {annotation.note}
                  </p>
                  <p className="mt-1 font-mono text-[9px] text-muted">
                    target: {annotation.target_type}:{annotation.target_id}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted">No investigator annotations yet.</p>
          )}

          <div className="rounded-xl border border-line bg-surface-2/40 p-3">
            <Textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Add a case note, follow-up task or review caveat…"
              rows={3}
              className="text-xs"
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <p className="text-[10px] text-muted">
                Annotations are attributable and included in the audit trail and reports.
              </p>
              <Button
                size="sm"
                variant="primary"
                icon={<MessageSquarePlus size={13} />}
                loading={createAnnotation.isPending}
                disabled={!note.trim()}
                onClick={addAnnotation}
              >
                Add annotation
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
