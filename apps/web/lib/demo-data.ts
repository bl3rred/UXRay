"use client";

import { clearDemoState, readDemoState, writeDemoState } from "./browser-session";
import type {
  PersonaSessionRecord,
  ProjectDetail,
  ProjectInput,
  ProjectSummary,
  RunDetail,
  RunInput,
  RunSummary,
} from "./types";

type DemoState = {
  projects: ProjectDetail[];
  runs: Record<string, RunDetail>;
};

function nowIso() {
  return new Date().toISOString();
}

function buildDemoPersonaSessions(runId: string): PersonaSessionRecord[] {
  const createdAt = nowIso();
  return [
    {
      id: `demo_persona_${runId}_ftv`,
      persona_key: "first_time_visitor",
      display_label: "First-time visitor",
      mission: "Audit like a first-time visitor focused on orientation, clarity, and whether the next step is obvious.",
      status: "completed",
      result_mode: "structured",
      live_url: "https://browser-use.example/demo-first-time-visitor",
      final_url: "https://demo.uxray.app/signup",
      summary: "The core path is visible, but onboarding confidence is weaker than it should be.",
      error_message: null,
      created_at: createdAt,
      started_at: createdAt,
      completed_at: createdAt,
      observations: [
        {
          id: `demo_persona_obs_${runId}_ftv`,
          route: "/signup",
          title: "Primary CTA friction on first visit",
          description: "A first-time visitor may hesitate because the CTA feedback is weak.",
          severity: "high",
          evidence: ["No immediate confirmation after click"],
          screenshot_url: null,
        },
      ],
      progress: [
        {
          id: `demo_persona_progress_${runId}_ftv`,
          summary: "First-time visitor checked the homepage and signup path.",
          type: "demo",
          created_at: createdAt,
          screenshot_url: null,
        },
      ],
      artifacts: [],
    },
    {
      id: `demo_persona_${runId}_intent`,
      persona_key: "intent_driven",
      display_label: "Intent-driven",
      mission: "Audit like a goal-driven user focused on speed to value, CTA clarity, and the shortest useful path.",
      status: "completed",
      result_mode: "structured",
      live_url: "https://browser-use.example/demo-intent-driven",
      final_url: "https://demo.uxray.app/pricing",
      summary: "A goal-driven user finds the route, but the path to value has minor friction.",
      error_message: null,
      created_at: createdAt,
      started_at: createdAt,
      completed_at: createdAt,
      observations: [
        {
          id: `demo_persona_obs_${runId}_intent`,
          route: "/pricing",
          title: "Pricing navigation is still too subtle",
          description: "An intent-driven user notices extra effort before reaching the key decision page.",
          severity: "medium",
          evidence: ["Low contrast on the path to pricing"],
          screenshot_url: null,
        },
      ],
      progress: [
        {
          id: `demo_persona_progress_${runId}_intent`,
          summary: "Intent-driven persona validated the fastest route to pricing and signup.",
          type: "demo",
          created_at: createdAt,
          screenshot_url: null,
        },
      ],
      artifacts: [],
    },
    {
      id: `demo_persona_${runId}_trust`,
      persona_key: "trust_evaluator",
      display_label: "Trust evaluator",
      mission: "Audit like a skeptical evaluator focused on credibility, reassurance, policy visibility, and conversion hesitation.",
      status: "completed",
      result_mode: "structured",
      live_url: "https://browser-use.example/demo-trust-evaluator",
      final_url: "https://demo.uxray.app/signup",
      summary: "The trust lens sees conversion hesitation caused by weak reassurance near the action.",
      error_message: null,
      created_at: createdAt,
      started_at: createdAt,
      completed_at: createdAt,
      observations: [
        {
          id: `demo_persona_obs_${runId}_trust`,
          route: "/signup",
          title: "Trust and reassurance cues are too quiet",
          description: "Trust-related support is present but visually secondary near the CTA.",
          severity: "medium",
          evidence: ["Supportive trust copy is easy to miss"],
          screenshot_url: null,
        },
      ],
      progress: [
        {
          id: `demo_persona_progress_${runId}_trust`,
          summary: "Trust evaluator checked support and reassurance around conversion.",
          type: "demo",
          created_at: createdAt,
          screenshot_url: null,
        },
      ],
      artifacts: [],
    },
  ];
}

function buildDemoRun(projectId: string, projectName: string, websiteUrl: string): RunDetail {
  const runId = `demo_run_${Math.random().toString(36).slice(2, 10)}`;
  const createdAt = nowIso();
  const personaSessions = buildDemoPersonaSessions(runId);

  return {
    id: runId,
    project_id: projectId,
    status: "completed",
    live_url: personaSessions[0]?.live_url ?? null,
    target_url: websiteUrl,
    target_source: "site",
    browser_use_model: "claude-sonnet-4.6",
    evaluation_status: "completed",
    evaluation_error: null,
    source_review_status: "completed",
    source_review_error: null,
    repo_build_status: "not_requested",
    repo_build_error: null,
    created_at: createdAt,
    started_at: createdAt,
    completed_at: createdAt,
    error_message: null,
    custom_audience: null,
    issues: [
      {
        id: `demo_issue_${runId}`,
        issue_type: "cta_feedback",
        title: `Primary CTA friction on ${projectName}`,
        summary:
          "The main conversion action is visible, but the surrounding feedback is weak enough that users may hesitate or retry.",
        severity: "high",
        route: "/signup",
        evidence: [
          "Primary action state is not obvious after click",
          "Trust/supporting copy is visually secondary",
          `Sample preview generated for ${websiteUrl}`,
        ],
        confidence: 0.88,
        personas: ["first_time_visitor", "trust_evaluator"],
        screenshot_url: null,
      },
    ],
    recommendations: [
      {
        id: `demo_rec_${runId}`,
        title: "Make the primary conversion path feel safer",
        summary:
          "Give the CTA stronger feedback, support it with a clearer trust cue, and reduce ambiguity near the decision point.",
        likely_fix:
          "Add a visible progress state, tighten button copy, and increase prominence of trust proof near the form or CTA.",
        source: "demo_preview",
      },
    ],
    artifacts: [
      {
        id: `demo_artifact_${runId}`,
        kind: "demo_snapshot",
        label: "Sample audit snapshot",
        path_or_url: websiteUrl,
      },
    ],
    progress: [
      {
        id: `demo_progress_${runId}`,
        summary: `Sample UXRay preview generated for ${projectName}.`,
        type: "demo",
        created_at: createdAt,
        screenshot_url: null,
      },
    ],
    evaluations: [
      {
        id: `demo_eval_${runId}`,
        issue_title: `Primary CTA friction on ${projectName}`,
        audience: "multi_agent_synthesis",
        priority: "high",
        impact_summary:
          "First-time visitors and intent-driven users both see the conversion path as shakier than it should be.",
        rationale:
          "This demo result mirrors the kind of output the hosted Fetch.ai audience-review layer will synthesize from a real issue packet.",
        source: "demo_preview",
        status: "completed",
      },
    ],
    persona_sessions: personaSessions,
  };
}

function createSeedState(): DemoState {
  const projectId = "demo_project_commerce";
  const seedRun = buildDemoRun(
    projectId,
    "Demo Commerce Landing",
    "https://demo.uxray.app",
  );

  return {
    projects: [
      {
        id: projectId,
        name: "Demo Commerce Landing",
        url: "https://demo.uxray.app",
        repo_url: "https://github.com/example/demo-commerce",
        created_at: nowIso(),
        runs: [
          {
            id: seedRun.id,
            project_id: seedRun.project_id,
            status: seedRun.status,
            live_url: seedRun.live_url,
            target_url: seedRun.target_url,
            target_source: seedRun.target_source,
            browser_use_model: seedRun.browser_use_model,
            evaluation_status: seedRun.evaluation_status,
            evaluation_error: seedRun.evaluation_error,
            source_review_status: seedRun.source_review_status,
            source_review_error: seedRun.source_review_error,
            repo_build_status: seedRun.repo_build_status,
            repo_build_error: seedRun.repo_build_error,
            created_at: seedRun.created_at,
            started_at: seedRun.started_at,
            completed_at: seedRun.completed_at,
            error_message: seedRun.error_message,
            custom_audience: seedRun.custom_audience,
          },
        ],
      },
    ],
    runs: {
      [seedRun.id]: seedRun,
    },
  };
}

function loadDemoState(): DemoState {
  const existing = readDemoState();
  if (!existing) {
    const seeded = createSeedState();
    writeDemoState(JSON.stringify(seeded));
    return seeded;
  }

  try {
    return JSON.parse(existing) as DemoState;
  } catch {
    clearDemoState();
    const seeded = createSeedState();
    writeDemoState(JSON.stringify(seeded));
    return seeded;
  }
}

function saveDemoState(state: DemoState) {
  writeDemoState(JSON.stringify(state));
}

function toRunSummary(run: RunDetail): RunSummary {
  return {
    id: run.id,
    project_id: run.project_id,
    status: run.status,
    live_url: run.live_url,
    target_url: run.target_url,
    target_source: run.target_source,
    browser_use_model: run.browser_use_model,
    evaluation_status: run.evaluation_status,
    evaluation_error: run.evaluation_error,
    source_review_status: run.source_review_status,
    source_review_error: run.source_review_error,
    repo_build_status: run.repo_build_status,
    repo_build_error: run.repo_build_error,
    created_at: run.created_at,
    started_at: run.started_at,
    completed_at: run.completed_at,
    error_message: run.error_message,
    custom_audience: run.custom_audience,
  };
}

export function listDemoProjects(): ProjectSummary[] {
  return loadDemoState().projects.map(({ runs: _runs, ...project }) => project);
}

export function getDemoProject(projectId: string): ProjectDetail {
  const project = loadDemoState().projects.find((item) => item.id === projectId);
  if (!project) {
    throw new Error("Demo project not found.");
  }

  return project;
}

export function createDemoProject(input: ProjectInput): ProjectDetail {
  const state = loadDemoState();
  const project: ProjectDetail = {
    id: `demo_project_${Math.random().toString(36).slice(2, 10)}`,
    name: input.name,
    url: input.url ?? null,
    repo_url: input.repo_url ?? null,
    created_at: nowIso(),
    runs: [],
  };

  state.projects.unshift(project);
  saveDemoState(state);
  return project;
}

export function createDemoRun(projectId: string, input?: RunInput): RunSummary {
  const state = loadDemoState();
  const project = state.projects.find((item) => item.id === projectId);
  if (!project) {
    throw new Error("Demo project not found.");
  }

  const run = buildDemoRun(projectId, project.name, project.url ?? "https://demo.uxray.app");
  run.custom_audience = input?.custom_audience ?? null;
  if (run.custom_audience) {
    run.persona_sessions.push({
      id: `demo_persona_${run.id}_custom`,
      persona_key: "custom_audience",
      display_label: "Custom audience",
      mission: `Audit through this custom audience lens: ${run.custom_audience}.`,
      status: "completed",
      result_mode: "structured",
      live_url: "https://browser-use.example/demo-custom-audience",
      final_url: project.url ?? "https://demo.uxray.app",
      summary: `Custom audience session used: ${run.custom_audience}`,
      error_message: null,
      created_at: run.created_at,
      started_at: run.started_at,
      completed_at: run.completed_at,
      observations: [],
      progress: [],
      artifacts: [],
    });
  }
  state.runs[run.id] = run;
  project.runs.unshift(toRunSummary(run));
  saveDemoState(state);
  return toRunSummary(run);
}

export function getDemoRun(runId: string): RunDetail {
  const run = loadDemoState().runs[runId];
  if (!run) {
    throw new Error("Demo run not found.");
  }

  return run;
}
