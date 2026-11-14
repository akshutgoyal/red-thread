import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Check, FileSearch, ShieldAlert, X } from "lucide-react";
import { useEvidence, useRelationship, useReviewRelationship } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ClassificationBadge } from "@/components/ClassificationBadge";
import { Textarea } from "@/components/ui/Field";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { formatDateTime, humanize } from "@/lib/format";

export function RelationshipEvidencePanel({
  caseId,
  relationshipId,
  onClose,
}: {
  caseId: string;
  relationshipId: string;
  onClose?: () => void;
}) {
  const toast = useToast();
  const relationshipQuery = useRelationship(caseId, relationshipId);
  const evidenceQuery = useEvidence(caseId);
  const review = useReviewRelationship(caseId);
  const [note, setNote] = useState("");

  const evidenceNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const item of evidenceQuery.data ?? []) {
      names.set(item.id, item.original_filename);
    }
    return names;
  }, [evidenceQuery.data]);

  if (relationshipQuery.isLoading) return <LoadingState label="Loading relationship evidence…" />;
  if (relationshipQuery.error) {
    return <ErrorState message={relationshipQuery.error.message} onRetry={() => relationshipQuery.refetch()} />;
  }
  if (!relationshipQuery.data) {
    return <EmptyState title="Relationship not found" icon={FileSearch} />;
  }

  const relationship = relationshipQuery.data;
  const supports = relationship.supports ?? [];
  const reviews = relationship.reviews ?? [];

  function submit(decision: string) {
    review.mutate(
      {
        relationshipId,
        payload: {
          decision,
          reviewer: "Investigator",
          note: note.trim(),
        },
      },
      {
        onSuccess: () => {
          setNote("");
          toast.push("success", "Relationship review saved");
        },
        onError: (error) => toast.push("error", "Could not save review", error.message),
      },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
            Provenance relationship
          </p>
          <h3 className="mt-1 text-sm font-semibold text-primary">
            {humanize(relationship.relationship_type)}
          </h3>
          <p className="mt-1 text-[11px] text-muted">
            {relationship.source_type}:{relationship.source_id} →{" "}
            {relationship.target_type}:{relationship.target_id}
          </p>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted transition-colors hover:bg-surface-2 hover:text-primary"
            aria-label="Close relationship panel"
          >
            <X size={15} />
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-1.5">
        <ClassificationBadge classification={relationship.classification} />
        <Badge className="border-line bg-surface-2 text-secondary">
          confidence: {relationship.confidence}
        </Badge>
        <Badge className="border-line bg-surface-2 text-secondary">
          {humanize(relationship.review_status)}
        </Badge>
        <Badge className="border-line bg-surface-2 text-secondary">
          {relationship.support_count} supports
        </Badge>
      </div>

      <div className="rounded-xl border border-line bg-surface-2/40 p-3">
        <p className="text-[11px] leading-relaxed text-secondary">{relationship.explanation}</p>
        <p className="mt-2 font-mono text-[10px] text-muted">
          rule: {relationship.correlation_rule}
        </p>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
          Supporting records
        </p>
        {supports.length === 0 ? (
          <p className="text-xs text-muted">No support records are attached to this relationship.</p>
        ) : (
          <div className="max-h-64 space-y-2 overflow-auto pr-1">
            {supports.map((support) => (
              <div
                key={support.id}
                className="rounded-lg border border-line bg-surface p-2.5 text-[11px]"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-primary">
                    {support.evidence_id
                      ? evidenceNames.get(support.evidence_id) ?? support.evidence_id
                      : "Evidence reference"}
                  </span>
                  <span className="font-mono text-[10px] text-muted">
                    {support.source_locator || "locator unavailable"}
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-muted">
                  {humanize(support.support_kind)}
                  {support.event_id ? ` · event ${support.event_id.slice(0, 12)}…` : ""}
                </p>
                {support.snippet ? (
                  <p className="mt-1 line-clamp-4 text-[10px] leading-relaxed text-secondary">
                    {support.snippet}
                  </p>
                ) : null}
                <div className="mt-1.5 flex flex-wrap gap-3 text-[10px] font-medium">
                  {support.evidence_id ? (
                    <Link
                      className="text-accent hover:underline"
                      to={`/cases/${caseId}/evidence?evidenceId=${support.evidence_id}`}
                    >
                      Open evidence
                    </Link>
                  ) : null}
                  {support.event_id ? (
                    <Link
                      className="text-accent hover:underline"
                      to={`/cases/${caseId}/reconstruction?tab=timeline&event=${support.event_id}`}
                    >
                      View event
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Link
        to={`/cases/${caseId}/ai?focusType=relationship&focusId=${relationshipId}`}
        className="inline-flex"
      >
        <Button size="sm" variant="secondary">
          Ask AI about this relationship
        </Button>
      </Link>

      <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-[10px] leading-relaxed text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80">
        <ShieldAlert size={12} className="mr-1 inline" />
        Exact identifiers, temporal proximity and spatial proximity are investigative leads. They
        do not by themselves prove identity, causation or criminality.
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
          Investigator review
        </p>
        <Textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Optional review note"
          rows={2}
          className="text-xs"
        />
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            icon={<Check size={13} />}
            loading={review.isPending}
            onClick={() => submit("accepted")}
          >
            Accept
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<X size={13} />}
            loading={review.isPending}
            onClick={() => submit("rejected")}
          >
            Reject
          </Button>
          <Button
            size="sm"
            variant="secondary"
            loading={review.isPending}
            onClick={() => submit("needs_more_evidence")}
          >
            Needs evidence
          </Button>
          <Button
            size="sm"
            variant="ghost"
            loading={review.isPending}
            onClick={() => submit("needs_review")}
          >
            Needs review
          </Button>
        </div>
        {relationship.review_note ? (
          <p className="mt-2 text-[10px] text-muted">Latest note: {relationship.review_note}</p>
        ) : null}
      </div>

      {reviews.length > 0 ? (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
            Review history
          </p>
          <div className="space-y-1">
            {reviews.map((item) => (
              <div
                key={item.id}
                className="flex items-start justify-between gap-2 rounded-md border border-line px-2 py-1.5 text-[10px]"
              >
                <span className="text-secondary">
                  {humanize(item.decision)} · {item.reviewer || "Investigator"}
                  {item.note ? ` — ${item.note}` : ""}
                </span>
                <span className="shrink-0 text-muted">{formatDateTime(item.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
