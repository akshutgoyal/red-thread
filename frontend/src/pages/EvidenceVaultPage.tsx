import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Copy,
  FileSearch,
  RefreshCcw,
  Search,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import {
  useAudit,
  useEvidence,
  useParseEvidence,
  useVerifyEvidence,
} from "@/hooks/useApi";
import { api } from "@/api/client";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Input, Select } from "@/components/ui/Field";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import {
  copyText,
  formatBytes,
  formatDateTime,
  humanize,
  shortHash,
} from "@/lib/format";
import type { Evidence } from "@/types";

export function EvidenceVaultPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const toast = useToast();
  const evidenceQuery = useEvidence(caseId);
  const auditQuery = useAudit(caseId);
  const verify = useVerifyEvidence(caseId ?? "");
  const parse = useParseEvidence(caseId ?? "");
  const [selected, setSelected] = useState<Evidence | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");

  const evidence = useMemo(() => evidenceQuery.data ?? [], [evidenceQuery.data]);
  const filtered = useMemo(
    () =>
      evidence.filter((item) => {
        const matchesSearch =
          !search ||
          item.original_filename.toLowerCase().includes(search.toLowerCase()) ||
          item.sha256.toLowerCase().includes(search.toLowerCase());
        const matchesStatus = status === "all" || item.processing_status === status;
        return matchesSearch && matchesStatus;
      }),
    [evidence, search, status],
  );

  if (!caseId) return <ErrorState title="Missing case ID" />;

  async function copyHash(hash: string) {
    const copied = await copyText(hash);
    toast.push(copied ? "success" : "error", copied ? "Hash copied" : "Copy failed");
  }

  async function verifyEvidence(item: Evidence) {
    try {
      const result = await verify.mutateAsync(item.id);
      toast.push(
        result.verified ? "success" : "error",
        result.verified ? "Integrity verified" : "Integrity violation",
        result.message,
      );
    } catch (error) {
      toast.push("error", "Verification failed", error instanceof Error ? error.message : "");
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Evidence vault"
        title="Evidence inventory"
        description="Browse stored files, verify digests, inspect provenance, and open source previews."
        actions={
          <Link to={`/cases/${caseId}/evidence/intake`}>
            <Button variant="primary" icon={<UploadCloud size={15} />}>
              Upload evidence
            </Button>
          </Link>
        }
      />

      <Card>
        <CardHeader
          title="Stored evidence"
          subtitle={`${evidence.length} file(s) in this case`}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-2.5 text-muted" />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search filename or hash"
                  className="w-56 pl-8 text-xs"
                />
              </div>
              <Select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="w-40 text-xs"
              >
                <option value="all">All statuses</option>
                <option value="uploaded">Uploaded</option>
                <option value="parsed">Parsed</option>
                <option value="partially_parsed">Partially parsed</option>
                <option value="ocr_unavailable">OCR unavailable</option>
                <option value="failed">Failed</option>
              </Select>
            </div>
          }
        />
        {evidenceQuery.isLoading ? (
          <CardBody>
            <LoadingState label="Loading evidence…" />
          </CardBody>
        ) : evidenceQuery.error ? (
          <CardBody>
            <ErrorState
              message={evidenceQuery.error.message}
              onRetry={() => evidenceQuery.refetch()}
            />
          </CardBody>
        ) : filtered.length === 0 ? (
          <CardBody>
            <EmptyState
              title={evidence.length === 0 ? "No evidence in this case" : "No matching evidence"}
              description={
                evidence.length === 0
                  ? "Upload supported files to preserve them and extract events."
                  : "Adjust the search or status filter."
              }
              icon={FileSearch}
            />
          </CardBody>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>File</TH>
                <TH className="hidden 2xl:table-cell">Type</TH>
                <TH>Size</TH>
                <TH>Status</TH>
                <TH>Integrity</TH>
                <TH>SHA-256</TH>
                <TH className="hidden 2xl:table-cell">Uploaded</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {filtered.map((item) => (
                <TR key={item.id} className="cursor-pointer" onClick={() => setSelected(item)}>
                  <TD className="min-w-[180px] font-medium text-primary">{item.original_filename}</TD>
                  <TD className="hidden 2xl:table-cell text-xs text-muted">{item.media_type}</TD>
                  <TD className="whitespace-nowrap">{formatBytes(item.size_bytes)}</TD>
                  <TD className="whitespace-nowrap">
                    <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                      {humanize(item.processing_status)}
                    </Badge>
                  </TD>
                  <TD className="whitespace-nowrap">
                    <Badge
                      className={
                        item.hash_verified
                          ? "border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
                          : "border-line-strong bg-surface-2/70 text-muted"
                      }
                    >
                      {item.hash_verified ? "Verified" : "Not checked"}
                    </Badge>
                  </TD>
                  <TD className="max-w-[140px] truncate font-mono text-[11px] text-muted">
                    {shortHash(item.sha256)}
                  </TD>
                  <TD className="hidden 2xl:table-cell whitespace-nowrap text-xs text-muted">
                    {formatDateTime(item.uploaded_at)}
                  </TD>
                  <TD className="whitespace-nowrap">
                    <div className="flex justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation();
                          void verifyEvidence(item);
                        }}
                        icon={<ShieldCheck size={12} />}
                      >
                        Verify
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(event) => {
                          event.stopPropagation();
                          parse.mutate(
                            { evidenceId: item.id, reparse: item.processing_status === "parsed" },
                            {
                              onSuccess: (result) =>
                                toast.push(
                                  "success",
                                  "Evidence parsed",
                                  `${result.events_created} event(s), ${result.findings_created} finding(s).`,
                                ),
                              onError: (error) =>
                                toast.push("error", "Parse failed", error.message),
                            },
                          );
                        }}
                        icon={<RefreshCcw size={12} />}
                      >
                        {item.processing_status === "parsed" ? "Reparse" : "Parse"}
                      </Button>
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      <Drawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.original_filename ?? "Evidence"}
        subtitle={selected?.media_type}
        wide
      >
        {selected ? (
          <EvidenceDetail
            evidence={selected}
            caseId={caseId}
            audit={auditQuery.data ?? []}
            onVerify={() => void verifyEvidence(selected)}
            onParse={() =>
              parse.mutate(
                {
                  evidenceId: selected.id,
                  reparse: selected.processing_status === "parsed",
                },
                {
                  onSuccess: (result) =>
                    toast.push(
                      "success",
                      "Evidence parsed",
                      `${result.events_created} event(s), ${result.findings_created} finding(s).`,
                    ),
                  onError: (error) => toast.push("error", "Parse failed", error.message),
                },
              )
            }
            onCopyHash={() => void copyHash(selected.sha256)}
          />
        ) : null}
      </Drawer>
    </div>
  );
}

function EvidenceDetail({
  evidence,
  caseId,
  audit,
  onVerify,
  onParse,
  onCopyHash,
}: {
  evidence: Evidence;
  caseId: string;
  audit: import("@/types").AuditEvent[];
  onVerify: () => void;
  onParse: () => void;
  onCopyHash: () => void;
}) {
  const isText =
    evidence.media_type.startsWith("text/") ||
    evidence.media_type === "application/json" ||
    evidence.media_type === "application/x-ndjson" ||
    evidence.media_type === "message/rfc822";
  const isImage = evidence.media_type.startsWith("image/");
  const isPdf = evidence.media_type === "application/pdf";
  const contentUrl = api.getEvidenceContentUrl(caseId, evidence.id);
  const textQuery = useQuery({
    queryKey: ["evidence-text", evidence.id],
    queryFn: () => api.getEvidenceText(caseId, evidence.id),
    enabled: isText,
  });
  const evidenceAudit = audit.filter((item) => item.evidence_id === evidence.id);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 text-xs">
        <Info label="Evidence ID" value={evidence.id} mono />
        <Info label="Case ID" value={evidence.case_id} mono />
        <Info label="Size" value={formatBytes(evidence.size_bytes)} />
        <Info label="Uploaded" value={formatDateTime(evidence.uploaded_at)} />
        <Info label="Parser" value={evidence.parser_name ?? "Not parsed"} />
        <Info label="Parser version" value={evidence.parser_version ?? "—"} />
        <Info label="Processing status" value={humanize(evidence.processing_status)} />
        <Info
          label="Integrity"
          value={
            evidence.hash_verified
              ? `Verified at ${formatDateTime(evidence.hash_verified_at)}`
              : "Not verified in this session"
          }
        />
      </div>

      <div className="rounded-xl border border-line bg-surface-2/40 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
          SHA-256 digest
        </p>
        <div className="mt-2 flex items-start gap-2">
          <code className="break-all font-mono text-[11px] leading-relaxed text-accent/80">
            {evidence.sha256}
          </code>
          <button
            type="button"
            onClick={onCopyHash}
            className="rounded p-1 text-muted hover:bg-surface-2 hover:text-accent"
            title="Copy hash"
          >
            <Copy size={14} />
          </button>
        </div>
      </div>

      {evidence.processing_error ? (
        <div className="rounded-xl border border-rose-200 dark:border-rose-500/20 bg-rose-50/80 dark:bg-rose-500/5 p-3 text-xs text-rose-700 dark:text-rose-200">
          {evidence.processing_error}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" icon={<ShieldCheck size={14} />} onClick={onVerify}>
          Verify integrity
        </Button>
        <Button variant="secondary" icon={<RefreshCcw size={14} />} onClick={onParse}>
          {evidence.processing_status === "parsed" ? "Reparse evidence" : "Parse evidence"}
        </Button>
        <a href={contentUrl} target="_blank" rel="noreferrer">
          <Button variant="ghost">Open stored file</Button>
        </a>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Source preview
        </p>
        <div className="max-h-80 overflow-auto rounded-xl border border-line bg-surface-2/60 p-3">
          {isText ? (
            textQuery.isLoading ? (
              <p className="text-xs text-muted">Loading preview…</p>
            ) : textQuery.error ? (
              <p className="text-xs text-rose-600 dark:text-rose-300">{textQuery.error.message}</p>
            ) : (
              <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-secondary">
                {textQuery.data?.text || "Empty file."}
              </pre>
            )
          ) : isImage ? (
            <img src={contentUrl} alt={evidence.original_filename} className="max-h-72 rounded-lg" />
          ) : isPdf ? (
            <iframe
              src={contentUrl}
              title={evidence.original_filename}
              className="h-72 w-full rounded-lg bg-white"
            />
          ) : (
            <p className="text-xs text-muted">
              Preview is not available for this media type. Use “Open stored file”.
            </p>
          )}
        </div>
        {isText && textQuery.data?.truncated ? (
          <p className="mt-1 text-[10px] text-amber-600/80 dark:text-amber-300/70">
            Preview truncated. Open the stored file for the complete content.
          </p>
        ) : null}
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Extraction metadata
        </p>
        <pre className="max-h-56 overflow-auto rounded-xl border border-line bg-surface-2/60 p-3 font-mono text-[10px] leading-relaxed text-muted">
          {JSON.stringify(evidence.metadata_json ?? {}, null, 2)}
        </pre>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Evidence audit trail
        </p>
        {evidenceAudit.length === 0 ? (
          <p className="text-xs text-muted">No audit events recorded for this file.</p>
        ) : (
          <div className="space-y-2">
            {evidenceAudit.map((item) => (
              <div
                key={item.id}
                className="rounded-lg border border-line bg-surface-2/40 px-3 py-2 text-xs"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-secondary">{humanize(item.action)}</span>
                  <span className="text-[10px] text-muted">
                    {formatDateTime(item.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-muted">
                  {item.actor} · {JSON.stringify(item.details_json)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
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
