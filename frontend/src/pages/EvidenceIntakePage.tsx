import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Copy,
  FileUp,
  HelpCircle,
  Loader2,
  ShieldCheck,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useGuidance, useParseEvidence, useUploadEvidence, useVerifyEvidence } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageGuide } from "@/components/guidance/PageGuide";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { copyText, formatBytes, shortHash } from "@/lib/format";
import type { Evidence, ParseResponse, WarningDetail } from "@/types";

const SUPPORTED = [
  ".csv",
  ".json",
  ".jsonl",
  ".txt",
  ".log",
  ".pdf",
  ".eml",
  ".png",
  ".jpg",
  ".jpeg",
  ".gpx",
  ".kml",
];
const MAX_MB = 50;

interface UploadResult {
  evidence?: Evidence;
  parse?: ParseResponse;
  error?: string;
  filename: string;
}

type StageState = "done" | "active" | "pending" | "failed";

/** Derive the visible processing stages from what actually happened for this file. */
function fileStages(result: UploadResult): { label: string; state: StageState }[] {
  const uploaded = Boolean(result.evidence);
  const parsed = Boolean(result.parse);
  const failed = Boolean(result.error) && !parsed;
  const hasWarnings = (result.parse?.warnings?.length ?? 0) > 0;
  return [
    { label: "Uploaded", state: uploaded ? "done" : failed ? "failed" : "pending" },
    { label: "Hash generated", state: uploaded ? "done" : "pending" },
    {
      label: "Parsing",
      state: parsed ? "done" : uploaded ? (failed ? "failed" : "active") : "pending",
    },
    {
      label: parsed ? (hasWarnings ? "Partially parsed" : "Successfully parsed") : "Parse result",
      state: parsed ? "done" : failed ? "failed" : "pending",
    },
    {
      label: "Needs review",
      state: hasWarnings ? "active" : parsed ? "done" : "pending",
    },
  ];
}

function StageIcon({ state }: { state: StageState }) {
  if (state === "done") return <CheckCircle2 size={12} className="text-emerald-500" />;
  if (state === "active") return <Loader2 size={12} className="text-accent" />;
  if (state === "failed") return <XCircle size={12} className="text-rose-500" />;
  return <Circle size={12} className="text-muted" />;
}

export function EvidenceIntakePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const guidanceQuery = useGuidance(caseId);
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
          {
            filename: file.name,
            error: `Unsupported file type ${extension || "(none)"}. Supported types: ${SUPPORTED.join(", ")}.`,
          },
        ]);
        toast.push(
          "error",
          "Unsupported file",
          `${file.name} is not a supported evidence type.`,
        );
        continue;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        setResults((current) => [
          ...current,
          { filename: file.name, error: `File exceeds the ${MAX_MB} MB upload limit.` },
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
              parsed.warnings.length > 0 ? "Parsed with warnings" : "Evidence parsed",
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

  const totalRecords = results.reduce(
    (sum, result) => sum + (result.parse?.records_extracted ?? 0),
    0,
  );
  const rejectedRecords = results.reduce(
    (sum, result) => sum + (result.parse?.records_rejected ?? 0),
    0,
  );
  const warningResults = results.filter((result) => (result.parse?.warnings.length ?? 0) > 0);

  return (
    <div>
      <PageHeader
        eyebrow="Step 2 · Upload evidence"
        title="Preserve and process evidence"
        description="Each file is hashed, parsed into events, and kept unchanged. You can see exactly what was extracted, what was skipped, and what needs your attention."
        actions={
          <Link to={`/cases/${caseId}/evidence`}>
            <Button variant="secondary">Open evidence vault</Button>
          </Link>
        }
      />

      <PageGuide page="evidence-intake" caseId={caseId ?? ""} guidance={guidanceQuery.data} />

      <div
        data-tour="warning-panel"
        className="mb-4 rounded-xl border border-line bg-surface-2/40 px-4 py-3 text-xs leading-relaxed text-secondary"
      >
        <p className="font-semibold text-primary">How warnings work</p>
        <p className="mt-1 text-muted">
          When a file cannot be read completely, the parser records a warning here saying what
          happened, why it matters, what to do, and whether the file is still usable. Warnings
          never block the rest of the file.
        </p>
      </div>

      <div className="mb-4 grid gap-2 rounded-xl border border-line bg-surface-2/40 px-4 py-3 text-xs leading-relaxed text-muted sm:grid-cols-3">
        <p>
          <span className="font-semibold text-secondary">What this does: </span>
          uploads a file, records its SHA-256 digest, and extracts events.
        </p>
        <p>
          <span className="font-semibold text-secondary">Why it matters: </span>
          every later finding must trace back to one of these source files.
        </p>
        <p>
          <span className="font-semibold text-secondary">What's next: </span>
          review parsed events on the timeline.
        </p>
      </div>

      <Card>
        <CardBody>
          <div
            data-tour="evidence-dropzone"
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
                icon={
                  busy ? <Loader2 size={15} className="animate-spin" /> : <FileUp size={15} />
                }
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
          title="Processing status"
          subtitle={
            results.length > 0
              ? `${results.length} file(s) · ${totalRecords} record(s) extracted${
                  rejectedRecords ? ` · ${rejectedRecords} rejected` : ""
                }`
              : "Each file shows its own progress"
          }
        />
        <CardBody className="space-y-3" data-tour="evidence-pipeline">
          {results.length === 0 ? (
            <EmptyState
              title="No files processed yet"
              description="Drop evidence above to see each file's hashing, parsing result and any warnings."
              icon={FileUp}
            />
          ) : (
            results.map((result, index) => (
              <div
                key={`${result.filename}-${index}`}
                className="rounded-xl border border-line bg-surface-2/30 p-3.5"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-primary">{result.filename}</p>
                    <p className="mt-0.5 text-[11px] text-muted">
                      {result.evidence ? formatBytes(result.evidence.size_bytes) : "—"}
                      {result.evidence ? " · " : ""}
                      {result.evidence ? (
                        <button
                          type="button"
                          onClick={() => void copyHash(result.evidence!.sha256)}
                          className="inline-flex items-center gap-1 font-mono hover:text-accent"
                          title="Copy full SHA-256"
                        >
                          SHA-256 {shortHash(result.evidence.sha256)}
                          <Copy size={10} />
                        </button>
                      ) : null}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {result.evidence ? (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<ShieldCheck size={12} />}
                          onClick={() => void verifyFile(result.evidence!)}
                        >
                          Verify integrity
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            parse.mutate(
                              {
                                evidenceId: result.evidence!.id,
                                reparse: Boolean(result.parse),
                              },
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
                      </>
                    ) : null}
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  {fileStages(result).map((stage, stageIndex) => (
                    <span
                      key={stage.label}
                      className="inline-flex items-center gap-1.5 text-[11px] text-muted"
                    >
                      <StageIcon state={stage.state} />
                      {stage.label}
                      {stageIndex < 4 ? (
                        <span className="text-line-strong" aria-hidden="true">
                          →
                        </span>
                      ) : null}
                    </span>
                  ))}
                </div>

                {result.error ? (
                  <div className="mt-2.5 rounded-lg border border-rose-200 bg-rose-50/80 px-3 py-2 text-[11px] leading-relaxed text-rose-800 dark:border-rose-500/20 dark:bg-rose-500/5 dark:text-rose-100/80">
                    <span className="font-semibold">Could not process this file: </span>
                    {result.error}
                    <span className="mt-1 block">
                      The original file is unchanged. Fix the issue above and retry, or upload
                      a different export.
                    </span>
                  </div>
                ) : null}

                {result.parse ? (
                  <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11px] text-muted">
                    <Badge className="border-line-strong bg-surface-2/70 text-secondary">
                      {result.parse.parser_name} {result.parse.parser_version}
                    </Badge>
                    <span>
                      {result.parse.events_created} event(s) ·{" "}
                      {result.parse.findings_created} finding(s)
                    </span>
                    {result.parse.records_extracted !== undefined &&
                    result.parse.records_extracted !== null ? (
                      <span>· {result.parse.records_extracted} record(s) read</span>
                    ) : null}
                    {result.parse.records_rejected ? (
                      <span className="text-amber-600 dark:text-amber-400">
                        · {result.parse.records_rejected} rejected
                      </span>
                    ) : null}
                    <Link
                      to={`/cases/${caseId}/events?evidenceId=${result.evidence?.id ?? ""}`}
                      className="text-accent hover:text-accent-strong"
                    >
                      Review extracted events
                    </Link>
                  </div>
                ) : null}

                {(result.parse?.warning_details?.length ?? 0) > 0 ? (
                  <ul className="mt-2.5 space-y-2">
                    {(result.parse?.warning_details ?? []).map((detail, detailIndex) => (
                      <WarningItem
                        key={`${result.filename}-w-${detailIndex}`}
                        detail={detail}
                      />
                    ))}
                  </ul>
                ) : (result.parse?.warnings.length ?? 0) > 0 ? (
                  <ul className="mt-2.5 space-y-1.5">
                    {(result.parse?.warnings ?? []).map((warning, warningIndex) => (
                      <li
                        key={`${result.filename}-w-${warningIndex}`}
                        className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-[11px] text-amber-800/80 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80"
                      >
                        <AlertTriangle size={11} className="mr-1 inline" />
                        {warning}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))
          )}
        </CardBody>
      </Card>

      {warningResults.length > 0 ? (
        <Card className="mt-5">
          <CardHeader
            title="Files that need your attention"
            subtitle="What happened, why it matters, and what you can do"
          />
          <CardBody className="space-y-3">
            {warningResults.map((result) => (
              <div key={`attention-${result.filename}`}>
                <p className="mb-2 text-xs font-medium text-primary">{result.filename}</p>
                <ul className="space-y-2">
                  {(result.parse?.warning_details ?? []).length > 0
                    ? (result.parse?.warning_details ?? []).map((detail, index) => (
                        <WarningItem
                          key={`${result.filename}-att-${index}`}
                          detail={detail}
                        />
                      ))
                    : (result.parse?.warnings ?? []).map((warning, index) => (
                        <li
                          key={`${result.filename}-att-legacy-${index}`}
                          className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-[11px] text-amber-800/80 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80"
                        >
                          {warning}
                        </li>
                      ))}
                </ul>
              </div>
            ))}
          </CardBody>
        </Card>
      ) : null}

      <p className="mt-4 text-[10px] leading-relaxed text-muted">
        SHA-256 verification proves a stored file matches the digest recorded at intake. It
        does not prove the file was authentic before acquisition. Verify against the original
        source and document custody.
      </p>
    </div>
  );
}

function WarningItem({ detail }: { detail: WarningDetail }) {
  return (
    <li className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-[11px] leading-relaxed text-amber-900/80 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80">
      <p className="font-medium">
        <AlertTriangle size={11} className="mr-1 inline" />
        {detail.message}
      </p>
      <dl className="mt-1 space-y-0.5">
        {detail.impact ? (
          <div>
            <dt className="inline font-semibold">Why it matters: </dt>
            <dd className="inline">{detail.impact}</dd>
          </div>
        ) : null}
        {detail.recommendation ? (
          <div>
            <dt className="inline font-semibold">What you can do: </dt>
            <dd className="inline">{detail.recommendation}</dd>
          </div>
        ) : null}
        <div className="flex items-center gap-1">
          <HelpCircle size={10} />
          <span>
            {detail.can_use
              ? "This file can still be used; affected records are flagged."
              : "This file may not contribute usable events until corrected."}
          </span>
        </div>
        {detail.source_locator ? (
          <div className="font-mono text-[10px] opacity-70">{detail.source_locator}</div>
        ) : null}
      </dl>
    </li>
  );
}
