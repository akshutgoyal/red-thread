import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Activity,
  Bot,
  FileSearch,
  GitBranch,
  ListChecks,
  PlayCircle,
  RefreshCcw,
  ScrollText,
  ShieldAlert,
  UploadCloud,
} from "lucide-react";
import { useCaseContext } from "@/context/CaseContext";
import {
  useAudit,
  useCase,
  useEvidence,
  useFindings,
  useReconcile,
  useUpdateCase,
} from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/ui/StatCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Label, Select, Textarea } from "@/components/ui/Field";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { severityLabel, severityStyle, statusStyle } from "@/lib/severity";
import { formatBytes, formatDateTime, humanize, shortHash } from "@/lib/format";

export function CaseOverviewPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { setSelectedCaseId } = useCaseContext();
  const toast = useToast();
  const caseQuery = useCase(caseId);
  const evidenceQuery = useEvidence(caseId);
  const findingsQuery = useFindings(caseId);
  const auditQuery = useAudit(caseId);
  const updateCase = useUpdateCase(caseId ?? "");
  const reconcile = useReconcile(caseId ?? "");

  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState("open");

  useEffect(() => {
    if (caseId) setSelectedCaseId(caseId);
  }, [caseId, setSelectedCaseId]);

  useEffect(() => {
    if (caseQuery.data) {
      setNotes(caseQuery.data.investigator_notes);
      setStatus(caseQuery.data.status);
    }
  }, [caseQuery.data]);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (caseQuery.isLoading) return <LoadingState label="Loading case…" />;
  if (caseQuery.error)
    return <ErrorState message={caseQuery.error.message} onRetry={() => caseQuery.refetch()} />;
  if (!caseQuery.data) return <ErrorState title="Case not found" />;

  const currentCase = caseQuery.data;
  const evidence = evidenceQuery.data ?? [];
  const findings = findingsQuery.data?.items ?? [];
  const audit = auditQuery.data ?? [];

  function saveCase() {
    updateCase.mutate(
      { investigator_notes: notes, status: status as "open" | "in_review" | "closed" },
      {
        onSuccess: () => toast.push("success", "Case updated"),
        onError: (error) => toast.push("error", "Could not update case", error.message),
      },
    );
  }

  function runReconciliation() {
    reconcile.mutate(undefined, {
      onSuccess: (result) =>
        toast.push(
          "success",
          "Reconciliation complete",
          `${result.findings_created} finding(s) produced by deterministic checks.`,
        ),
      onError: (error) => toast.push("error", "Reconciliation failed", error.message),
    });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Case overview"
        title={currentCase.title}
        description={currentCase.description || "No case description supplied."}
        actions={
          <>
            <Link to={`/cases/${caseId}/evidence/intake`}>
              <Button variant="primary" icon={<UploadCloud size={15} />}>
                Upload evidence
              </Button>
            </Link>
            <Button
              variant="secondary"
              icon={<PlayCircle size={15} />}
              onClick={runReconciliation}
              loading={reconcile.isPending}
            >
              Run checks
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Evidence" value={evidence.length} icon={FileSearch} tone="cyan" />
        <StatCard label="Events" value={currentCase.event_count} icon={Activity} tone="violet" />
        <StatCard
          label="Open findings"
          value={currentCase.open_finding_count}
          hint={`${findings.length} total`}
          icon={ShieldAlert}
          tone="rose"
        />
        <StatCard
          label="Hash-verified"
          value={evidence.filter((item) => item.hash_verified).length}
          hint="Files matching recorded SHA-256"
          icon={RefreshCcw}
          tone="emerald"
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Case notes and status" subtitle="Investigator-controlled context" />
          <CardBody className="grid gap-4 md:grid-cols-[2fr_1fr]">
            <div>
              <Label htmlFor="case-notes">Investigator notes</Label>
              <Textarea
                id="case-notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Authorization, scope, handling notes, and hypotheses."
              />
            </div>
            <div className="space-y-4">
              <div>
                <Label htmlFor="case-status">Status</Label>
                <Select
                  id="case-status"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                >
                  <option value="open">Open</option>
                  <option value="in_review">In review</option>
                  <option value="closed">Closed</option>
                </Select>
              </div>
              <Button
                variant="primary"
                onClick={saveCase}
                loading={updateCase.isPending}
                className="w-full"
              >
                Save changes
              </Button>
              <p className="text-[10px] leading-relaxed text-muted">
                Case metadata is stored with an audit event. Evidence files are never modified
                by this action.
              </p>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Investigation workspaces" subtitle="Jump to a case view" />
          <CardBody className="grid grid-cols-2 gap-2">
            <WorkspaceLink to={`/cases/${caseId}/auth`} icon={ShieldAlert} label="Auth analysis" />
            <WorkspaceLink to={`/cases/${caseId}/timeline`} icon={ScrollText} label="Timeline" />
            <WorkspaceLink to={`/cases/${caseId}/graph`} icon={GitBranch} label="Graph" />
            <WorkspaceLink to={`/cases/${caseId}/findings`} icon={ListChecks} label="Findings" />
            <WorkspaceLink to={`/cases/${caseId}/ai`} icon={Bot} label="AI assistant" />
            <WorkspaceLink to={`/cases/${caseId}/reports`} icon={FileSearch} label="Reports" />
          </CardBody>
        </Card>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader
            title="Evidence"
            subtitle="Original files with SHA-256 provenance"
            action={
              <Link
                to={`/cases/${caseId}/evidence`}
                className="text-xs text-accent hover:text-accent"
              >
                Open vault
              </Link>
            }
          />
          {evidence.length === 0 ? (
            <CardBody>
              <EmptyState
                title="No evidence"
                description="Upload supported files to start the investigation."
              />
            </CardBody>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>File</TH>
                  <TH>Status</TH>
                  <TH>SHA-256</TH>
                  <TH>Uploaded</TH>
                </TR>
              </THead>
              <TBody>
                {evidence.slice(0, 8).map((item) => (
                  <TR key={item.id}>
                    <TD className="font-medium text-primary">{item.original_filename}</TD>
                    <TD>
                      <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                        {humanize(item.processing_status)}
                      </Badge>
                    </TD>
                    <TD className="font-mono text-[11px] text-muted">
                      {shortHash(item.sha256)}
                    </TD>
                    <TD className="text-xs text-muted">{formatBytes(item.size_bytes)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Findings"
            subtitle="Deterministic and correlation output"
            action={
              <Link
                to={`/cases/${caseId}/findings`}
                className="text-xs text-accent hover:text-accent"
              >
                Review
              </Link>
            }
          />
          <CardBody className="space-y-2">
            {findings.length === 0 ? (
              <EmptyState
                title="No findings yet"
                description="Parse evidence and run deterministic checks."
              />
            ) : (
              findings.slice(0, 6).map((finding) => (
                <div
                  key={finding.id}
                  className="rounded-lg border border-line bg-surface-2/40 p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-medium text-secondary">{finding.title}</p>
                    <Badge className={severityStyle(finding.severity)}>
                      {severityLabel(finding.severity)}
                    </Badge>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] text-muted">
                    <Badge className={statusStyle(finding.status)}>{humanize(finding.status)}</Badge>
                    <span>{humanize(finding.detection_method)}</span>
                  </div>
                </div>
              ))
            )}
          </CardBody>
        </Card>
      </div>

      <Card className="mt-5">
        <CardHeader title="Audit trail" subtitle="Evidence handling and analysis actions" />
        <CardBody>
          {audit.length === 0 ? (
            <EmptyState title="No audit events yet" />
          ) : (
            <div className="space-y-2">
              {audit.slice(0, 12).map((event) => (
                <div
                  key={event.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface-2/30 px-3 py-2"
                >
                  <div>
                    <p className="text-xs font-medium text-secondary">
                      {humanize(event.action)}
                    </p>
                    <p className="text-[10px] text-muted">
                      {event.evidence_id ? `Evidence ${event.evidence_id.slice(0, 8)}` : "Case"} ·{" "}
                      {event.actor}
                    </p>
                  </div>
                  <span className="text-[10px] text-muted">
                    {formatDateTime(event.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function WorkspaceLink({
  to,
  icon: Icon,
  label,
}: {
  to: string;
  icon: typeof Activity;
  label: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 rounded-lg border border-line bg-surface-2/40 px-3 py-2.5 text-xs text-secondary transition hover:border-accent/30 hover:text-accent"
    >
      <Icon size={14} />
      {label}
    </Link>
  );
}
