import { useParams } from "react-router-dom";
import {
  Download,
  FileJson,
  FileText,
  RefreshCcw,
  ShieldAlert,
} from "lucide-react";
import { useGenerateReport, useReports } from "@/hooks/useApi";
import { api } from "@/api/client";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { formatDateTime, humanize } from "@/lib/format";

export function ReportsPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const toast = useToast();
  const reportsQuery = useReports(caseId);
  const generate = useGenerateReport(caseId ?? "");

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (reportsQuery.isLoading) return <LoadingState label="Loading reports…" />;
  if (reportsQuery.error)
    return <ErrorState message={reportsQuery.error.message} onRetry={() => reportsQuery.refetch()} />;

  const reports = reportsQuery.data ?? [];

  function createReport(type: "pdf" | "json") {
    generate.mutate(type, {
      onSuccess: () =>
        toast.push("success", "Report generated", `The ${type.toUpperCase()} report is ready.`),
      onError: (error) => toast.push("error", "Report generation failed", error.message),
    });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Reports"
        title="Traceable investigation exports"
        description="Reports include evidence hashes, provenance, timeline events, findings, limitations and review status. AI content is labelled separately."
        actions={
          <>
            <Button
              variant="primary"
              icon={<FileText size={15} />}
              onClick={() => createReport("pdf")}
              loading={generate.isPending}
            >
              Generate PDF
            </Button>
            <Button
              variant="secondary"
              icon={<FileJson size={15} />}
              onClick={() => createReport("json")}
              loading={generate.isPending}
            >
              Generate JSON
            </Button>
          </>
        }
      />

      <div className="mb-4 rounded-xl border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 px-4 py-3 text-xs leading-relaxed text-amber-800/80 dark:text-amber-100/80">
        <ShieldAlert size={15} className="mr-1 inline" />
        Generated reports are drafts for human review. They are not automatically
        court-admissible. Any Section 63 BSA certificate must be completed, verified and signed
        by the appropriate authorized person.
      </div>

      <Card>
        <CardHeader
          title="Generated reports"
          subtitle={`${reports.length} report(s) stored for this case`}
          action={
            <Button
              size="sm"
              variant="ghost"
              icon={<RefreshCcw size={13} />}
              onClick={() => reportsQuery.refetch()}
            >
              Refresh
            </Button>
          }
        />
        {reports.length === 0 ? (
          <CardBody>
            <EmptyState
              title="No reports generated"
              description="Generate a PDF or JSON report to preserve the current investigation state."
              icon={FileText}
            />
          </CardBody>
        ) : (
          <CardBody className="space-y-2">
            {reports.map((report) => (
              <div
                key={report.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface-2/40 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-primary">
                    {humanize(report.report_type)} report
                  </p>
                  <p className="mt-0.5 text-[10px] text-muted">
                    {report.filename} · generated {formatDateTime(report.generated_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="border-emerald-300 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200">
                    {humanize(report.status)}
                  </Badge>
                  <a
                    href={api.getReportDownloadUrl(caseId, report.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Button size="sm" variant="secondary" icon={<Download size={13} />}>
                      Download
                    </Button>
                  </a>
                </div>
              </div>
            ))}
          </CardBody>
        )}
      </Card>

      <Card className="mt-5">
        <CardHeader title="Report contents" subtitle="What the export preserves" />
        <CardBody className="grid gap-2 text-xs text-muted sm:grid-cols-2 lg:grid-cols-3">
          {[
            "Case metadata and status",
            "Evidence inventory and SHA-256 hashes",
            "Integrity verification results",
            "Parser and processing metadata",
            "Timeline events with source locators",
            "Rule-based findings and severity",
            "Graph relationships and conflicts",
            "Investigator review notes",
            "Limitations and alternative explanations",
            "AI interpretations, clearly labelled",
            "Audit trail summary",
            "Draft Section 63 BSA preparation",
          ].map((item) => (
            <div
              key={item}
              className="rounded-lg border border-line bg-surface-2/30 px-3 py-2"
            >
              {item}
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
