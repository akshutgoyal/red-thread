import { Dialog, DialogPanel, DialogTitle } from "@headlessui/react";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <div
        className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm dark:bg-slate-950/80"
        aria-hidden="true"
      />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <DialogPanel
          className={cn(
            "max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-line bg-surface p-6 shadow-2xl",
            wide ? "max-w-3xl" : "max-w-lg",
          )}
        >
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <DialogTitle className="text-base font-semibold text-primary">
                {title}
              </DialogTitle>
              {description ? (
                <p className="mt-1 text-xs text-muted">{description}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-primary"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>
          {children}
        </DialogPanel>
      </div>
    </Dialog>
  );
}
