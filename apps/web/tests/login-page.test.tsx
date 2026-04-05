import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import LoginPage from "../app/login/page";

const replaceMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

vi.mock("../lib/auth", () => ({
  useAuth: () => useAuthMock(),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    useAuthMock.mockReset();
  });

  it("does not auto-redirect guests away from the login page", async () => {
    useAuthMock.mockReturnValue({
      mode: "guest",
      error: null,
      isSupabaseConfigured: true,
      continueAsGuest: vi.fn(),
      signInWithGitHub: vi.fn().mockResolvedValue(undefined),
    });

    render(<LoginPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /login with github/i })).toBeInTheDocument();
    });
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("still redirects authenticated users into the app", async () => {
    useAuthMock.mockReturnValue({
      mode: "authenticated",
      error: null,
      isSupabaseConfigured: true,
      continueAsGuest: vi.fn(),
      signInWithGitHub: vi.fn().mockResolvedValue(undefined),
    });

    render(<LoginPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/app");
    });
  });
});
