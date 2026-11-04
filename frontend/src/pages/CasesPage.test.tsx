import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useCaseContext: vi.fn(),
  useCreateCase: vi.fn(),
  useAuth: vi.fn(),
  useToast: vi.fn(),
}));

vi.mock("@/context/CaseContext", () => ({ useCaseContext: mocks.useCaseContext }));
vi.mock("@/context/AuthContext", () => ({ useAuth: mocks.useAuth }));
vi.mock("@/hooks/useApi", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/hooks/useApi")>();
  return { ...actual, useCreateCase: mocks.useCreateCase };
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
});
