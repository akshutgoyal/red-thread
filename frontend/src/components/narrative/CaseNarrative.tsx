import { Link } from "react-router-dom";
import { ArrowRight, BookOpen } from "lucide-react";
import type { NarrativeResponse } from "@/types";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";
import { Skeleton } from "@/components/ui/Primitives";

export function CaseNarrative({
  caseId,
  narrative,
  loading,
  limit,
}: {
  caseId: string;
  narrative?: NarrativeResponse;
  loading?: boolean;
  limit?: number;
}) {
  const items = limit ? (narrative?.items ?? []).slice(0, limit) : (narrative?.items ?? []);
  const truncated = limit ? (narrative?.items.length ?? 0) > limit : false;

  return (
    <Card>
      <CardHeader
        title="What happened in this case?"
        subtitle="Chronological statements extracted from stored records. Open any statement to see the evidence behind it."
        action={
          truncated ? (
            <Link
              to={`/cases/${caseId}/reconstruction`}
              className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-strong"
            >
              Full narrative <ArrowRight size={12} />
            </Link>
          ) : undefined
        }
      />
      <CardBody className="space-y-2">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title="Nothing to summarise yet"
            description="Statements appear once evidence has been parsed into events."
            icon={BookOpen}
          />
        ) : (
          <ol className="space-y-1.5">
            {items.map((item) => (
              <li key={`${item.kind}-${item.index}`}>
                <Link
                  to={item.href}
                  className="flex gap-2.5 rounded-lg border border-line bg-surface-2/40 px-3 py-2 text-xs leading-relaxed text-secondary transition hover:border-accent/40 hover:text-primary"
                >
                  <span className="mt-0.5 font-mono text-[10px] text-muted">
                    {item.index}.
                  </span>
                  <span>
                    {item.statement}
                    <span className="ml-1.5 text-[10px] uppercase tracking-wider text-accent">
                      {item.kind}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        )}
        {narrative ? (
          <p className="pt-1 text-[10px] leading-relaxed text-muted">
            {narrative.disclaimer}
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}
