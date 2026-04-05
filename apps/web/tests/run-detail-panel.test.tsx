import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RunDetailPanel } from "../components/run-detail-panel";
import type { RunDetail } from "../lib/types";

const run: RunDetail = {
  id: "run_123",
  project_id: "project_123",
  status: "completed",
  live_url: "https://browser-use.example/live",
  target_url: "http://127.0.0.1:4100",
  target_source: "repo_preview",
  browser_use_model: "claude-sonnet-4.6",
  evaluation_status: "skipped",
  evaluation_error: null,
  source_review_status: "completed",
  source_review_error: null,
  repo_build_status: "completed",
  repo_build_error: null,
  created_at: "2026-04-03T10:00:00Z",
  started_at: "2026-04-03T10:00:01Z",
  completed_at: "2026-04-03T10:01:00Z",
  error_message: null,
  custom_audience: "B2B buyer comparing vendors",
  issues: [
    {
      id: "issue_1",
      issue_type: "cta_feedback",
      title: "Primary CTA did not respond",
      summary: "The main signup action provided no visible feedback.",
      severity: "high",
      route: "/signup",
      evidence: ["No loading state", "User clicked twice"],
      confidence: 0.92,
      personas: ["first_time_visitor", "trust_evaluator"],
      screenshot_url: "https://example.com/finding.png",
    },
  ],
  recommendations: [
    {
      id: "rec_1",
      title: "Add explicit CTA feedback",
      summary: "Show a loading state and success/error response after click.",
      likely_fix: "Wire the button to submission state and surface inline feedback.",
      source: "analyzer",
    },
    {
      id: "rec_2",
      title: "Wire CTA state transitions in source",
      summary: "The repo review found that request-state feedback is not modeled deeply enough in the CTA component.",
      likely_fix: "Update src/app.tsx so the CTA renders pending, success, and error states.",
      source: "source_review_gpt",
    },
  ],
  artifacts: [
    {
      id: "artifact_1",
      kind: "screenshot",
      label: "CTA screenshot",
      path_or_url: "https://example.com/cta.png",
    },
  ],
  progress: [
    {
      id: "progress_1",
      summary: "Inspecting signup CTA",
      type: "tool",
      created_at: "2026-04-03T10:00:30Z",
      screenshot_url: "https://example.com/live.png",
    },
  ],
  evaluations: [],
  persona_sessions: [
    {
      id: "persona_1",
      persona_key: "first_time_visitor",
      display_label: "First-time visitor",
      mission:
        "Audit like a first-time visitor focused on orientation, clarity, and whether the next step is obvious.",
      status: "completed",
      result_mode: "salvaged",
      live_url: "https://browser-use.example/first-time",
      final_url: "https://example.com/signup",
      summary: "First-time visitor saw CTA hesitation.",
      error_message: null,
      created_at: "2026-04-03T10:00:00Z",
      started_at: "2026-04-03T10:00:01Z",
      completed_at: "2026-04-03T10:00:40Z",
      observations: [
        {
          id: "persona_obs_1",
          route: "/signup",
          title: "CTA hesitation",
          description: "The first-time visitor hesitated because the CTA state was ambiguous.",
          severity: "high",
          evidence: ["No visible confirmation"],
          screenshot_url: null,
        },
      ],
      progress: [
        {
          id: "persona_progress_1",
          summary: "First-time visitor reviewed the signup route",
          type: "assistant",
          created_at: "2026-04-03T10:00:20Z",
          screenshot_url: null,
        },
      ],
      artifacts: [],
    },
  ],
};

describe("RunDetailPanel", () => {
  it("renders findings and recommendations for a completed run", () => {
    render(<RunDetailPanel run={run} />);

    expect(screen.getByText(/primary cta did not respond/i)).toBeInTheDocument();
    expect(screen.getByText(/add explicit cta feedback/i)).toBeInTheDocument();
    expect(screen.getByText(/focused evidence, not an endless scroll/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view logs/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /persona detail/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /live session/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /primary cta did not respond evidence screenshot/i })).toHaveAttribute(
      "src",
      "https://example.com/finding.png",
    );
    expect(screen.getByTitle(/browser use live session/i)).toHaveAttribute(
      "src",
      "https://browser-use.example/live",
    );
  });

  it("opens the logs overlay on demand", async () => {
    render(<RunDetailPanel run={run} />);

    fireEvent.click(screen.getByRole("button", { name: /view logs/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /run logs/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("img", { name: /inspecting signup cta screenshot/i })).toHaveAttribute(
      "src",
      "https://example.com/live.png",
    );
  });

  it("opens the fetch overlay on demand", async () => {
    render(<RunDetailPanel run={run} />);

    fireEvent.click(screen.getByRole("button", { name: /fetch review/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /fetch\.ai review/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/fetch\.ai evaluation is not configured yet/i)).toBeInTheDocument();
  });

  it("opens the source review overlay on demand", async () => {
    render(<RunDetailPanel run={run} />);

    fireEvent.click(screen.getByRole("button", { name: /source review/i }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /source review/i })).toBeInTheDocument();
    });
    expect(screen.getAllByText(/wire cta state transitions in source/i).length).toBeGreaterThan(0);
  });
});
