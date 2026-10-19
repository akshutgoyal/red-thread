import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  FileSearch,
  FolderOpen,
  ListChecks,
  ShieldAlert,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useCaseContext } from "@/context/CaseContext";
import { useCase, useEvidence, useEvents, useFindings } from "@/hooks/useApi";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { severityStyle, severityLabel, SEVERITY_ORDER } from "@/lib/severity";
import { formatBytes, formatDateTime, humanize, shortHash } from "@/lib/format";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--chart-rose)",
  high: "var(--chart-orange)",
  medium: "var(--chart-amber)",
  low: "var(--chart-sky)",
  info: "var(--chart-slate)",
};

export function DashboardPage() {
  const { cases, selectedCaseId, selectedCase, isLoading: casesLoading, error: casesError } =
    useCaseContext();
  const caseQuery = useCase(selectedCaseId ?? undefined);
  const evidenceQuery = useEvidence(selectedCaseId ?? undefined);
  const eventsQuery = useEvents(selectedCaseId ?? undefined, { limit: 500 });
  const findingsQuery = useFindings(selectedCaseId ?? undefined);

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

  const latestFindings = useMemo(
    () =>
      [...findings]
        .sort((left, right) => {
          const severityDelta =
            SEVERITY_ORDER.indexOf(left.severity) - SEVERITY_ORDER.indexOf(right.severity);
          if (severityDelta !== 0) return severityDelta;
          return right.created_at.localeCompare(left.created_at);
        })
        .slice(0, 5),
    [findings],
  );

  const evidenceByType = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of evidence) {
      const extension = item.original_filename.includes(".")
        ? item.original_filename.split(".").pop()?.toUpperCase() ?? "OTHER"
        : "OTHER";
      counts.set(extension, (counts.get(extension) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((left, right) => right.count - left.count);
  }, [evidence]);

  const parsedEvidenceCount = useMemo(
    () => evidence.filter((item) => item.processing_status === "parsed").length,
    [evidence],
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
            <Link to="/cases">
              <Button variant="primary" icon={<FolderOpen size={15} />}>
                Create a case
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  if (!selectedCaseId) {
    return <ErrorState title="No active case" message="Select or create a case to continue." />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Investigation overview"
        title="Dashboard"
        description="Real counts from the current case. Every number is derived from stored evidence and findings."
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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Cases" value={cases.length} icon={FolderOpen} tone="cyan" />
        <StatCard
          label="Evidence files"
          value={evidence.length}
          hint={summary ? `${summary.event_count} extracted events` : undefined}
          icon={FileSearch}
          tone="emerald"
        />
        <StatCard
          label="Open findings"
          value={findings.filter((item) => item.status === "open" || item.status === "needs_review").length}
          hint={`${findings.length} findings total`}
          icon={ShieldAlert}
          tone="rose"
        />
        <StatCard
          label="Timeline events"
          value={events.length}
          hint="Most recent 500 loaded"
          icon={Activity}
          tone="violet"
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <Card className="min-w-0 xl:col-span-2">
          <CardHeader
            title="Events by type"
            subtitle="Extracted canonical events in the current case"
          />
          <CardBody className="h-72">
            {eventsByType.length === 0 ? (
              <EmptyState title="No events yet" description="Upload and parse evidence first." />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={eventsByType} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "var(--chart-axis)", fontSize: 10 }}
                    interval={0}
                    angle={-18}
                    textAnchor="end"
                    height={55}
                  />
                  <YAxis tick={{ fill: "var(--chart-axis)", fontSize: 11 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--chart-tooltip-bg)",
                      border: "1px solid var(--chart-tooltip-border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "var(--chart-axis)" }}
                    itemStyle={{ color: "var(--chart-axis)" }}
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
          <CardHeader title="Findings by severity" subtitle="Rule-based and reconciliation output" />
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
                          <Cell key={entry.key} fill={SEVERITY_COLORS[entry.key] ?? "#94a3b8"} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "var(--chart-tooltip-bg)",
                          border: "1px solid var(--chart-tooltip-border)",
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        labelStyle={{ color: "var(--chart-axis)" }}
                        itemStyle={{ color: "var(--chart-axis)" }}
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

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <Card className="min-w-0 xl:col-span-2">
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
          {evidence.length === 0 ? (
            <CardBody>
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
            </CardBody>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>File</TH>
                  <TH>Size</TH>
                  <TH>Status</TH>
                  <TH>SHA-256</TH>
                  <TH>Uploaded</TH>
                </TR>
              </THead>
              <TBody>
                {evidence.slice(0, 6).map((item) => (
                  <TR key={item.id}>
                    <TD className="font-medium text-primary">{item.original_filename}</TD>
                    <TD>{formatBytes(item.size_bytes)}</TD>
                    <TD>
                      <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                        {humanize(item.processing_status)}
                      </Badge>
                    </TD>
                    <TD className="font-mono text-[11px] text-muted">
                      {shortHash(item.sha256)}
                    </TD>
                    <TD className="text-xs text-muted">{formatDateTime(item.uploaded_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Latest findings"
            subtitle="Require investigator review"
            action={
              <Link
                to={`/cases/${selectedCaseId}/findings`}
                className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent-strong"
              >
                View all <ArrowRight size={12} />
              </Link>
            }
          />
          <CardBody className="space-y-3">
            {findings.length === 0 ? (
              <EmptyState
                title="No findings yet"
                description="Parse evidence and run reconciliation."
              />
            ) : (
              latestFindings.map((finding) => (
                <Link
                  key={finding.id}
                  to={`/cases/${selectedCaseId}/findings`}
                  className="block rounded-lg border border-line bg-surface-2/40 p-3 transition hover:border-line-strong"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-medium leading-snug text-secondary">
                      {finding.title}
                    </p>
                    <Badge className={severityStyle(finding.severity)}>
                      {severityLabel(finding.severity)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-[10px] uppercase tracking-wider text-muted">
                    {humanize(finding.category)} · {humanize(finding.status)}
                  </p>
                </Link>
              ))
            )}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-5 min-w-0">
        <CardHeader
          title="Evidence by file type"
          subtitle={`${parsedEvidenceCount} of ${evidence.length} parsed · grouped by extension`}
        />
        <CardBody className="h-56">
          {evidenceByType.length === 0 ? (
            <EmptyState title="No evidence data" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={evidenceByType} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="name" tick={{ fill: "var(--chart-axis)", fontSize: 10 }} />
                <YAxis tick={{ fill: "var(--chart-axis)", fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "var(--chart-tooltip-bg)",
                    border: "1px solid var(--chart-tooltip-border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: "var(--chart-axis)" }}
                  itemStyle={{ color: "var(--chart-axis)" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {evidenceByType.map((entry, index) => (
                    <Cell
                      key={entry.name}
                      fill={
                        [
                          "var(--chart-cyan)",
                          "var(--chart-violet)",
                          "var(--chart-amber)",
                          "var(--chart-emerald)",
                          "var(--chart-sky)",
                          "var(--chart-orange)",
                        ][index % 6]
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
