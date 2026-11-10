import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  useAuth: vi.fn(),
}));

vi.mock("@/context/AuthContext", () => ({ useAuth: auth.useAuth }));

import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    auth.useAuth.mockReturnValue({
      user: null,
      isLoading: false,
      loginGoogle: vi.fn(),
      loginDemo: vi.fn().mockResolvedValue({ id: "demo", is_demo: true }),
      logout: vi.fn(),
    });
  });

  it("renders the Google/demo choice and starts the demo", async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Open your workspace")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Explore demo workspace/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Explore demo workspace/i }));
    await waitFor(() => expect(auth.useAuth().loginDemo).toHaveBeenCalledTimes(1));
  });

  it("initializes Google sign-in after the loading state clears", async () => {
    // Regression: the effect used to run while the loading state was rendered,
    // so the button container did not exist yet and the effect never re-ran.
    const renderButton = vi.fn();
    const initialize = vi.fn();
    (window as unknown as { google: unknown }).google = {
      accounts: { id: { initialize, renderButton } },
    };

    auth.useAuth.mockReturnValue({
      user: null,
      isLoading: false,
      loginGoogle: vi.fn(),
      loginDemo: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(initialize).toHaveBeenCalled());
    expect(renderButton).toHaveBeenCalled();

    delete (window as unknown as { google?: unknown }).google;
  });
});
