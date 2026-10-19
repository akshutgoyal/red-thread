import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useCases } from "@/hooks/useApi";
import type { CaseSummary } from "@/types";

const STORAGE_KEY = "red-thread.selectedCaseId";

interface CaseContextValue {
  cases: CaseSummary[];
  isLoading: boolean;
  error: Error | null;
  selectedCaseId: string | null;
  selectedCase: CaseSummary | null;
  setSelectedCaseId: (caseId: string | null) => void;
}

const CaseContext = createContext<CaseContextValue | null>(null);

export function CaseProvider({ children }: { children: ReactNode }) {
  const { data: cases = [], isLoading, error } = useCases();
  const [selectedCaseId, setSelectedCaseIdState] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY),
  );

  useEffect(() => {
    // Do not overwrite a case ID supplied by the URL while the case list is
    // still loading. Without this guard, the initial empty list can reset the
    // active case to null and then to the preferred case when the query resolves.
    if (isLoading) return;
    const preferredCase =
      cases.find((item) => item.title.toLowerCase().includes("phishtrace")) ?? cases[0];
    if (selectedCaseId && !cases.some((item) => item.id === selectedCaseId)) {
      setSelectedCaseIdState(preferredCase?.id ?? null);
    } else if (!selectedCaseId && cases.length > 0) {
      setSelectedCaseIdState(preferredCase.id);
    }
  }, [cases, selectedCaseId, isLoading]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (selectedCaseId) window.localStorage.setItem(STORAGE_KEY, selectedCaseId);
    else window.localStorage.removeItem(STORAGE_KEY);
  }, [selectedCaseId]);

  const setSelectedCaseId = useCallback((caseId: string | null) => {
    setSelectedCaseIdState(caseId);
  }, []);

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );

  const value = useMemo(
    () => ({
      cases,
      isLoading,
      error: error as Error | null,
      selectedCaseId,
      selectedCase,
      setSelectedCaseId,
    }),
    [cases, isLoading, error, selectedCaseId, selectedCase, setSelectedCaseId],
  );

  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>;
}

export function useCaseContext(): CaseContextValue {
  const context = useContext(CaseContext);
  if (!context) throw new Error("useCaseContext must be used inside CaseProvider");
  return context;
}
