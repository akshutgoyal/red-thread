import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Columns3, Save } from "lucide-react";
import { api } from "@/api/client";
import { useSaveColumnMapping } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/States";
import type { ColumnMappingResponse, Evidence } from "@/types";

/**
 * Map a CSV/JSON file's columns onto the fields the parser understands.
 *
 * The preview is read-only and shows sample rows so the investigator can
 * confirm the guess before it changes how the file is parsed. Saving the
 * mapping never modifies the stored bytes.
 */
export function ColumnMappingPanel({
  caseId,
  evidence,
}: {
  caseId: string;
  evidence: Evidence;
}) {
  const toast = useToast();
  const save = useSaveColumnMapping(caseId);
  const [preview, setPreview] = useState<ColumnMappingResponse | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getColumnMapping(caseId, evidence.id)
      .then((result) => {
        if (cancelled) return;
        setPreview(result);
        const initial: Record<string, string> = {};
        for (const [key, value] of Object.entries(result.saved_mapping ?? {})) {
          if (value) initial[key] = value;
        }
        if (Object.keys(initial).length === 0) {
          for (const [key, value] of Object.entries(result.suggested ?? {})) {
            if (value) initial[key] = value;
          }
        }
        setValues(initial);
      })
      .catch((caught: Error) => {
        if (!cancelled) setError(caught.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, evidence.id]);

  const hasTimestamp = Boolean(values.timestamp);

  const sampleRow = useMemo(() => preview?.rows?.[0] ?? null, [preview]);

  return (
    <Card>
      <CardHeader
        title="Column mapping"
        subtitle="Tell the parser which column holds each value. The stored file is never modified."
      />
      <CardBody className="space-y-3">
        {loading ? (
          <p className="text-xs text-muted">Reading file header…</p>
        ) : error ? (
          <p className="text-xs text-rose-600 dark:text-rose-300">{error}</p>
        ) : !preview ? (
          <EmptyState title="Mapping unavailable" description="Could not read this file." />
        ) : !preview.supported ? (
          <p className="rounded-lg border border-line bg-surface-2/40 px-3 py-2 text-xs leading-relaxed text-muted">
            <Columns3 size={12} className="mr-1 inline" />
            {preview.reason}
          </p>
        ) : (
          <>
            <div className="grid gap-2 sm:grid-cols-2">
              {preview.fields.map((field) => (
                <label key={field.key} className="block">
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-muted">
                    {field.label}
                    {field.required ? <span className="text-rose-500"> *</span> : null}
                  </span>
                  <Select
                    value={values[field.key] ?? ""}
                    onChange={(event) =>
                      setValues((current) => {
                        const next = { ...current };
                        if (event.target.value) next[field.key] = event.target.value;
                        else delete next[field.key];
                        return next;
                      })
                    }
                    className="w-full text-xs"
                  >
                    <option value="">Not mapped</option>
                    {preview.headers.map((header) => (
                      <option key={header} value={header}>
                        {header}
                      </option>
                    ))}
                  </Select>
                </label>
              ))}
            </div>

            {!hasTimestamp ? (
              <p className="rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2 text-[11px] leading-relaxed text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-100/80">
                <AlertTriangle size={11} className="mr-1 inline" />
                Choose a timestamp column. Without one the records cannot be placed on
                the timeline.
              </p>
            ) : null}

            {sampleRow ? (
              <div>
                <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
                  Sample row
                </p>
                <div className="overflow-x-auto rounded-lg border border-line bg-surface-2/40 p-2">
                  <table className="min-w-full text-[10px]">
                    <thead>
                      <tr>
                        {Object.keys(sampleRow).map((key) => (
                          <th
                            key={key}
                            className="whitespace-nowrap px-2 py-1 text-left font-semibold text-secondary"
                          >
                            {key}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        {Object.entries(sampleRow).map(([key, value]) => (
                          <td
                            key={key}
                            className="max-w-[220px] truncate px-2 py-1 font-mono text-muted"
                          >
                            {value}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="primary"
                icon={<Save size={13} />}
                disabled={!hasTimestamp || save.isPending}
                loading={save.isPending}
                onClick={() =>
                  save.mutate(
                    { evidenceId: evidence.id, mapping: values },
                    {
                      onSuccess: () => {
                        toast.push(
                          "success",
                          "Mapping saved",
                          "Reparse the file to apply the new column mapping.",
                        );
                        setPreview((current) =>
                          current ? { ...current, saved_mapping: values } : current,
                        );
                      },
                      onError: (mutationError: Error) =>
                        toast.push("error", "Could not save mapping", mutationError.message),
                    },
                  )
                }
              >
                Save mapping
              </Button>
              <p className="text-[10px] leading-relaxed text-muted">
                Saving only affects how the file is read. Reparse the evidence to rebuild
                events.
              </p>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
