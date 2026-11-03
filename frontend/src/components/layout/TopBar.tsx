import { Menu, Plus } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useCaseContext } from "@/context/CaseContext";
import { useAiStatus } from "@/hooks/useApi";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { humanize } from "@/lib/format";
import { ThemeToggle } from "./ThemeToggle";

function routeTitle(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  if (pathname === "/cases") return "Cases";
  if (pathname.includes("/evidence/intake")) return "Evidence intake";
  if (pathname.includes("/evidence")) return "Evidence vault";
  if (pathname.includes("/auth")) return "Authentication analysis";
  if (pathname.includes("/timeline")) return "Unified timeline";
  if (pathname.includes("/graph")) return "Relationship graph";
  if (pathname.includes("/findings")) return "Findings";
  if (pathname.includes("/ai")) return "AI investigation assistant";
  if (pathname.includes("/reports")) return "Reports";
  return "Case overview";
}

export function TopBar({ onMenu }: { onMenu: () => void }) {
  const location = useLocation();
  const { selectedCase } = useCaseContext();
  const { data: aiStatus } = useAiStatus();

  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-line bg-surface/75 px-4 backdrop-blur-xl sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          className="rounded-lg p-2 text-secondary transition-colors hover:bg-surface-2 hover:text-primary lg:hidden"
          aria-label="Open navigation"
        >
          <Menu size={18} />
        </button>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-primary">
            {routeTitle(location.pathname)}
          </p>
          <p className="truncate text-[11px] text-muted">
            {selectedCase ? selectedCase.title : "No case selected"}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {selectedCase ? (
          <Badge className="hidden border-line bg-surface-2 text-secondary sm:inline-flex">
            {humanize(selectedCase.status)}
          </Badge>
        ) : null}
        <Badge
          className={
            aiStatus?.configured
              ? "hidden max-w-[190px] truncate border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/40 dark:bg-violet-500/10 dark:text-violet-200 md:inline-flex"
              : "hidden border-line bg-surface-2 text-muted sm:inline-flex"
          }
          title={
            aiStatus?.configured
              ? `${aiStatus.model_label ?? aiStatus.model} via ${aiStatus.provider}`
              : "AI disabled"
          }
        >
          {aiStatus?.configured ? aiStatus.model_label ?? aiStatus.model : "AI disabled"}
        </Badge>
        <ThemeToggle />
        <Link to="/cases" className="hidden sm:block">
          <Button size="sm" variant="primary" icon={<Plus size={14} />}>
            New case
          </Button>
        </Link>
      </div>
    </header>
  );
}
