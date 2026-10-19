import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import {
  ApiError,
  accessGateRequired,
  api,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

type GateState = "locked" | "checking" | "open";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "That access code was not accepted.";
    return error.message;
  }
  if (error instanceof TypeError) {
    return "Could not reach the demo API. It may be waking up; try again.";
  }
  return "Could not verify the access code.";
}

export function AccessGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GateState>(() => {
    if (!accessGateRequired()) return "open";
    return getAccessToken() ? "checking" : "locked";
  });
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (state !== "checking") return;
    let cancelled = false;
    api
      .listCases()
      .then(() => {
        if (cancelled) return;
        setError(null);
        setState("open");
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        clearAccessToken();
        setError(messageFor(reason));
        setState("locked");
      });
    return () => {
      cancelled = true;
    };
  }, [state]);

  if (state === "open") return <>{children}</>;

  if (state === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-app px-4 py-10 text-primary">
        <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-8 text-center shadow-card">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 text-accent">
            <Loader2 size={22} className="animate-spin" />
          </div>
          <h1 className="mt-5 text-lg font-semibold">Waking the demo</h1>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Checking your access code. The free API tier can take up to a minute to
            wake up after a period of inactivity.
          </p>
        </div>
      </div>
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = code.trim();
    if (!value) {
      setError("Enter the access code.");
      return;
    }
    setError(null);
    setAccessToken(value);
    setState("checking");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-app px-4 py-10 text-primary">
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-7 shadow-card">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent">
            <ShieldCheck size={20} />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-[0.16em] text-primary">
              Red Thread
            </p>
            <p className="text-[10px] uppercase tracking-wider text-muted">
              Restricted investigation demo
            </p>
          </div>
        </div>

        <h1 className="mt-6 text-xl font-semibold">Enter the access code</h1>
        <p className="mt-2 text-xs leading-relaxed text-muted">
          The access code protects the case data and the AI quota. It is a shared
          demo gate, not a user account. Ask the investigator for the code.
        </p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-3">
          <label
            htmlFor="red-thread-access-code"
            className="block text-[10px] font-semibold uppercase tracking-wider text-muted"
          >
            Access code
          </label>
          <div className="relative">
            <KeyRound
              size={15}
              className="pointer-events-none absolute left-3 top-3 text-muted"
            />
            <Input
              id="red-thread-access-code"
              type="password"
              value={code}
              onChange={(event) => {
                setCode(event.target.value);
                if (error) setError(null);
              }}
              autoComplete="current-password"
              autoFocus
              className="pl-9"
              aria-invalid={Boolean(error)}
            />
          </div>
          {error ? (
            <p
              role="alert"
              className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200"
            >
              {error}
            </p>
          ) : null}
          <Button type="submit" variant="primary" className="w-full" icon={<KeyRound size={15} />}>
            Unlock demo
          </Button>
        </form>

        <p className="mt-4 text-[10px] leading-relaxed text-muted">
          The API may take up to a minute to wake up on the free tier. The
          deterministic analysis, evidence vault and reports work without AI.
        </p>
      </div>
    </div>
  );
}
