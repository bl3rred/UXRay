"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";

import { createRun, getProject } from "../lib/api";
import { isDemoRecordId } from "../lib/browser-session";
import { usePolling } from "../lib/hooks";
import { RunList } from "./run-list";

type ProjectOverviewProps = {
  projectId: string;
};

export function ProjectOverview({ projectId }: ProjectOverviewProps) {
  const router = useRouter();
  const [startingRun, setStartingRun] = useState(false);
  const [customAudience, setCustomAudience] = useState("");
  const [startError, setStartError] = useState<string | null>(null);
  const loader = useCallback(() => getProject(projectId), [projectId]);
  const { data: project, error, loading } = usePolling(loader, 3000, true, (value) => {
    return (
      !value ||
      value.runs.some(
        (run) =>
          run.status === "queued" ||
          run.status === "running" ||
          run.evaluation_status === "pending" ||
          run.evaluation_status === "running" ||
          run.source_review_status === "pending" ||
          run.source_review_status === "running",
      )
    );
  });

  async function handleStartAudit() {
    setStartingRun(true);
    setStartError(null);
    try {
      const run = await createRun(projectId, {
        custom_audience: customAudience.trim() || undefined,
      });
      setCustomAudience("");
      router.push(`/app/runs/${run.id}`);
    } catch (error) {
      setStartError(error instanceof Error ? error.message : "Failed to start audit.");
    } finally {
      setStartingRun(false);
    }
  }

  if (loading && !project) {
    return <p className="text-sm text-body">Loading project...</p>;
  }

  if (error || !project) {
    return <p className="text-sm text-red-400">{error ?? "Project not found."}</p>;
  }

  const hasActiveRun = project.runs.some(
    (run) =>
      run.status === "queued" ||
      run.status === "running" ||
      run.evaluation_status === "pending" ||
      run.evaluation_status === "running" ||
      run.source_review_status === "pending" ||
      run.source_review_status === "running",
  );
  const isDemoProject = isDemoRecordId(project.id);

  return (
    <div className="space-y-6">
      {isDemoProject ? (
        <div className="border hairline-border border-white/10 bg-white/[0.02] px-4 py-3 text-sm text-zinc-500">
          This project is seeded demo data. Live audits still require your local backend
          and Browser Use to be reachable.
        </div>
      ) : null}

      <section className="border hairline-border border-white/10 bg-[#0c0c0c] p-6 md:p-8">
        <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-4">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-zinc-600">Project</p>
              <h1 className="mt-3 font-display text-4xl font-semibold tracking-[-0.03em] text-white md:text-5xl">
                {project.name}
              </h1>
            </div>
            {project.url ? (
              <div className="border hairline-border border-white/10 bg-white/[0.02] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-zinc-600">Website</p>
                <p className="mt-2 text-sm text-zinc-400">{project.url}</p>
              </div>
            ) : null}
            {project.repo_url ? (
              <div className="border hairline-border border-white/10 bg-white/[0.02] px-4 py-3">
                <p className="text-xs uppercase tracking-[0.18em] text-zinc-600">Public repo</p>
                <p className="mt-2 text-sm text-zinc-400">{project.repo_url}</p>
                <p className="mt-2 text-sm text-zinc-500">
                  Supported public Next.js and Vite repos will try to boot a local preview before the run starts.
                </p>
              </div>
            ) : null}
          </div>

          <div className="border hairline-border border-white/10 bg-black/20 p-5 md:p-6">
            <p className="text-xs uppercase tracking-[0.22em] text-zinc-600">Start audit</p>
            <p className="mt-3 text-sm leading-7 text-zinc-500">
              Add a custom audience only if this run needs a specific buyer, stakeholder, or risk lens.
            </p>

            <label className="mt-5 block text-sm text-white">
              <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-zinc-600">
                Custom audience
              </span>
              <textarea
                className="min-h-28 w-full border hairline-border border-white/10 bg-black/20 px-4 py-3 text-white outline-none transition focus:border-[#adc6ff]/50"
                value={customAudience}
                onChange={(event) => setCustomAudience(event.target.value)}
                placeholder="Optional. Example: B2B buyer comparing vendors for risk and ROI."
              />
            </label>

            {startError ? <p className="mt-4 text-sm text-red-300">{startError}</p> : null}

            <button
              className="mt-5 inline-flex cursor-pointer items-center gap-2 bg-white px-5 py-3 text-xs font-bold uppercase tracking-[0.22em] text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => void handleStartAudit()}
              disabled={startingRun}
            >
              {startingRun ? "Starting audit..." : "Start audit"}
              <ArrowRight className="size-4" />
            </button>
          </div>
        </div>
      </section>

      {hasActiveRun ? (
        <div className="border hairline-border border-white/10 bg-white/[0.02] px-4 py-3 text-sm text-zinc-500">
          This project still has a live run or background enrichment in progress. UXRay will keep polling.
        </div>
      ) : null}

      <section className="space-y-4">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-[-0.03em] text-white">Run history</h2>
        </div>
        <RunList runs={project.runs} />
      </section>
    </div>
  );
}
