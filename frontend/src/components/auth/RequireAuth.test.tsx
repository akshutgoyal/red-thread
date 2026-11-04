import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  useAuth: vi.fn(),
}));
vi.mock("@/context/AuthContext", () => ({ useAuth: auth.useAuth }));

import { RequireAuth } from "./RequireAuth";

function renderGuard() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/login" element={<div>login screen</div>} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <div>private workspace</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  beforeEach(() => {
    auth.useAuth.mockReturnValue({ user: null, isLoading: false });
  });

  it("redirects an unauthenticated visitor to login", () => {
    renderGuard();
    expect(screen.getByText("login screen")).toBeInTheDocument();
  });

  it("renders the protected workspace for an authenticated user", () => {
    auth.useAuth.mockReturnValue({
      user: { id: "u1", is_demo: false },
      isLoading: false,
    });
    renderGuard();
    expect(screen.getByText("private workspace")).toBeInTheDocument();
  });
});
