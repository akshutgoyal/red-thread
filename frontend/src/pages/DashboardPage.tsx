import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ChevronDown,
  FileSearch,
  FolderOpen,
  Link2,
  ListChecks,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useCaseContext } from "@/context/CaseContext";
import { useAuth } from "@/context/AuthContext";
import {
  useCase,
  useEvidence,
  useEvents,
  useFindings,
  useGuidance,
  useNarrative,
} from "@/hooks/useApi";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { InvestigationStepper } from "@/components/ui/Stepper";
import { Skeleton } from "@/components/ui/Primitives";
import {
  AttentionList,
  NextActionPanel,
  useSessionDismiss,
} from "@/components/guidance/GuidancePanels";
import { CaseNarrative } from "@/components/narrative/CaseNarrative";
import { severityStyle, severityLabel, SEVERITY_ORDER } from "@/lib/severity";
import { formatBytes, humanize, shortHash } from "@/lib/format";
import type { Finding } from "@/types";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--chart-rose)",
  high: "var(--chart-orange)",
  medium: "var(--chart-amber)",
  low: "var(--chart-sky)",
  info: "var(--chart-slate)",
};

export function DashboardPage() {
  const {
    cases,
    selectedCaseId,
    selectedCase,
    isLoading: casesLoading,
    error: casesError,
  } = useCaseContext();
  const { loginDemo } = useAuth();
  const navigate = useNavigate();
  const [showStats, setShowStats] = useState(false);
  const { dismissed, dismiss } = useSessionDismiss(
    `red-thread.next-action.dismissed.${selectedCaseId ?? "none"}`,
  );

  const caseQuery = useCase(selectedCaseId ?? undefined);
  const guidanceQuery = useGuidance(selectedCaseId ?? undefined);
  const evidenceQuery = useEvidence(selectedCaseId ?? undefined);
  const eventsQuery = useEvents(selectedCaseId ?? undefined, { limit: 500 });
  const findingsQuery = useFindings(selectedCaseId ?? undefined);
  const narrativeQuery = useNarrative(selectedCaseId ?? undefined);

  const evidence = useMemo(() => evidenceQuery.data ?? [], [evidenceQuery.data]);
  const events = useMemo(() => eventsQuery.data?.items ?? [], [eventsQuery.data]);
  const findings = useMemo(() => findingsQuery.data?.items ?? [], [findingsQuery.data]);
  const summary = caseQuery.data ?? selectedCase;

  const findingsBySeverity = useMemo(
    () =>
      SEVERITY_ORDER.map((severity) => ({
        name: severityLabel(severity),
        key: severity,
        count: findings.filter((finding) => finding.severity === severity).length,
      })).filter((item) => item.count > 0),
    [findings],
  );

  const keyFindings = useMemo(
    () =>
      [...findings]
        .sort((left, right) => {
          const severityDelta =
            SEVERITY_ORDER.indexOf(left.severity) - SEVERITY_ORDER.indexOf(right.severity);
          if (severityDelta !== 0) return severityDelta;
          return right.created_at.localeCompare(left.created_at);
        })
        .slice(0, 3),
    [findings],
  );

  const eventsByType = useMemo(() => {
    const counts = new Map<string, number>();
    for (const event of events) {
      counts.set(event.event_type, (counts.get(event.event_type) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name: humanize(name), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [events]);

  if (casesLoading) return <LoadingState label="Loading workspace…" />;
  if (casesError) return <ErrorState message={casesError.message} />;
  if (cases.length === 0) {
    return (
      <div>
        <PageHeader
          eyebrow="Workspace"
          title="Welcome to Red Thread"
          description="Create your first investigation case, then upload evidence to begin a traceable forensic workflow."
        />
        <EmptyState
          title="No investigation cases yet"
          description="A case groups evidence, events, findings and reports. Create one to begin."
          icon={FolderOpen}
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Link to="/cases">
                <Button variant="primary" icon={<FolderOpen size={15} />}>
                  Create a case
                </Button>
              </Link>
              <Button
                variant="secondary"
                icon={<Sparkles size={15} />}
                onClick={() => void loginDemo()}
              >
                Explore demo
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  if (!selectedCaseId) {
    return <ErrorState title="No active case" message="Select or create a case to continue." />;
  }

  const guidance = guidanceQuery.data;
  const progress = guidance
    ? {
        completed: guidance.stages.filter((stage) => stage.status === "complete").length,
        total: guidance.stages.length,
      }
    : { completed: 0, total: 9 };

  return (
    <div>
      <PageHeader
        eyebrow="Investigation overview"
        title={summary?.title ?? "Dashboard"}
        description="Follow the steps below. Every recommendation is derived from this case's stored evidence, events and findings."
        actions={
          <>
            <Link to={`/cases/${selectedCaseId}/evidence/intake`}>
              <Button variant="primary" icon={<FileSearch size={15} />}>
                Upload evidence
              </Button>
            </Link>
            <Link to={`/cases/${selectedCaseId}/findings`}>
              <Button variant="secondary" icon={<ListChecks size={15} />}>
                Review findings
              </Button>
            </Link>
          </>
        }
      />

      {guidanceQuery.isLoading ? (
        <Skeleton className="mb-4 h-24 w-full" />
      ) : guidance ? (
        <>
          {dismissed ? null : (
            <div className="mb-4">
              <NextActionPanel guidance={guidance} onDismiss={dismiss} />
            </div>
          )}
          <Card className="mb-4">
            <CardHeader
              title="Investigation progress"
              subtitle={`${progress.completed} of ${progress.total} stages complete`}
            />
            <CardBody>
              <InvestigationStepper stages={guidance.stages} compact />
            </CardBody>
          </Card>
        </>
      ) : null}

      <div className="mb-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Evidence files"
          value={evidence.length}
          hint={
            guidance
              ? `${guidance.summary.parsed} processed · ${guidance.summary.needs_attention} need attention`
              : undefined
          }
          icon={FileSearch}
          tone="emerald"
        />
        <StatCard
          label="Extracted events"
          value={guidance?.summary.events ?? events.length}
          hint={`${guidance?.summary.entities ?? 0} identified entities`}
          icon={Activity}
          tone="violet"
        />
        <StatCard
          label="Findings to review"
          value={guidance?.summary.open_findings ?? 0}
          hint={`${findings.length} findings recorded in total`}
          icon={ShieldAlert}
          tone="rose"
        />
        <StatCard
          label="Relationships"
          value={guidance?.summary.unreviewed_relationships ?? 0}
          hint="Unreviewed correlation candidates"
          icon={Link2}
          tone="cyan"
        />
      </div>

      {guidance ? (
        <div className="mb-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader title="Key findings" subtitle="Plain-language summary of the highest-priority items" />
            <CardBody className="space-y-3">
              {keyFindings.length === 0 ? (
                <EmptyState
                  title="No findings yet"
                  description="Findings appear once evidence is parsed and deterministic checks run."
                />
              ) : (
                keyFindings.map((finding) => (
                  <FindingCard
                    key={finding.id}
                    finding={finding}
                    caseId={selectedCaseId}
                    onOpenEvidence={() => navigate(`/cases/${selectedCaseId}/evidence`)}
                  />
                ))
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Needs attention"
              subtitle="Derived from processing state, integrity checks and review backlogs"
            />
            <CardBody>
              <AttentionList
                items={guidance.attention}
                onSelect={(item) => navigate(item.href)}
              />
            </CardBody>
          </Card>
        </div>
      ) : null}

      <div className="mb-4">
        <CaseNarrative
          caseId={selectedCaseId}
          narrative={narrativeQuery.data}
          loading={narrativeQuery.isLoading}
          limit={3}
        />
      </div>

      <button
        type="button"
        onClick={() => setShowStats((current) => !current)}
        className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:text-accent-strong"
        aria-expanded={showStats}
      >
        <ChevronDown
          size={14}
          className={`transition ${showStats ? "rotate-180" : ""}`}
        />
        {showStats ? "Hide statistics" : "Show statistics"}
      </button>

      {showStats ? (
        <>
          <div className="grid gap-5 xl:grid-cols-3">
            <Card className="min-w-0 xl:col-span-2">
              <CardHeader
                title="Events by type"
                subtitle="Extracted canonical events in the current case"
              />
              <CardBody className="h-72">
                {eventsByType.length === 0 ? (
                  <EmptyState
                    title="No events yet"
                    description="Upload and parse evidence first."
                  />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={eventsByType}
                      margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: "var(--chart-axis)", fontSize: 10 }}
                        interval={0}
                        angle={-18}
                        textAnchor="end"
                        height={55}
                      />
                      <YAxis
                        tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
                        allowDecimals={false}
                      />
                      <ChartTooltip
                        contentStyle={{
                          background: "var(--chart-tooltip-bg)",
                          border: "1px solid var(--chart-tooltip-border)",
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                      />
                      <Bar
                        dataKey="count"
                        fill="var(--chart-cyan)"
                        radius={[4, 4, 0, 0]}
                        isAnimationActive={false}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardBody>
            </Card>

            <Card className="min-w-0">
              <CardHeader
                title="Findings by severity"
                subtitle="Rule-based and reconciliation output"
              />
              <CardBody className="flex h-72 flex-col">
                {findingsBySeverity.length === 0 ? (
                  <EmptyState
                    title="No findings"
                    description="Deterministic checks have not produced findings yet."
                  />
                ) : (
                  <>
                    <div className="min-h-0 flex-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={findingsBySeverity}
                            dataKey="count"
                            nameKey="name"
                            innerRadius={55}
                            outerRadius={88}
                            paddingAngle={3}
                            isAnimationActive={false}
                          >
                            {findingsBySeverity.map((entry) => (
                              <Cell
                                key={entry.key}
                                fill={SEVERITY_COLORS[entry.key] ?? "#94a3b8"}
                              />
                            ))}
                          </Pie>
                          <ChartTooltip
                            contentStyle={{
                              background: "var(--chart-tooltip-bg)",
                              border: "1px solid var(--chart-tooltip-border)",
                              borderRadius: 8,
                              fontSize: 12,
                            }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1.5">
                      {findingsBySeverity.map((entry) => (
                        <span
                          key={entry.key}
                          className="inline-flex items-center gap-1.5 text-[10px] text-muted"
                        >
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ background: SEVERITY_COLORS[entry.key] }}
                          />
                          {entry.name}
                          <span className="font-mono text-primary">{entry.count}</span>
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </CardBody>
            </Card>
          </div>

          <Card className="mt-5 min-w-0">
            <CardHeader
              title="Recent evidence"
              subtitle="Hash and processing status are stored with every upload"
              action={
                <Link
                  to={`/cases/${selectedCaseId}/evidence`}
                  className="text-xs text-accent hover:text-accent-strong"
                >
                  Open vault
                </Link>
              }
            />
            <CardBody className="space-y-2">
              {evidence.length === 0 ? (
                <EmptyState
                  title="No evidence uploaded"
                  description="Upload supported files to begin extraction."
                  action={
                    <Link to={`/cases/${selectedCaseId}/evidence/intake`}>
                      <Button size="sm" variant="primary">
                        Upload evidence
                      </Button>
                    </Link>
                  }
                />
              ) : (
                evidence.slice(0, 6).map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface-2/40 px-3 py-2"
                  >
                    <span className="text-xs font-medium text-primary">
                      {item.original_filename}
                    </span>
                    <span className="flex items-center gap-3 text-[11px] text-muted">
                      <span>{formatBytes(item.size_bytes)}</span>
                      <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                        {humanize(item.processing_status)}
                      </Badge>
                      <span className="font-mono">{shortHash(item.sha256)}</span>
                    </span>
                  </div>
                ))
              )}
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function FindingCard({
  finding,
  caseId,
  onOpenEvidence,
}: {
  finding: Finding;
  caseId: string;
  onOpenEvidence: () => void;
}) {
  const evidenceCount = finding.evidence_links.length;
  const firstEvidence = finding.evidence_links[0]?.evidence_id;
  return (
    <div className="rounded-xl border border-line bg-surface-2/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={severityStyle(finding.severity)}>
          {severityLabel(finding.severity)}
        </Badge>
        <Badge className="border-line-strong bg-surface-2/70 text-secondary">
          {humanize(finding.status)}
        </Badge>
        {finding.classification ? (
          <Badge className="border-line-strong bg-surface-2/70 capitalize text-muted">
            {finding.classification}
          </Badge>
        ) : null}
      </div>
      <p className="mt-2 text-sm font-medium leading-snug text-primary">{finding.title}</p>
      <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-secondary">
        {finding.explanation}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-muted">
        <span>
          {evidenceCount} supporting record{evidenceCount === 1 ? "" : "s"}
        </span>
        <span>Confidence: {humanize(finding.confidence)}</span>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-2">
        <Link to={`/cases/${caseId}/findings`}>
          <Button size="sm" variant="ghost" icon={<ArrowRight size={12} />}>
            Review finding
          </Button>
        </Link>
        <Button
          size="sm"
          variant="ghost"
          icon={<FileSearch size={12} />}
          onClick={onOpenEvidence}
        >
          View evidence ({firstEvidence ? shortHash(firstEvidence) : "—"})
        </Button>
      </div>
    </div>
  );
}
