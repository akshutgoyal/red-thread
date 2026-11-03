import {
  Activity,
  Bot,
  FileSearch,
  FolderOpen,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  ScrollText,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useCaseContext } from "@/context/CaseContext";
import { useAiStatus, useHealth } from "@/hooks/useApi";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/Badge";
import { ThemeToggle } from "./ThemeToggle";

const baseItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/cases", label: "Cases", icon: FolderOpen, end: true },
];

const caseItems = [
  { suffix: "", label: "Case overview", icon: Activity, end: true },
  { suffix: "/evidence", label: "Evidence vault", icon: FileSearch },
  { suffix: "/evidence/intake", label: "Evidence intake", icon: UploadCloud },
  { suffix: "/auth", label: "Auth analysis", icon: ShieldCheck },
  { suffix: "/timeline", label: "Timeline", icon: ScrollText },
  { suffix: "/graph", label: "Relationship graph", icon: GitBranch },
  { suffix: "/findings", label: "Findings", icon: ListChecks },
  { suffix: "/ai", label: "AI assistant", icon: Bot },
  { suffix: "/reports", label: "Reports", icon: FileSearch },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { cases, selectedCaseId, selectedCase, setSelectedCaseId } =
    useCaseContext();
  const { data: health } = useHealth();
  const { data: aiStatus } = useAiStatus();

  const caseBase = selectedCaseId ? `/cases/${selectedCaseId}` : null;

  return (
    <aside className="flex h-full w-72 flex-col border-r border-line bg-surface/95 backdrop-blur-xl">
      <div className="border-b border-line px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent shadow-sm">
            <ShieldCheck size={20} />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-[0.16em] text-primary">
              Red Thread
            </p>
            <p className="text-[10px] uppercase tracking-wider text-muted">
              Forensic investigation
            </p>
          </div>
        </div>
        <p className="mt-4 text-[11px] leading-relaxed text-muted">
          From fragmented digital traces to an explainable, human-reviewed
          investigation picture.
        </p>
      </div>

      <div className="border-b border-line px-4 py-4">
        <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-muted">
          Active case
        </label>
        <select
          value={selectedCaseId ?? ""}
          onChange={(event) => setSelectedCaseId(event.target.value || null)}
          className="w-full cursor-pointer rounded-lg border border-line-strong bg-surface-2 px-3 py-2 text-xs text-primary transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
        >
          {cases.length === 0 ? <option value="">No cases yet</option> : null}
          {cases.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </select>
        {selectedCase ? (
          <p className="mt-2 truncate text-[10px] text-muted">
            {selectedCase.evidence_count} evidence · {selectedCase.event_count}{" "}
            events · {selectedCase.open_finding_count} open findings
          </p>
        ) : null}
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        <div>
          <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
            Workspace
          </p>
          <div className="space-y-0.5">
            {baseItems.map((item) => (
              <NavItem key={item.to} {...item} onNavigate={onNavigate} />
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
            Investigation
          </p>
          <div className="space-y-0.5">
            {caseItems.map((item) => {
              const to = caseBase ? `${caseBase}${item.suffix}` : "/cases";
              return (
                <NavItem
                  key={item.label}
                  to={to}
                  label={item.label}
                  icon={item.icon}
                  end={item.end}
                  disabled={!caseBase}
                  onNavigate={onNavigate}
                />
              );
            })}
          </div>
        </div>
      </nav>

      <div className="space-y-2 border-t border-line px-4 py-4 text-[10px] text-muted">
        <div className="flex items-center justify-between">
          <span>Theme</span>
          <ThemeToggle className="h-7 w-7" />
        </div>
        <div className="flex items-center justify-between">
          <span>Backend</span>
          <Badge
            className={
              health?.database === "ok"
                ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200"
                : "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200"
            }
          >
            {health?.database === "ok" ? "Online" : "Offline"}
          </Badge>
        </div>
        <div className="flex items-center justify-between">
          <span>OCR</span>
          <Badge
            className={
              health?.ocr_available
                ? "border-accent/30 bg-accent/10 text-accent"
                : "border-line bg-surface-2 text-muted"
            }
          >
            {health?.ocr_available ? "Available" : "Unavailable"}
          </Badge>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span>AI</span>
          <Badge
            className={
              aiStatus?.configured
                ? "max-w-[150px] truncate border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-200"
                : "border-line bg-surface-2 text-muted"
            }
            title={
              aiStatus?.configured
                ? `${aiStatus.model_label ?? aiStatus.model} via ${aiStatus.provider}`
                : "AI disabled"
            }
          >
            {aiStatus?.configured ? aiStatus.model_label ?? aiStatus.model : "Off"}
          </Badge>
        </div>
      </div>
    </aside>
  );
}

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  disabled,
  onNavigate,
}: {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  end?: boolean;
  disabled?: boolean;
  onNavigate?: () => void;
}) {
  if (disabled) {
    return (
      <span className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2 text-xs text-muted/60">
        <Icon size={15} />
        {label}
      </span>
    );
  }
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs transition-colors",
          isActive
            ? "bg-accent/10 font-medium text-accent"
            : "text-secondary hover:bg-surface-2 hover:text-primary",
        )
      }
    >
      <Icon size={15} />
      {label}
    </NavLink>
  );
}
