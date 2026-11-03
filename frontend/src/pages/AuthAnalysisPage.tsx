import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertTriangle,
  Download,
  Search,
  ShieldAlert,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useEvents, useFindings } from "@/hooks/useApi";
import { api } from "@/api/client";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input, Select } from "@/components/ui/Field";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { severityLabel, severityStyle } from "@/lib/severity";
import { formatDateTime, humanize } from "@/lib/format";
import type { EventRecord, Finding } from "@/types";

export function AuthAnalysisPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const eventsQuery = useEvents(caseId, { limit: 1000 });
  const findingsQuery = useFindings(caseId, { category: "authentication" });
  const [search, setSearch] = useState("");
  const [resultFilter, setResultFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState("all");
  const [selected, setSelected] = useState<EventRecord | null>(null);

  const allEvents = useMemo(() => eventsQuery.data?.items ?? [], [eventsQuery.data]);
  const authEvents = useMemo(
    () => allEvents.filter((event) => event.event_type.startsWith("auth.")),
    [allEvents],
  );
  const alerts = findingsQuery.data?.items ?? [];

  const filtered = useMemo(
    () =>
      authEvents.filter((event) => {
        const attributes = event.attributes_json as Record<string, unknown>;
        const user = String(attributes.username ?? "").toLowerCase();
        const ip = String(attributes.source_ip ?? "").toLowerCase();
        const matchesSearch =
          !search ||
          user.includes(search.toLowerCase()) ||
          ip.includes(search.toLowerCase()) ||
          event.source_snippet.toLowerCase().includes(search.toLowerCase());
        const status = String(attributes.auth_status ?? "unknown");
        const matchesResult = resultFilter === "all" || status === resultFilter;
        const matchesType = typeFilter === "all" || event.event_type === typeFilter;
        const matchesTime =
          timeFilter === "all" ||
          event.timestamp_normalized?.slice(0, 13) === timeFilter;
        return matchesSearch && matchesResult && matchesType && matchesTime;
      }),
    [authEvents, search, resultFilter, typeFilter, timeFilter],
  );

  const timeOptions = useMemo(() => {
    const options = new Map<string, string>();
    for (const event of authEvents) {
      if (!event.timestamp_normalized) continue;
      const key = event.timestamp_normalized.slice(0, 13);
      options.set(
        key,
        `${key.slice(8, 10)} ${key.slice(5, 7)} ${key.slice(11, 13)}:00 UTC`,
      );
    }
    return Array.from(options.entries()).sort((left, right) =>
      left[0].localeCompare(right[0]),
    );
  }, [authEvents]);

  const hourlySeries = useMemo(() => {
    const buckets = new Map<
      string,
      { hour: string; failures: number; successes: number }
    >();
    for (const event of authEvents) {
      if (!event.timestamp_normalized) continue;
      const key = event.timestamp_normalized.slice(0, 13);
      const bucket =
        buckets.get(key) ?? {
          hour: `${key.slice(8, 10)} ${key.slice(5, 7)} ${key.slice(11, 13)}:00`,
          failures: 0,
          successes: 0,
        };
      const attributes = event.attributes_json as Record<string, unknown>;
      if (attributes.auth_status === "failure") bucket.failures += 1;
      if (attributes.auth_status === "success") bucket.successes += 1;
      buckets.set(key, bucket);
    }
    return Array.from(buckets.entries())
      .sort((left, right) => left[0].localeCompare(right[0]))
      .map(([, value]) => value);
  }, [authEvents]);

  const counts = useMemo(() => {
    const failed = authEvents.filter(
      (event) => (event.attributes_json as Record<string, unknown>).auth_status === "failure",
    ).length;
    const success = authEvents.filter(
      (event) => (event.attributes_json as Record<string, unknown>).auth_status === "success",
    ).length;
    const invalid = authEvents.filter(
      (event) => (event.attributes_json as Record<string, unknown>).invalid_user === true,
    ).length;
    return { total: authEvents.length, failed, success, invalid };
  }, [authEvents]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (eventsQuery.isLoading) return <LoadingState label="Loading authentication events…" />;
  if (eventsQuery.error)
    return <ErrorState message={eventsQuery.error.message} onRetry={() => eventsQuery.refetch()} />;

  return (
    <div>
      <PageHeader
        eyebrow="Authentication analysis"
        title="SSH and host access activity"
        description="Deterministic parsing and threshold-based indicators. A suspicious pattern is not proof of compromise."
        actions={
          <>
            <a href={api.getAuthExportUrl(caseId, "json")} target="_blank" rel="noreferrer">
              <Button variant="secondary" icon={<Download size={14} />}>
                Export JSON
              </Button>
            </a>
            <a href={api.getAuthExportUrl(caseId, "csv")} target="_blank" rel="noreferrer">
              <Button variant="secondary" icon={<Download size={14} />}>
                Export CSV
              </Button>
            </a>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Summary label="Parsed auth events" value={counts.total} tone="cyan" />
        <Summary label="Successful logins" value={counts.success} tone="emerald" />
        <Summary label="Failed logins" value={counts.failed} tone="rose" />
        <Summary label="Invalid-user attempts" value={counts.invalid} tone="amber" />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Detection alerts"
            subtitle="Rule-based indicators produced by the authentication parser"
          />
          <CardBody className="space-y-3">
            {alerts.length === 0 ? (
              <EmptyState
                title="No authentication alerts"
                description="Parse an authentication log to run threshold-based checks."
                icon={ShieldCheck}
              />
            ) : (
              alerts.map((finding) => <AlertCard key={finding.id} finding={finding} />)
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Interpretation guardrails" subtitle="Read before acting" />
          <CardBody className="space-y-3 text-xs leading-relaxed text-muted">
            <p className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 p-3 text-amber-800/80 dark:text-amber-100/80">
              <AlertTriangle size={14} className="mb-1 inline" /> Failed-login bursts can be
              caused by user error, stale credentials, scanners, NAT sharing, or authorized
              testing. The parser reports indicators, not guilt.
            </p>
            <p>
              Source timestamps from syslog usually omit the year and timezone. Red Thread records
              the raw value, the inferred year, and the timezone assumption on every event.
            </p>
            <p>
              Every alert links back to the exact source line. Open a row to inspect the raw
              evidence before relying on a finding.
            </p>
          </CardBody>
        </Card>
      </div>

      <Card className="mt-5 min-w-0">
        <CardHeader
          title="Authentication volume by hour"
          subtitle="UTC buckets from normalized timestamps; failed vs successful logins"
        />
        <CardBody className="h-64">
          {hourlySeries.length === 0 ? (
            <EmptyState title="No timestamped authentication events" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={hourlySeries}
                margin={{ top: 8, right: 8, left: -18, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                <XAxis dataKey="hour" tick={{ fill: "var(--chart-axis)", fontSize: 10 }} />
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
                  dataKey="failures"
                  name="Failures"
                  fill="var(--chart-rose)"
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
                <Bar
                  dataKey="successes"
                  name="Successes"
                  fill="var(--chart-emerald)"
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>

      <Card className="mt-5">
        <CardHeader
          title="Parsed events"
          subtitle={`${filtered.length} of ${authEvents.length} authentication events`}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-2.5 text-muted" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="User, IP, or raw line"
                  className="w-52 pl-8 text-xs"
                />
              </div>
              <Select
                value={resultFilter}
                onChange={(event) => setResultFilter(event.target.value)}
                className="w-36 text-xs"
              >
                <option value="all">All results</option>
                <option value="success">Success</option>
                <option value="failure">Failure</option>
                <option value="unknown">Unknown</option>
              </Select>
              <Select
                value={typeFilter}
                onChange={(event) => setTypeFilter(event.target.value)}
                className="w-40 text-xs"
              >
                <option value="all">All event types</option>
                <option value="auth.login">Login</option>
                <option value="auth.session">Session</option>
                <option value="auth.sudo">Sudo</option>
                <option value="auth.invalid_user">Invalid user</option>
                <option value="auth.connection_closed">Connection closed</option>
                <option value="auth.disconnect">Disconnect</option>
              </Select>
              <Select
                value={timeFilter}
                onChange={(event) => setTimeFilter(event.target.value)}
                className="w-40 text-xs"
              >
                <option value="all">All times</option>
                {timeOptions.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </div>
          }
        />
        {filtered.length === 0 ? (
          <CardBody>
            <EmptyState
              title={authEvents.length === 0 ? "No authentication events" : "No matching events"}
              description={
                authEvents.length === 0
                  ? "Upload an auth.log or supported SSH log and parse it."
                  : "Adjust the filters or search query."
              }
              icon={Terminal}
            />
          </CardBody>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Timestamp</TH>
                <TH>Event</TH>
                <TH>User</TH>
                <TH>Source IP</TH>
                <TH>Result</TH>
                <TH>Method</TH>
                <TH>Source</TH>
              </TR>
            </THead>
            <TBody>
              {filtered.slice(0, 500).map((event) => {
                const attributes = event.attributes_json as Record<string, unknown>;
                return (
                  <TR
                    key={event.id}
                    className="cursor-pointer"
                    onClick={() => setSelected(event)}
                  >
                    <TD className="whitespace-nowrap text-xs">
                      <div>{formatDateTime(event.timestamp_normalized)}</div>
                      <div className="text-[10px] text-muted">
                        {event.timestamp_raw || "No timestamp"}
                      </div>
                    </TD>
                    <TD>
                      <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                        {humanize(event.event_type.replace("auth.", ""))}
                      </Badge>
                    </TD>
                    <TD className="font-mono text-xs">{String(attributes.username ?? "—")}</TD>
                    <TD className="font-mono text-xs">
                      {String(attributes.source_ip ?? "—")}
                    </TD>
                    <TD>
                      <ResultBadge value={String(attributes.auth_status ?? "unknown")} />
                    </TD>
                    <TD className="text-xs">{String(attributes.auth_method ?? "—")}</TD>
                    <TD className="font-mono text-[10px] text-muted">
                      {event.source_filename}:{event.source_locator}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </Card>

      <Drawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title="Authentication event"
        subtitle={selected ? `${selected.source_filename} · ${selected.source_locator}` : undefined}
        wide
      >
        {selected ? <EventDetail event={selected} /> : null}
      </Drawer>
    </div>
  );
}

function Summary({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "cyan" | "emerald" | "rose" | "amber";
}) {
  const tones = {
    cyan: "border-accent/20 bg-accent/5 text-accent",
    emerald: "border-emerald-200 dark:border-emerald-500/20 bg-emerald-50/80 dark:bg-emerald-500/5 text-emerald-700 dark:text-emerald-200",
    rose: "border-rose-200 dark:border-rose-500/20 bg-rose-50/80 dark:bg-rose-500/5 text-rose-700 dark:text-rose-200",
    amber: "border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 text-amber-700 dark:text-amber-200",
  };
  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <p className="text-[10px] uppercase tracking-wider opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function ResultBadge({ value }: { value: string }) {
  const className =
    value === "success"
      ? "border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
      : value === "failure"
        ? "border-rose-300 dark:border-rose-500/40 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-200"
        : "border-line-strong bg-surface-2/70 text-muted";
  return <Badge className={className}>{humanize(value)}</Badge>;
}

function AlertCard({ finding }: { finding: Finding }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-primary">{finding.title}</p>
          <p className="mt-1 text-[10px] uppercase tracking-wider text-muted">
            {humanize(finding.detection_method)} · confidence {humanize(finding.confidence)}
          </p>
        </div>
        <div className="flex gap-2">
          <Badge className={severityStyle(finding.severity)}>
            {severityLabel(finding.severity)}
          </Badge>
          <Badge className="border-line-strong bg-surface-2/70 text-secondary">
            {humanize(finding.status)}
          </Badge>
        </div>
      </div>
      <p className="mt-3 whitespace-pre-line text-xs leading-relaxed text-muted">
        {finding.explanation}
      </p>
      {finding.limitations ? (
        <p className="mt-3 rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 p-2 text-[11px] leading-relaxed text-amber-800/80 dark:text-amber-100/70">
          <ShieldAlert size={12} className="mr-1 inline" />
          {finding.limitations}
        </p>
      ) : null}
      {finding.alternative_explanations ? (
        <p className="mt-2 text-[11px] leading-relaxed text-muted">
          Alternatives: {finding.alternative_explanations}
        </p>
      ) : null}
    </div>
  );
}

function EventDetail({ event }: { event: EventRecord }) {
  const attributes = event.attributes_json as Record<string, unknown>;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 text-xs">
        <Info label="Event type" value={event.event_type} />
        <Info label="Timestamp confidence" value={humanize(event.timestamp_confidence)} />
        <Info label="Raw timestamp" value={event.timestamp_raw || "—"} mono />
        <Info
          label="Normalized (UTC)"
          value={event.timestamp_normalized || "Not normalized"}
          mono
        />
        <Info label="Source file" value={event.source_filename} />
        <Info label="Source locator" value={event.source_locator} mono />
        <Info label="Parser" value={`${event.parser_name} ${event.parser_version}`} />
        <Info label="Evidence ID" value={event.evidence_id} mono />
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Raw source line
        </p>
        <pre className="whitespace-pre-wrap break-words rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[11px] leading-relaxed text-accent">
          {event.source_snippet || "No source snippet stored."}
        </pre>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Extracted attributes
        </p>
        <pre className="max-h-64 overflow-auto rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[10px] leading-relaxed text-muted">
          {JSON.stringify(attributes, null, 2)}
        </pre>
      </div>

      {event.warnings_json.length > 0 ? (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-500/80">
            Parser warnings
          </p>
          <div className="space-y-1">
            {event.warnings_json.map((warning, index) => (
              <p
                key={index}
                className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 px-3 py-2 text-[11px] text-amber-800/80 dark:text-amber-100/80"
              >
                {warning}
              </p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Info({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/40 px-3 py-2">
      <p className="text-[9px] uppercase tracking-wider text-muted">{label}</p>
      <p className={`mt-0.5 break-all text-xs text-secondary ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}
