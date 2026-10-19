import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderOpen, Plus, ShieldCheck } from "lucide-react";
import { useCaseContext } from "@/context/CaseContext";
import { useCreateCase } from "@/hooks/useApi";
import { useToast } from "@/components/ui/Toast";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { Modal } from "@/components/ui/Modal";
import { Input, Label, Textarea } from "@/components/ui/Field";
import { formatDate, humanize } from "@/lib/format";

export function CasesPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { cases, isLoading, error, selectedCaseId, setSelectedCaseId } = useCaseContext();
  const createCase = useCreateCase();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    createCase.mutate(
      { title: title.trim(), description, investigator_notes: notes },
      {
        onSuccess: (created) => {
          toast.push("success", "Case created", `${created.title} is ready for evidence.`);
          setSelectedCaseId(created.id);
          setOpen(false);
          setTitle("");
          setDescription("");
          setNotes("");
          navigate(`/cases/${created.id}`);
        },
        onError: (mutationError) => {
          toast.push("error", "Could not create case", mutationError.message);
        },
      },
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="Investigation cases"
        description="Each case is an isolated evidence vault with its own events, findings, graph and reports."
        actions={
          <Button variant="primary" icon={<Plus size={15} />} onClick={() => setOpen(true)}>
            New case
          </Button>
        }
      />

      {isLoading ? <LoadingState label="Loading cases…" /> : null}
      {error ? <ErrorState message={error.message} /> : null}

      {!isLoading && !error && cases.length === 0 ? (
        <EmptyState
          title="No cases yet"
          description="Create a case to group evidence, extracted events, findings and reports."
          icon={FolderOpen}
          action={
            <Button variant="primary" icon={<Plus size={15} />} onClick={() => setOpen(true)}>
              Create your first case
            </Button>
          }
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {cases.map((item) => (
          <Card key={item.id} className="flex flex-col">
            <CardHeader
              title={item.title}
              subtitle={`Created ${formatDate(item.created_at)}`}
              action={
                <Badge
                  className={
                    item.status === "closed"
                      ? "border-line-strong bg-surface-2 text-muted"
                      : item.status === "in_review"
                        ? "border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-200"
                        : "border-accent/40 bg-accent/10 text-accent"
                  }
                >
                  {humanize(item.status)}
                </Badge>
              }
            />
            <CardBody className="flex flex-1 flex-col justify-between gap-4">
              <p className="line-clamp-3 min-h-[3rem] text-xs leading-relaxed text-muted">
                {item.description || "No description supplied."}
              </p>
              <div className="grid grid-cols-4 gap-2 text-center">
                <Metric label="Evidence" value={item.evidence_count} />
                <Metric label="Events" value={item.event_count} />
                <Metric label="Findings" value={item.finding_count} />
                <Metric label="Open" value={item.open_finding_count} />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  className="flex-1"
                  variant={item.id === selectedCaseId ? "primary" : "secondary"}
                  icon={<ShieldCheck size={14} />}
                  onClick={() => {
                    setSelectedCaseId(item.id);
                    navigate(`/cases/${item.id}`);
                  }}
                >
                  {item.id === selectedCaseId ? "Active case" : "Open case"}
                </Button>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create investigation case"
        description="The case starts empty. Evidence and derived data are stored separately by case ID."
      >
        <form className="space-y-4" onSubmit={submit}>
          <div>
            <Label htmlFor="case-title">Case title</Label>
            <Input
              id="case-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Operation PhishTrace"
              autoFocus
            />
          </div>
          <div>
            <Label htmlFor="case-description">Description</Label>
            <Textarea
              id="case-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What is being investigated? Include the incident context."
            />
          </div>
          <div>
            <Label htmlFor="case-notes">Investigator notes</Label>
            <Textarea
              id="case-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Authorization, scope, or handling notes."
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={createCase.isPending}>
              Create case
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-surface-2/40 px-2 py-2">
      <p className="text-base font-semibold text-primary">{value}</p>
      <p className="text-[9px] uppercase tracking-wider text-muted">{label}</p>
    </div>
  );
}
