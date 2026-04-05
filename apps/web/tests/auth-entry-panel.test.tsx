import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { AuthEntryPanel } from "../components/auth-entry-panel";

describe("AuthEntryPanel", () => {
  it("supports guest continuation even when Supabase is not configured", () => {
    const onContinueAsGuest = vi.fn();
    const onSignInWithGitHub = vi.fn().mockResolvedValue(undefined);

    render(
      <AuthEntryPanel
        error={null}
        isSupabaseConfigured={false}
        onContinueAsGuest={onContinueAsGuest}
        onSignInWithGitHub={onSignInWithGitHub}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /continue as guest/i }));

    expect(onContinueAsGuest).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /login with github/i })).toBeInTheDocument();
    expect(
      screen.getByText(/github sign-in is not configured in this environment yet/i),
    ).toBeInTheDocument();
  });
});
