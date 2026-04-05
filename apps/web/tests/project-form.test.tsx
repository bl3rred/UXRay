import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ProjectForm } from "../components/project-form";
import { AuthProvider } from "../lib/auth";

describe("ProjectForm", () => {
  it("submits the expected payload", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <ProjectForm onCreate={onCreate} />
      </AuthProvider>,
    );

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "UXRay Demo" },
    });
    fireEvent.change(screen.getByLabelText(/website url/i), {
      target: { value: "https://example.com" },
    });
    fireEvent.change(screen.getByLabelText(/public repository url/i), {
      target: { value: "https://github.com/example/repo" },
    });

    fireEvent.click(screen.getByRole("button", { name: /create project/i }));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith({
        name: "UXRay Demo",
        url: "https://example.com",
        repo_url: "https://github.com/example/repo",
      });
    });
  });
});
