import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/theme/ThemeContext";
import { cn } from "@/lib/cn";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={`Switch to ${next} theme`}
      aria-label={`Switch to ${next} theme`}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface/70 text-secondary transition-colors hover:bg-surface-2 hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        className,
      )}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
