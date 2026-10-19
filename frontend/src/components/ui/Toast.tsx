import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { cn } from "@/lib/cn";

type ToastTone = "success" | "error" | "info";
interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  message?: string;
}

interface ToastContextValue {
  push: (tone: ToastTone, title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback(
    (tone: ToastTone, title: string, message?: string) => {
      const id = Date.now() + Math.random();
      setItems((current) => [...current, { id, tone, title, message }]);
      window.setTimeout(() => {
        setItems((current) => current.filter((item) => item.id !== id));
      }, 6000);
    },
    [],
  );

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-full max-w-sm flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.id}
            className={cn(
              "pointer-events-auto flex items-start gap-3 rounded-xl border bg-surface/95 p-4 shadow-2xl backdrop-blur",
              item.tone === "success" &&
                "border-emerald-300 dark:border-emerald-500/30",
              item.tone === "error" &&
                "border-rose-300 dark:border-rose-500/30",
              item.tone === "info" && "border-accent/30",
            )}
          >
            <span className="mt-0.5">
              {item.tone === "success" ? (
                <CheckCircle2
                  size={17}
                  className="text-emerald-600 dark:text-emerald-400"
                />
              ) : item.tone === "error" ? (
                <AlertTriangle
                  size={17}
                  className="text-rose-600 dark:text-rose-400"
                />
              ) : (
                <Info size={17} className="text-accent" />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-primary">{item.title}</p>
              {item.message ? (
                <p className="mt-0.5 text-xs leading-relaxed text-muted">
                  {item.message}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() =>
                setItems((current) =>
                  current.filter((entry) => entry.id !== item.id),
                )
              }
              className="rounded p-1 text-muted transition-colors hover:text-primary"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
