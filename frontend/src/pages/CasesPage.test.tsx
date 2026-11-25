import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useCaseContext: vi.fn(),
  useCreateCase: vi.fn(),
  useDeleteCase: vi.fn(),
  useAuth: vi.fn(),
  useToast: vi.fn(),
}));

vi.mock("@/context/CaseContext", () => ({ useCaseContext: mocks.useCaseContext }));
vi.mock("@/context/AuthContext", () => ({ useAuth: mocks.useAuth }));
vi.mock("@/hooks/useApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/useApi")>();
  return {
    ...actual,
    useCreateCase: mocks.useCreateCase,
    useDeleteCase: mocks.useDeleteCase,
  };
});
vi.mock("@/components/ui/Toast", () => ({ useToast: mocks.useToast }));

import { CasesPage } from "./CasesPage";

describe("CasesPage", () => {
  const mutate = vi.fn();

  beforeEach(() => {
    mutate.mockReset();
    mocks.useCaseContext.mockReturnValue({
      cases: [],
      isLoading: false,
      error: null,
      selectedCaseId: null,
      setSelectedCaseId: vi.fn(),
    });
    mocks.useCreateCase.mockReturnValue({ mutate, isPending: false });
    mocks.useDeleteCase.mockReturnValue({ mutate: vi.fn(), isPending: false });
    mocks.useAuth.mockReturnValue({ loginDemo: vi.fn(), user: null });
    mocks.useToast.mockReturnValue({ push: vi.fn() });
  });

  it("opens the new-case form and submits an empty account's first case", () => {
    render(
      <MemoryRouter>
        <CasesPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "New case" }));
    fireEvent.change(screen.getByLabelText("Case title"), {
      target: { value: "First Personal Case" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create case" }));

    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate.mock.calls[0][0]).toMatchObject({
      title: "First Personal Case",
    });
  });

  it("asks for confirmation before deleting a case", () => {
    const deleteMutate = vi.fn();
    mocks.useDeleteCase.mockReturnValue({ mutate: deleteMutate, isPending: false });
    mocks.useCaseContext.mockReturnValue({
      cases: [
        {
          id: "case-1",
          title: "operation red ledger",
          description: "",
          status: "open",
          evidence_count: 9,
          event_count: 32,
          finding_count: 4,
          open_finding_count: 2,
          created_at: "2026-11-14T10:28:10Z",
        },
      ],
      isLoading: false,
      error: null,
      selectedCaseId: null,
      setSelectedCaseId: vi.fn(),
    });

    render(
      <MemoryRouter>
        <CasesPage />
      </MemoryRouter>,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Delete operation red ledger" }),
    );

    // Nothing is destroyed until the confirmation is accepted.
    expect(deleteMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Delete permanently/i }));
    expect(deleteMutate).toHaveBeenCalledWith("case-1", expect.any(Object));
  });
});
