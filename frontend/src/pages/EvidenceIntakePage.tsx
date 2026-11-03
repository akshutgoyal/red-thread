import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CheckCircle2,
  Copy,
  FileUp,
  Loader2,
  ShieldCheck,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useParseEvidence, useUploadEvidence, useVerifyEvidence } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { copyText, formatBytes, humanize, shortHash } from "@/lib/format";
import type { Evidence, ParseResponse } from "@/types";

const SUPPORTED = [".csv", ".json", ".jsonl", ".txt", ".log", ".pdf", ".eml", ".png", ".jpg", ".jpeg"];
const MAX_MB = 50;

interface UploadResult {
  evidence?: Evidence;
  parse?: ParseResponse;
  error?: string;
  filename: string;
}

export function EvidenceIntakePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadEvidence(caseId ?? "");
  const parse = useParseEvidence(caseId ?? "");
  const verify = useVerifyEvidence(caseId ?? "");
  const [dragActive, setDragActive] = useState(false);
  const [autoParse, setAutoParse] = useState(true);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [busy, setBusy] = useState(false);

  if (!caseId) return <ErrorState title="Missing case ID" />;

  async function handleFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    setBusy(true);
    for (const file of files) {
      const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
      if (!SUPPORTED.includes(extension)) {
        setResults((current) => [
          ...current,
          { filename: file.name, error: `Unsupported file type ${extension}.` },
        ]);
        toast.push("error", "Unsupported file", `${file.name} is not a supported evidence type.`);
        continue;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        setResults((current) => [
          ...current,
          { filename: file.name, error: `File exceeds ${MAX_MB} MB.` },
        ]);
        toast.push("error", "File too large", `${file.name} exceeds the ${MAX_MB} MB limit.`);
        continue;
      }

      try {
        const evidence = await upload.mutateAsync(file);
        setResults((current) => [...current, { filename: file.name, evidence }]);
        toast.push("success", "Evidence uploaded", `${file.name} hashed with SHA-256.`);

        if (autoParse) {
          try {
            const parsed = await parse.mutateAsync({ evidenceId: evidence.id });
            setResults((current) =>
              current.map((item) =>
                item.evidence?.id === evidence.id ? { ...item, parse: parsed } : item,
              ),
            );
            toast.push(
              "success",
              "Evidence parsed",
              `${parsed.events_created} event(s) and ${parsed.findings_created} finding(s).`,
            );
          } catch (error) {
            const message = error instanceof Error ? error.message : "Parsing failed";
            setResults((current) =>
              current.map((item) =>
                item.evidence?.id === evidence.id ? { ...item, error: message } : item,
              ),
            );
            toast.push("error", "Parsing failed", message);
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Upload failed";
        setResults((current) => [...current, { filename: file.name, error: message }]);
        toast.push("error", "Upload failed", message);
      }
    }
    setBusy(false);
  }

  async function copyHash(hash: string) {
    const copied = await copyText(hash);
    toast.push(copied ? "success" : "error", copied ? "Hash copied" : "Copy failed");
  }

  async function verifyFile(evidence: Evidence) {
    try {
      const result = await verify.mutateAsync(evidence.id);
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
        eyebrow="Evidence intake"
        title="Preserve and process evidence"
        description="Every upload is stored with a generated filename, a SHA-256 digest, and an audit record. The original bytes are never modified."
        actions={
          <Link to={`/cases/${caseId}/evidence`}>
            <Button variant="secondary">Open evidence vault</Button>
          </Link>
        }
      />

      <Card>
        <CardBody>
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              void handleFiles(event.dataTransfer.files);
            }}
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition ${
              dragActive
                ? "border-accent/60 bg-accent/5"
                : "border-line-strong bg-surface-2/30"
            }`}
          >
            <span className="rounded-full border border-line-strong bg-surface p-4 text-accent">
              <UploadCloud size={26} />
            </span>
            <p className="mt-4 text-sm font-medium text-secondary">
              Drop evidence files here, or choose files
            </p>
            <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted">
              Supported: {SUPPORTED.join(", ")}. Maximum {MAX_MB} MB per file. Uploaded
              content is never executed.
            </p>
            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              <Button
                variant="primary"
                icon={busy ? <Loader2 size={15} className="animate-spin" /> : <FileUp size={15} />}
                onClick={() => inputRef.current?.click()}
                disabled={busy}
              >
                {busy ? "Processing…" : "Choose files"}
              </Button>
              <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-muted">
                <input
                  type="checkbox"
                  checked={autoParse}
                  onChange={(event) => setAutoParse(event.target.checked)}
                  className="h-4 w-4 rounded border-line-strong bg-surface text-accent"
                />
                Parse after upload
              </label>
            </div>
            <input
              ref={inputRef}
              type="file"
              multiple
              className="hidden"
              accept={SUPPORTED.join(",")}
              onChange={(event) => {
                if (event.target.files) void handleFiles(event.target.files);
                event.target.value = "";
              }}
            />
          </div>
        </CardBody>
      </Card>

      <Card className="mt-5">
        <CardHeader
          title="Upload results"
          subtitle="Per-file hash, parser status and extraction summary"
        />
        {results.length === 0 ? (
          <CardBody>
            <EmptyState
              title="No files processed yet"
              description="Drop evidence above to see hashes and parser output."
              icon={FileUp}
            />
          </CardBody>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>File</TH>
                <TH>Size</TH>
                <TH>SHA-256</TH>
                <TH>Status</TH>
                <TH>Parser</TH>
                <TH>Events / findings</TH>
                <TH>Actions</TH>
              </TR>
            </THead>
            <TBody>
              {results.map((result, index) => (
                <TR key={`${result.filename}-${index}`}>
                  <TD className="font-medium text-primary">{result.filename}</TD>
                  <TD>
                    {result.evidence ? formatBytes(result.evidence.size_bytes) : "—"}
                  </TD>
                  <TD className="font-mono text-[11px] text-muted">
                    {result.evidence ? (
                      <button
                        type="button"
                        onClick={() => void copyHash(result.evidence!.sha256)}
                        className="inline-flex items-center gap-1 hover:text-accent"
                        title="Copy full SHA-256"
                      >
                        {shortHash(result.evidence.sha256)}
                        <Copy size={11} />
                      </button>
                    ) : (
                      "—"
                    )}
                  </TD>
                  <TD>
                    {result.error ? (
                      <Badge className="border-rose-300 dark:border-rose-500/40 bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-200">
                        <XCircle size={11} /> Error
                      </Badge>
                    ) : result.parse ? (
                      <Badge className="border-emerald-300 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200">
                        <CheckCircle2 size={11} /> {humanize(result.parse.status)}
                      </Badge>
                    ) : (
                      <Badge className="border-accent/40 bg-accent/10 text-accent">
                        Uploaded
                      </Badge>
                    )}
                  </TD>
                  <TD className="text-xs text-muted">
                    {result.parse?.parser_name ?? result.evidence?.parser_name ?? "—"}
                  </TD>
                  <TD className="text-xs text-muted">
                    {result.parse
                      ? `${result.parse.events_created} / ${result.parse.findings_created}`
                      : "—"}
                  </TD>
                  <TD>
                    {result.evidence ? (
                      <div className="flex flex-wrap gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<ShieldCheck size={12} />}
                          onClick={() => void verifyFile(result.evidence!)}
                        >
                          Verify
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            parse.mutate(
                              { evidenceId: result.evidence!.id, reparse: Boolean(result.parse) },
                              {
                                onSuccess: (parsed) =>
                                  setResults((current) =>
                                    current.map((item, itemIndex) =>
                                      itemIndex === index ? { ...item, parse: parsed } : item,
                                    ),
                                  ),
                                onError: (error) =>
                                  toast.push("error", "Parse failed", error.message),
                              },
                            )
                          }
                        >
                          {result.parse ? "Reparse" : "Parse"}
                        </Button>
                      </div>
                    ) : null}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      {results.some((result) => result.parse?.warnings?.length) ? (
        <Card className="mt-5 border-amber-200 dark:border-amber-500/20">
          <CardHeader title="Parser warnings" subtitle="Preserved as provenance, not hidden" />
          <CardBody className="space-y-2">
            {results.flatMap((result) =>
              (result.parse?.warnings ?? []).map((warning, warningIndex) => (
                <p
                  key={`${result.filename}-${warningIndex}`}
                  className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 px-3 py-2 text-xs text-amber-800/80 dark:text-amber-100/80"
                >
                  <span className="font-medium">{result.filename}:</span> {warning}
                </p>
              )),
            )}
          </CardBody>
        </Card>
      ) : null}

      <p className="mt-4 text-[10px] leading-relaxed text-muted">
        SHA-256 verification proves that a stored file matches the digest recorded at intake. It
        does not prove that the file was authentic before acquisition. Always verify against the
        original source and document custody.
      </p>
    </div>
  );
}
