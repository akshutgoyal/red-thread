import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/States";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const GOOGLE_SCRIPT_ID = "google-identity-services";

export function LoginPage() {
  const { user, isLoading, loginGoogle, loginDemo } = useAuth();
  const navigate = useNavigate();
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [navigate, user]);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || user) return;
    let cancelled = false;

    function initializeGoogle() {
      const google = window.google;
      const container = googleButtonRef.current;
      if (!google || !container || cancelled || !GOOGLE_CLIENT_ID) return;
      google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response) => {
          if (!response.credential) {
            setError("Google returned an empty credential.");
            return;
          }
          setBusy(true);
          setError(null);
          loginGoogle(response.credential)
            .then(() => navigate("/", { replace: true }))
            .catch((loginError: Error) => setError(loginError.message))
            .finally(() => setBusy(false));
        },
      });
      google.accounts.id.renderButton(container, {
        type: "standard",
        theme: "outline",
        size: "large",
        shape: "pill",
        text: "continue_with",
        width: 320,
      });
    }

    const existing = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    if (window.google) {
      initializeGoogle();
      return () => {
        cancelled = true;
      };
    }
    if (existing) {
      existing.addEventListener("load", initializeGoogle, { once: true });
      return () => {
        cancelled = true;
        existing.removeEventListener("load", initializeGoogle);
      };
    }
    const script = document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.addEventListener("load", initializeGoogle, { once: true });
    script.addEventListener("error", () => setError("Could not load Google sign-in."), { once: true });
    document.head.appendChild(script);
    return () => {
      cancelled = true;
      script.removeEventListener("load", initializeGoogle);
    };
  }, [loginGoogle, navigate, user, isLoading]);

  async function handleDemo() {
    setBusy(true);
    setError(null);
    try {
      await loginDemo();
      navigate("/", { replace: true });
    } catch (demoError) {
      setError((demoError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) return <LoadingState label="Opening Red Thread…" />;
  if (user) return <Navigate to="/" replace />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-app px-4 py-10 text-primary">
      <div className="pointer-events-none fixed inset-0 app-aurora" />
      <Card className="relative w-full max-w-md overflow-hidden">
        <CardBody className="p-8 sm:p-10">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent">
              <ShieldCheck size={22} />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-[0.16em]">Red Thread</p>
              <p className="text-[10px] uppercase tracking-wider text-muted">
                Forensic investigation
              </p>
            </div>
          </div>

          <h1 className="mt-8 text-2xl font-semibold tracking-tight">Open your workspace</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Sign in with Google to access your cases. New accounts start empty—create a
            case to enable the investigation tools. You can also explore the synthetic
            demo with full interaction.
          </p>

          <div className="mt-7">
            {GOOGLE_CLIENT_ID ? (
              <div ref={googleButtonRef} className="flex min-h-[44px] justify-center" />
            ) : (
              <div className="rounded-xl border border-amber-300/60 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
                Google sign-in is not configured. Set <code>VITE_GOOGLE_CLIENT_ID</code>{" "}
                in the frontend environment, or use the demo.
              </div>
            )}
          </div>

          <div className="my-6 flex items-center gap-3 text-[10px] uppercase tracking-wider text-muted">
            <span className="h-px flex-1 bg-line" />
            or
            <span className="h-px flex-1 bg-line" />
          </div>

          <Button
            className="w-full"
            variant="secondary"
            icon={<Sparkles size={15} />}
            loading={busy}
            onClick={handleDemo}
          >
            Explore demo workspace
          </Button>

          {error ? <p className="mt-3 text-xs text-rose-600 dark:text-rose-300">{error}</p> : null}

          <p className="mt-6 text-[10px] leading-relaxed text-muted">
            The demo contains synthetic, fictional records only. Findings and AI output
            require human review.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
