"use client";

import { useCallback } from "react";

import { getRun } from "../lib/api";
import { usePolling } from "../lib/hooks";
import { RunDetailPanel } from "./run-detail-panel";

type RunViewProps = {
  runId: string;
};

export function RunView({ runId }: RunViewProps) {
  const loader = useCallback(() => getRun(runId), [runId]);
  const { data: run, error, loading } = usePolling(loader, 2500, true, (value) => {
    return (
      !value ||
      value.status === "queued" ||
      value.status === "running" ||
      value.evaluation_status === "pending" ||
      value.evaluation_status === "running" ||
      value.source_review_status === "pending" ||
      value.source_review_status === "running"
    );
  });

  if (loading && !run) {
    return <p className="text-sm text-body">Loading run...</p>;
  }

  if (!run) {
    return <p className="text-sm text-red-400">{error ?? "Run not found."}</p>;
  }

  return (
    <div className="space-y-4">
      {error ? (
        <div className="border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Live refresh hit an error, but the latest run snapshot is still visible. {error}
        </div>
      ) : null}
      <RunDetailPanel run={run} />
    </div>
  );
}
