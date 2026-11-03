import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertTriangle,
  Bot,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useAiStatus, useAskAi } from "@/hooks/useApi";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import type { AiAnswer } from "@/types";

interface ChatMessage {
  id: number;
  role: "investigator" | "assistant";
  content: string;
  answer?: AiAnswer;
}

const SUGGESTIONS = [
  "Summarize the evidence in this case without drawing conclusions.",
  "Explain the amount discrepancy between the screenshot and the transaction ledger.",
  "Which identifiers appear in more than one evidence source?",
  "What investigative questions remain unanswered by the current evidence?",
];

export function AiAssistantPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const statusQuery = useAiStatus();
  const askAi = useAskAi(caseId ?? "");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  if (!caseId) return <ErrorState title="Missing case ID" />;
  if (statusQuery.isLoading) return <LoadingState label="Checking AI configuration…" />;
  if (statusQuery.error)
    return <ErrorState message={statusQuery.error.message} onRetry={() => statusQuery.refetch()} />;

  const status = statusQuery.data;

  async function send() {
    const trimmed = question.trim();
    if (!trimmed || askAi.isPending) return;
    setError(null);
    const userMessage: ChatMessage = {
      id: Date.now(),
      role: "investigator",
      content: trimmed,
    };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    try {
      const answer = await askAi.mutateAsync({ question: trimmed });
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: answer.answer,
          answer,
        },
      ]);
    } catch (mutationError) {
      const message = mutationError instanceof Error ? mutationError.message : "AI request failed";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          id: Date.now() + 2,
          role: "assistant",
          content:
            "The AI service could not produce an answer. The deterministic investigation data remains available and unchanged.",
        },
      ]);
    }
  }

  if (!status?.configured) {
    return (
      <div>
        <PageHeader
          eyebrow="AI investigation assistant"
          title="AI assistance is not configured"
          description="Red Thread's deterministic pipeline remains fully functional without AI. Configure a provider only if your evidence handling policy permits sending selected excerpts to an external API."
        />
        <Card className="border-amber-200 dark:border-amber-500/20">
          <CardHeader
            title="Configuration required"
            subtitle="The assistant will not fabricate an answer when no provider is available."
          />
          <CardBody className="space-y-4 text-xs leading-relaxed text-muted">
            <div className="rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 p-4 text-amber-800/80 dark:text-amber-100/80">
              <AlertTriangle size={15} className="mr-1 inline" />
              Only send evidence to an external provider if you are authorized to do so. Use the
              minimum necessary excerpts and review the provider's data-handling terms.
            </div>
            <div>
              <p className="mb-1 font-medium text-secondary">CommandCode route</p>
              <pre className="rounded-lg border border-line bg-surface-2/60 p-3 font-mono text-[10px] text-secondary">
{`COMMANDCODE_API_KEY=your_key_here
COMMANDCODE_BASE_URL=https://api.commandcode.ai/provider/v1
COMMANDCODE_MODEL=deepseek/deepseek-v4.1-flash
AI_PROVIDER=auto`}
              </pre>
            </div>
            <div>
              <p className="mb-1 font-medium text-secondary">TokenHarbor route</p>
              <pre className="rounded-lg border border-line bg-surface-2/60 p-3 font-mono text-[10px] text-secondary">
{`TOKENHARBOR_API_KEY=your_key_here
TOKENHARBOR_BASE_URL=https://tokenharbor.ai/v1
TOKENHARBOR_MODEL=deepseek-v4.1-flash:free`}
              </pre>
            </div>
            <p>
              Both routes serve <strong className="text-secondary">DeepSeek V4.1 Flash</strong>;
              the route only determines the API endpoint. Add the values to{" "}
              <code className="text-accent">backend/.env</code>, restart the backend, and reload
              this page. Never commit a real key or place it in a frontend environment variable.
            </p>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="AI investigation assistant"
        title="Evidence-grounded questions"
        description="Answers are generated from retrieved case records. Citations are validated against stored evidence IDs and source locators before display."
        actions={
          <Button
            variant="secondary"
            icon={<Trash2 size={14} />}
            onClick={() => setMessages([])}
          >
            Clear conversation
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-violet-200 dark:border-violet-500/20 bg-violet-50/80 dark:bg-violet-500/5 px-4 py-3 text-xs text-violet-800/80 dark:text-violet-100/80">
        <Sparkles size={14} />
        Model: <strong>{status.model_label ?? status.model}</strong>
        <span className="text-violet-700/70 dark:text-violet-200/60">
          · external provider: <span className="font-mono text-[11px]">{status.provider}</span> ·
          selected evidence excerpts will be sent to that provider.
        </span>
      </div>

      <Card>
        <CardHeader
          title="Conversation"
          subtitle="AI output is an interpretation, not evidence. Validate every citation."
        />
        <CardBody className="min-h-[420px] space-y-4">
          {messages.length === 0 ? (
            <EmptyState
              title="Ask a question about this case"
              description="The assistant retrieves relevant stored events, findings and evidence metadata. It is instructed not to invent identifiers or citations."
              icon={Bot}
              action={
                <div className="flex max-w-2xl flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => setQuestion(suggestion)}
                      className="rounded-lg border border-line-strong bg-surface/60 px-3 py-2 text-left text-[11px] text-secondary hover:border-accent/30 hover:text-accent"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              }
            />
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === "investigator" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-3xl rounded-2xl border px-4 py-3 ${
                    message.role === "investigator"
                      ? "border-accent/20 bg-accent/10 text-primary"
                      : "border-line bg-surface-2/60 text-secondary"
                  }`}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <Badge
                      className={
                        message.role === "investigator"
                          ? "border-accent/30 bg-accent/10 text-accent"
                          : "border-violet-300 dark:border-violet-500/30 bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-200"
                      }
                    >
                      {message.role === "investigator" ? "Investigator" : "AI-generated"}
                    </Badge>
                    {message.answer ? (
                      <span
                        className="text-[10px] font-medium text-secondary"
                        title={`Served via ${message.answer.provider}`}
                      >
                        {message.answer.model_label ?? message.answer.model}
                      </span>
                    ) : null}
                  </div>
                  <p className="whitespace-pre-line text-sm leading-relaxed">{message.content}</p>

                  {message.answer?.insufficient_evidence ? (
                    <p className="mt-3 rounded-lg border border-amber-200 dark:border-amber-500/20 bg-amber-50/80 dark:bg-amber-500/5 p-2 text-[11px] text-amber-800/80 dark:text-amber-100/80">
                      <ShieldAlert size={12} className="mr-1 inline" />
                      The stored evidence is insufficient to answer this question fully.
                    </p>
                  ) : null}

                  {message.answer?.citations?.length ? (
                    <div className="mt-3">
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
                        Citations
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {message.answer.citations.map((citation, index) => (
                          <span
                            key={`${citation.id ?? citation.evidence_id ?? citation.event_id ?? index}`}
                            className={`rounded-md border px-2 py-1 font-mono text-[10px] ${
                              citation.verified
                                ? "border-emerald-300 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
                                : "border-amber-300 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-200"
                            }`}
                            title={citation.source_locator ?? citation.warning ?? undefined}
                          >
                            {citation.evidence_id ?? citation.event_id ?? citation.label ?? "reference"}
                            {citation.source_locator ? `:${citation.source_locator}` : ""} ·{" "}
                            {citation.verified ? "verified" : "unverified"}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {message.answer?.uncertainties?.length ? (
                    <div className="mt-3 text-[11px] leading-relaxed text-amber-800/80 dark:text-amber-100/70">
                      <p className="font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400/80">
                        Uncertainties
                      </p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-4">
                        {message.answer.uncertainties.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {message.answer?.alternative_explanations?.length ? (
                    <div className="mt-3 text-[11px] leading-relaxed text-muted">
                      <p className="font-semibold uppercase tracking-wider text-muted">
                        Alternative explanations
                      </p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-4">
                        {message.answer.alternative_explanations.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {message.answer?.suggested_next_steps?.length ? (
                    <div className="mt-3 text-[11px] leading-relaxed text-muted">
                      <p className="font-semibold uppercase tracking-wider text-muted">
                        Suggested next steps
                      </p>
                      <ul className="mt-1 list-disc space-y-0.5 pl-4">
                        {message.answer.suggested_next_steps.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </div>
            ))
          )}

          {askAi.isPending ? (
            <div className="flex items-center gap-2 text-xs text-violet-600 dark:text-violet-300">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
              Retrieving evidence and waiting for the provider…
            </div>
          ) : null}

          {error ? (
            <p className="rounded-lg border border-rose-200 dark:border-rose-500/20 bg-rose-50/80 dark:bg-rose-500/5 p-3 text-xs text-rose-700 dark:text-rose-200">
              {error}
            </p>
          ) : null}
        </CardBody>

        <div className="border-t border-line p-4">
          <div className="flex items-end gap-2">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
              rows={2}
              placeholder="Ask about the evidence, findings, timeline or relationships…"
              className="min-h-[52px] flex-1 resize-none rounded-lg border border-line-strong bg-surface-2/60 px-3 py-2 text-sm text-primary placeholder:text-muted focus:border-accent focus:outline-none"
            />
            <Button
              variant="primary"
              icon={<Send size={14} />}
              onClick={() => void send()}
              loading={askAi.isPending}
              disabled={!question.trim()}
            >
              Send
            </Button>
          </div>
          <p className="mt-2 text-[10px] text-muted">
            Do not treat AI-generated content as a finding, a legal conclusion, or proof of
            criminal activity. Human review is mandatory.
          </p>
        </div>
      </Card>
    </div>
  );
}
