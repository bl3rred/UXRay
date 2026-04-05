import Link from "next/link";
import { ArrowUpRight, Sparkle, TimerReset } from "lucide-react";

import type { RunSummary } from "../lib/types";

type RunListProps = {
  runs: RunSummary[];
};

function statusClasses(status: RunSummary["status"] | RunSummary["evaluation_status"]) {
  switch (status) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/10 text-emerald-100";
    case "running":
      return "border-sky-400/20 bg-sky-400/10 text-sky-100";
    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-100";
    default:
      return "border-amber-400/20 bg-amber-400/10 text-amber-100";
  }
}

export function RunList({ runs }: RunListProps) {
  if (!runs.length) {
    return (
      <div className="border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-zinc-500">
        No audit runs yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <Link
          key={run.id}
          href={`/app/runs/${run.id}`}
          className="block border hairline-border border-white/10 bg-[#0c0c0c] p-5 transition hover:border-white/20 hover:bg-white/[0.03]"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center border hairline-border border-white/10 bg-white/[0.02] text-[#adc6ff]">
                  {run.status === "completed" ? (
                    <Sparkle className="size-4" />
                  ) : (
                    <TimerReset className="size-4" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{run.id}</p>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                    {run.browser_use_model}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <span
                  className={`border px-3 py-1 text-xs uppercase tracking-[0.18em] ${statusClasses(run.status)}`}
                >
                  {run.status}
                </span>
                <span
                  className={`border px-3 py-1 text-xs uppercase tracking-[0.18em] ${statusClasses(run.evaluation_status)}`}
                >
                  Fetch {run.evaluation_status}
                </span>
                <span
                  className={`border px-3 py-1 text-xs uppercase tracking-[0.18em] ${statusClasses(run.source_review_status)}`}
                >
                  Source {run.source_review_status}
                </span>
                {run.repo_build_status !== "not_requested" ? (
                  <span
                    className={`border px-3 py-1 text-xs uppercase tracking-[0.18em] ${statusClasses(run.repo_build_status)}`}
                  >
                    Repo {run.repo_build_status}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Updated
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  {run.completed_at ?? run.started_at ?? run.created_at}
                </p>
                {run.target_url ? (
                  <p className="mt-2 max-w-[220px] truncate text-xs text-zinc-500">
                    {run.target_source === "repo_preview" ? "Local preview" : "Target"}: {run.target_url}
                  </p>
                ) : null}
              </div>
              <ArrowUpRight className="size-4 text-slate-400" />
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
