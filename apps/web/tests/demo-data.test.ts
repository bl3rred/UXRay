import { beforeEach, describe, expect, it } from "vitest";

import {
  createDemoProject,
  createDemoRun,
  getDemoProject,
  getDemoRun,
  listDemoProjects,
} from "../lib/demo-data";
import { clearDemoState } from "../lib/browser-session";

describe("demo-data", () => {
  beforeEach(() => {
    clearDemoState();
  });

  it("seeds a browseable project list", () => {
    const projects = listDemoProjects();

    expect(projects.length).toBeGreaterThan(0);
    expect(projects[0]?.id.startsWith("demo_")).toBe(true);
  });

  it("creates a project and run inside session storage", () => {
    const project = createDemoProject({
      name: "Judge walkthrough",
      url: "https://judge.demo",
      repo_url: "https://github.com/example/judge-demo",
    });

    const run = createDemoRun(project.id);
    const hydratedProject = getDemoProject(project.id);
    const hydratedRun = getDemoRun(run.id);

    expect(hydratedProject.runs[0]?.id).toBe(run.id);
    expect(hydratedRun.project_id).toBe(project.id);
    expect(hydratedRun.recommendations.length).toBeGreaterThan(0);
  });
});
