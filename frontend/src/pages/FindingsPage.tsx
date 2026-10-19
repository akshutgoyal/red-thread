import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CheckCircle2,
  ChevronRight,
  ListChecks,
  PlayCircle,
  Search,
  XCircle,
} from "lucide-react";
import { useFindings, useReconcile, useReviewFinding } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input, Label, Select } from "@/components/ui/Field";
import { severityLabel, severityStyle, statusStyle } from "@/lib/severity";
import { humanize } from "@/lib/format";
import type { Finding, FindingStatus } from "@/types";

export function FindingsPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const toast = useToast();
  const findingsQuery = useFindings(caseId);
  const reconcile = useReconcile(caseId ?? "");
  const review = useReviewFinding(caseId ?? "");
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("all");
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<Finding | null>(null);
  const [reviewStatus, setReviewStatus] = useState<FindingStatus>("accepted");
  const [reviewNote, setReviewNote] = useState("");

  const findings = useMemo(() => findingsQuery.data?.items ?? [], [findingsQuery.data]);
  const categories = useMemo(
    () => Array.from(new Set(findings.map((item) => item.category))).sort(),
    [findings],
  );
  const filtered = useMemo(
    () =>
      findings.filter((finding) => {
        const text = `${finding.title} ${finding.explanation} ${finding.detection_method}`.toLowerCase();
        const matchesSearch = !search || text.includes(search.toLowerCase());
        const matchesSeverity = severity === "all" || finding.severity === severity;
        const matchesStatus = status === "all" || finding.status === status;
        const matchesCategory = category === "all" || finding.category === category;
        return matchesSearch && matchesSeverity && matchesStatus && matchesCategory;
      }),
    [findings, search, severity, status, category],
  );

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (findingsQuery.isLoading) return <LoadingState label="Loading findings…" />;
  if (findingsQuery.error)
    return <ErrorState message={findingsQuery.error.message} onRetry={() => findingsQuery.refetch()} />;

  function openFinding(finding: Finding) {
    setSelected(finding);
    setReviewStatus(
      finding.status === "open" || finding.status === "needs_review"
        ? "accepted"
        : (finding.status as FindingStatus),
    );
    setReviewNote(finding.reviewer_note ?? "");
  }

  function submitReview() {
    if (!selected) return;
    review.mutate(
      {
        findingId: selected.id,
        payload: { status: reviewStatus, reviewer_note: reviewNote },
      },
      {
        onSuccess: (updated) => {
          setSelected(updated);
          toast.push("success", "Finding reviewed", `Status set to ${humanize(updated.status)}.`);
        },
        onError: (error) => toast.push("error", "Review failed", error.message),
      },
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Findings"
        title="Deterministic findings and correlations"
        description="Every finding separates observation from interpretation. Review, annotate, and decide whether it is supported by the evidence."
        actions={
          <Button
            variant="primary"
            icon={<PlayCircle size={15} />}
            onClick={() =>
              reconcile.mutate(undefined, {
                onSuccess: (result) =>
                  toast.push(
                    "success",
                    "Checks complete",
                    `${result.findings_created} finding(s) produced.`,
                  ),
                onError: (error) => toast.push("error", "Checks failed", error.message),
              })
            }
            loading={reconcile.isPending}
          >
            Run deterministic checks
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total findings" value={findings.length} tone="cyan" />
        <Metric
          label="Awaiting review"
          value={findings.filter((item) => item.status === "open" || item.status === "needs_review").length}
          tone="amber"
        />
        <Metric
          label="High / critical"
          value={findings.filter((item) => item.severity === "high" || item.severity === "critical").length}
          tone="rose"
        />
        <Metric
          label="Accepted"
          value={findings.filter((item) => item.status === "accepted").length}
          tone="emerald"
        />
      </div>

      <Card className="mt-5">
        <CardHeader
          title="Findings register"
          subtitle={`${filtered.length} of ${findings.length} findings`}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-2.5 text-muted" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search findings"
                  className="w-52 pl-8 text-xs"
                />
              </div>
              <Select
                value={severity}
                onChange={(event) => setSeverity(event.target.value)}
                className="w-36 text-xs"
              >
                <option value="all">All severity</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </Select>
              <Select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="w-44 text-xs"
              >
                <option value="all">All statuses</option>
                <option value="open">Open</option>
                <option value="needs_review">Needs review</option>
                <option value="accepted">Accepted</option>
                <option value="rejected">Rejected</option>
                <option value="needs_more_evidence">Needs more evidence</option>
              </Select>
              <Select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="w-40 text-xs"
              >
                <option value="all">All categories</option>
                {categories.map((item) => (
                  <option key={item} value={item}>
                    {humanize(item)}
                  </option>
                ))}
              </Select>
            </div>
          }
        />
        {filtered.length === 0 ? (
          <CardBody>
            <EmptyState
              title={findings.length === 0 ? "No findings yet" : "No matching findings"}
              description={
                findings.length === 0
                  ? "Parse evidence and run deterministic checks to produce reviewable findings."
                  : "Adjust the filters or search query."
              }
              icon={ListChecks}
            />
          </CardBody>
        ) : (
          <CardBody className="grid gap-3 lg:grid-cols-2">
            {filtered.map((finding) => (
              <button
                key={finding.id}
                type="button"
                onClick={() => openFinding(finding)}
                className="rounded-xl border border-line bg-surface-2/40 p-4 text-left transition hover:border-accent/30 hover:bg-surface/50"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-medium leading-snug text-primary">
                      {finding.title}
                    </p>
                    <p className="mt-1 text-[10px] uppercase tracking-wider text-muted">
                      {humanize(finding.category)} · {humanize(finding.detection_method)} ·{" "}
                      {humanize(finding.confidence)} confidence
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge className={severityStyle(finding.severity)}>
                      {severityLabel(finding.severity)}
                    </Badge>
                    <Badge className={statusStyle(finding.status)}>
                      {humanize(finding.status)}
                    </Badge>
                  </div>
                </div>
                <p className="mt-3 line-clamp-3 text-xs leading-relaxed text-muted">
                  {finding.explanation}
                </p>
                <div className="mt-3 flex items-center justify-between text-[10px] text-muted">
                  <span>
                    {finding.evidence_links.length} evidence link(s) ·{" "}
                    {finding.evidence_links.filter((link) => link.event_id).length} event(s)
                  </span>
                  <ChevronRight size={14} className="text-muted" />
                </div>
              </button>
            ))}
          </CardBody>
        )}
      </Card>

      <p className="mt-4 text-[10px] leading-relaxed text-muted">
        A suspicious pattern, discrepancy or AI explanation does not by itself prove criminal
        activity. Findings remain hypotheses until an authorized investigator validates them
        against the source evidence.
      </p>

      <Drawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.title ?? "Finding"}
        subtitle={
          selected
            ? `${severityLabel(selected.severity)} · ${humanize(selected.detection_method)}`
            : undefined
        }
        wide
      >
        {selected ? (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2">
              <Badge className={severityStyle(selected.severity)}>
                {severityLabel(selected.severity)}
              </Badge>
              <Badge className={statusStyle(selected.status)}>{humanize(selected.status)}</Badge>
              <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                {humanize(selected.category)}
              </Badge>
              <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                {humanize(selected.confidence)} confidence
              </Badge>
            </div>

            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Explanation
              </p>
              <p className="whitespace-pre-line text-sm leading-relaxed text-secondary">
                {selected.explanation}
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400/80">
                  Limitations
                </p>
                <p className="mt-1 text-xs leading-relaxed text-amber-800/80 dark:text-amber-100/70">
                  {selected.limitations || "No limitations recorded."}
                </p>
              </div>
              <div className="rounded-lg border border-line bg-surface-2/40 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                  Alternative explanations
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {selected.alternative_explanations || "None recorded."}
                </p>
              </div>
            </div>

            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Supporting records
              </p>
              <div className="space-y-2">
                {selected.evidence_links.map((link) => (
                  <div
                    key={`${link.evidence_id}-${link.event_id}-${link.role}`}
                    className="rounded-lg border border-line bg-surface-2/40 px-3 py-2 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-[10px] text-accent/80">
                        {link.evidence_id}
                      </span>
                      <Badge className="border-line-strong bg-surface-2/70 text-muted">
                        {humanize(link.role)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-[10px] text-muted">
                      {link.event_id ? `Event ${link.event_id}` : "Evidence-level link"}
                      {link.source_locator ? ` · ${link.source_locator}` : ""}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-line bg-surface-2/40 p-4">
              <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-muted">
                Investigator review
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="review-status">Decision</Label>
                  <Select
                    id="review-status"
                    value={reviewStatus}
                    onChange={(event) => setReviewStatus(event.target.value as FindingStatus)}
                  >
                    <option value="accepted">Accept finding</option>
                    <option value="rejected">Reject finding</option>
                    <option value="needs_review">Keep for review</option>
                    <option value="needs_more_evidence">Needs more evidence</option>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="review-note">Reviewer note</Label>
                  <Input
                    id="review-note"
                    value={reviewNote}
                    onChange={(event) => setReviewNote(event.target.value)}
                    placeholder="Basis for the decision"
                  />
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  icon={<CheckCircle2 size={14} />}
                  onClick={submitReview}
                  loading={review.isPending}
                >
                  Save review
                </Button>
                <Button
                  variant="ghost"
                  icon={<XCircle size={14} />}
                  onClick={() => {
                    setReviewStatus("rejected");
                    setReviewNote((current) => current || "Rejected after investigator review.");
                  }}
                >
                  Mark rejected
                </Button>
              </div>
              {selected.reviewed_at ? (
                <p className="mt-3 text-[10px] text-muted">
                  Last reviewed {selected.reviewed_at}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "cyan" | "amber" | "rose" | "emerald";
}) {
  const tones = {
    cyan: "border-accent/20 bg-accent/5 text-accent",
    amber: "border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 text-amber-700 dark:text-amber-200",
    rose: "border-rose-200 dark:border-rose-500/20 bg-rose-50/80 dark:bg-rose-500/5 text-rose-700 dark:text-rose-200",
    emerald: "border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/80 dark:bg-emerald-500/5 text-emerald-700 dark:text-emerald-200",
  };
  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <p className="text-[10px] uppercase tracking-wider opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
