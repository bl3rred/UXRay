"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Clock3,
  Flag,
  Layers3,
  Logs,
  Sparkles,
  X,
} from "lucide-react";

import { retryFetchReview } from "../lib/api";
import { isDemoRecordId } from "../lib/browser-session";
import type { PersonaSessionRecord, RunDetail } from "../lib/types";
import { SmartImage } from "./ui/smart-image";

type RunDetailPanelProps = {
  run: RunDetail;
};

type OverlaySection = "logs" | "personas" | "fetch" | "source";
type LiveSessionCard = {
  id: string;
  label: string;
  liveUrl: string;
};

function normalizedIssueTerms(value: string) {
  return new Set(
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .split(" ")
      .filter((token) => token.length > 2),
  );
}

function issueImageCandidates(run: RunDetail, issue: RunDetail["issues"][number]) {
  const issueTerms = normalizedIssueTerms(`${issue.title} ${issue.summary}`);
  const candidates = new Set<string>();

  if (issue.screenshot_url) {
    candidates.add(issue.screenshot_url);
  }

  for (const persona of run.persona_sessions) {
    for (const observation of persona.observations) {
      const observationTerms = normalizedIssueTerms(`${observation.title} ${observation.description}`);
      if (
        observation.screenshot_url &&
        ((observation.title === issue.title && observation.route === issue.route) ||
          (observation.route === issue.route &&
            [...issueTerms].some((term) => observationTerms.has(term))))
      ) {
        candidates.add(observation.screenshot_url);
      }
    }

    for (const progress of persona.progress) {
      if (progress.screenshot_url) {
        candidates.add(progress.screenshot_url);
      }
    }

    for (const artifact of persona.artifacts) {
      const artifactTerms = normalizedIssueTerms(artifact.label);
      if (
        artifact.kind === "screenshot" &&
        (artifact.label.toLowerCase().includes(issue.title.toLowerCase()) ||
          [...issueTerms].some((term) => artifactTerms.has(term)))
      ) {
        candidates.add(artifact.path_or_url);
      }
    }
  }

  for (const progress of run.progress) {
    if (progress.screenshot_url) {
      candidates.add(progress.screenshot_url);
    }
  }

  for (const artifact of run.artifacts) {
    const artifactTerms = normalizedIssueTerms(artifact.label);
    if (
      artifact.kind === "screenshot" &&
      (artifact.label.toLowerCase().includes(issue.title.toLowerCase()) ||
        [...issueTerms].some((term) => artifactTerms.has(term)))
    ) {
      candidates.add(artifact.path_or_url);
    }
  }

  for (const artifact of run.artifacts) {
    if (artifact.kind === "screenshot") {
      candidates.add(artifact.path_or_url);
    }
  }

  return [...candidates];
}

function formatDate(value: string | null) {
  if (!value) {
    return "Pending";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusTone(status: string) {
  if (status === "completed") {
    return "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/20";
  }
  if (status === "failed") {
    return "bg-red-500/15 text-red-200 ring-1 ring-red-400/20";
  }
  if (status === "running" || status === "pending") {
    return "bg-accent/15 text-accent ring-1 ring-accent/20";
  }
  return "bg-white/8 text-slate-200 ring-1 ring-white/10";
}

function severityTone(severity: string) {
  if (severity === "high") {
    return "bg-red-500/15 text-red-200 ring-1 ring-red-400/20";
  }
  if (severity === "medium") {
    return "bg-amber-500/15 text-amber-200 ring-1 ring-amber-400/20";
  }
  return "bg-sky-500/15 text-sky-200 ring-1 ring-sky-400/20";
}

function resultModeLabel(resultMode: PersonaSessionRecord["result_mode"]) {
  if (resultMode === "salvaged") {
    return "Salvaged evidence";
  }
  if (resultMode === "failed") {
    return "Failed";
  }
  return "Structured output";
}

function evaluationSummary(run: RunDetail) {
  if (run.evaluation_status === "completed") {
    const usedAsiFallback = run.evaluations.some((evaluation) => evaluation.source === "fetch_ai_asi_fallback");
    if (usedAsiFallback) {
      return "Hosted Fetch.ai review completed through the ASI fallback path.";
    }
    return run.evaluations.length
      ? "Hosted Fetch.ai synthesis completed."
      : "Hosted Fetch.ai synthesis completed without saved audience evaluations.";
  }
  if (run.evaluation_status === "failed") {
    return run.evaluation_error ?? "Hosted Fetch.ai evaluation failed.";
  }
  if (run.evaluation_status === "running" || run.evaluation_status === "pending") {
    return "Waiting for hosted Fetch.ai review to finish.";
  }
  return "Fetch.ai evaluation is not configured yet.";
}

function sourceReviewSummary(run: RunDetail) {
  if (run.source_review_status === "completed") {
    return "GPT source review completed.";
  }
  if (run.source_review_status === "failed") {
    return run.source_review_error ?? "GPT source review failed.";
  }
  if ((run.source_review_status === "running" || run.source_review_status === "pending") && run.source_review_error) {
    return run.source_review_error;
  }
  if (run.source_review_status === "running" || run.source_review_status === "pending") {
    return "GPT source review is still processing the linked repo.";
  }
  return "Source review is unavailable for this run.";
}

function liveSessionCards(run: RunDetail) {
  const cards: LiveSessionCard[] = [];
  const seenUrls = new Set<string>();

  for (const persona of run.persona_sessions) {
    if (!persona.live_url) {
      continue;
    }
    if (seenUrls.has(persona.live_url)) {
      continue;
    }
    seenUrls.add(persona.live_url);
    cards.push({
      id: persona.id,
      label: persona.display_label,
      liveUrl: persona.live_url,
    });
  }

  if (cards.length === 0 && run.live_url && !isDemoRecordId(run.id)) {
    cards.push({
      id: `${run.id}-aggregate-live`,
      label: "Aggregate session",
      liveUrl: run.live_url,
    });
  }

  return cards;
}

function compactProgress<T extends { created_at: string }>(items: T[], limit = 6) {
  return [...items]
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .slice(0, limit);
}

function issueImageFocus(issue: RunDetail["issues"][number]) {
  const haystack = `${issue.title} ${issue.summary} ${issue.evidence.join(" ")}`.toLowerCase();
  if (haystack.includes("faq") || haystack.includes("accordion")) {
    return "origin-top scale-[1.42] object-[50%_20%]";
  }
  if (haystack.includes("hero") || haystack.includes("headline") || haystack.includes("messaging")) {
    return "origin-top scale-[1.25] object-[50%_15%]";
  }
  if (haystack.includes("pricing") || haystack.includes("plan")) {
    return "origin-center scale-[1.32] object-[50%_45%]";
  }
  if (haystack.includes("footer")) {
    return "origin-bottom scale-[1.38] object-[50%_88%]";
  }
  if (haystack.includes("nav") || haystack.includes("header") || haystack.includes("menu")) {
    return "origin-top scale-[1.3] object-[50%_10%]";
  }
  if (haystack.includes("cta") || haystack.includes("button") || haystack.includes("signup")) {
    return "origin-center scale-[1.34] object-[50%_42%]";
  }
  return "origin-center scale-[1.18] object-center";
}

function DetailOverlay({
  run,
  section,
  onClose,
  onRetryFetch,
  retryingFetch,
}: {
  run: RunDetail;
  section: OverlaySection | null;
  onClose: () => void;
  onRetryFetch: () => void;
  retryingFetch: boolean;
}) {
  const recentRunProgress = compactProgress(run.progress, 12);

  if (!section) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end bg-black/70 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex h-[calc(100vh-2rem)] w-full max-w-2xl flex-col overflow-hidden border hairline-border border-white/10 bg-[#0c0c0c]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-zinc-600">Run detail</p>
            <h2 className="mt-1 font-display text-2xl text-white">
              {section === "logs"
                ? "Run logs"
                : section === "personas"
                  ? "Persona sessions"
                  : section === "fetch"
                    ? "Fetch.ai review"
                      : "Source review"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center justify-center border border-white/10 p-2 text-slate-300 transition hover:bg-white/5 hover:text-white"
            aria-label="Close detail panel"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          {section === "logs" ? (
            <div className="space-y-3">
              {recentRunProgress.length > 0 ? (
                recentRunProgress.map((entry) => (
                  <div key={entry.id} className="border hairline-border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center justify-between gap-3 text-xs uppercase tracking-[0.18em] text-zinc-500">
                      <span>{entry.type}</span>
                      <span>{formatDate(entry.created_at)}</span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-200">{entry.summary}</p>
                    {entry.screenshot_url ? (
                      <div className="mt-4">
                        <SmartImage
                          src={entry.screenshot_url}
                          alt={`${entry.summary} screenshot`}
                          className="h-44 w-full rounded-[1.25rem] object-cover"
                        />
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-sm text-zinc-500">No run logs yet.</p>
              )}
            </div>
          ) : null}

          {section === "fetch" ? (
            <div className="space-y-4">
              <div className="border hairline-border border-white/10 bg-black/20 p-4">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(run.evaluation_status)}`}>
                    {run.evaluation_status}
                  </span>
                  {run.evaluation_status === "completed" ? (
                    <CheckCircle2 className="size-4 text-emerald-300" />
                  ) : run.evaluation_status === "failed" ? (
                    <AlertTriangle className="size-4 text-red-300" />
                  ) : null}
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-200">{evaluationSummary(run)}</p>
                {run.evaluation_status === "failed" ? (
                  <button
                    type="button"
                    onClick={onRetryFetch}
                    disabled={retryingFetch}
                    className="mt-4 inline-flex items-center gap-2 border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {retryingFetch ? "Retrying..." : "Retry Fetch review"}
                  </button>
                ) : null}
              </div>

              {run.evaluations.length > 0 ? (
                run.evaluations.map((evaluation) => (
                  <div key={evaluation.id} className="border hairline-border border-white/10 bg-black/20 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-white">{evaluation.issue_title}</p>
                      <span className="border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                        {evaluation.audience}
                      </span>
                      <span className="border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                        {evaluation.priority}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{evaluation.impact_summary}</p>
                    <p className="mt-3 text-sm leading-6 text-slate-200">{evaluation.rationale}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-zinc-500">No saved Fetch.ai evaluation items.</p>
              )}
            </div>
          ) : null}

          {section === "source" ? (
            <div className="space-y-4">
              <div className="border hairline-border border-white/10 bg-black/20 p-4">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusTone(run.source_review_status)}`}>
                    {run.source_review_status}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-200">{sourceReviewSummary(run)}</p>
              </div>

              {run.recommendations.filter((recommendation) => recommendation.source === "source_review_gpt").length > 0 ? (
                run.recommendations
                  .filter((recommendation) => recommendation.source === "source_review_gpt")
                  .map((recommendation) => (
                    <div key={recommendation.id} className="border hairline-border border-white/10 bg-black/20 p-4">
                      <p className="text-sm font-medium text-white">{recommendation.title}</p>
                      <p className="mt-3 text-sm leading-6 text-slate-300">{recommendation.summary}</p>
                      <div className="mt-4 border border-white/10 bg-white/[0.02] p-4 text-sm text-slate-200">
                        {recommendation.likely_fix}
                      </div>
                    </div>
                  ))
              ) : (
                <p className="text-sm text-zinc-500">No saved GPT source-review recommendations yet.</p>
              )}
            </div>
          ) : null}

          {section === "personas" ? (
            <div className="space-y-4">
              {run.persona_sessions.map((persona) => (
                <details key={persona.id} className="border hairline-border border-white/10 bg-black/20 p-4">
                  <summary className="cursor-pointer list-none">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-white">{persona.display_label}</span>
                      <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${statusTone(persona.status)}`}>
                        {persona.status}
                      </span>
                      {persona.result_mode ? (
                        <span className="border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                          {resultModeLabel(persona.result_mode)}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm text-zinc-500">{persona.mission}</p>
                  </summary>

                  <div className="mt-4 space-y-4">
                    {persona.summary ? <p className="text-sm leading-6 text-slate-200">{persona.summary}</p> : null}
                    {persona.error_message ? (
                      <div className="border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                        {persona.error_message}
                      </div>
                    ) : null}

                    {persona.observations.length > 0 ? (
                      <div className="space-y-3">
                        {persona.observations.map((observation) => (
                          <div key={observation.id} className="border border-white/10 bg-white/[0.02] p-4">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-medium text-white">{observation.title}</p>
                              <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${severityTone(observation.severity)}`}>
                                {observation.severity}
                              </span>
                            </div>
                            <p className="mt-3 text-sm leading-6 text-slate-300">{observation.description}</p>
                            {observation.screenshot_url ? (
                              <div className="mt-4">
                                <SmartImage
                                  src={observation.screenshot_url}
                                  alt={`${observation.title} evidence screenshot`}
                                  className="h-48 w-full rounded-[1.25rem] object-cover"
                                />
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </details>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function RunDetailPanel({ run }: RunDetailPanelProps) {
  const [overlaySection, setOverlaySection] = useState<OverlaySection | null>(null);
  const [retryingFetch, setRetryingFetch] = useState(false);
  const [fetchRetryError, setFetchRetryError] = useState<string | null>(null);
  const liveSessions = useMemo(() => liveSessionCards(run), [run]);
  const topIssues = useMemo(() => {
    const severityRank = { high: 3, medium: 2, low: 1 } as const;
    return [...run.issues]
      .sort((left, right) => {
        const severityDelta = severityRank[right.severity] - severityRank[left.severity];
        if (severityDelta !== 0) {
          return severityDelta;
        }
        const personaDelta = right.personas.length - left.personas.length;
        if (personaDelta !== 0) {
          return personaDelta;
        }
        return right.evidence.length - left.evidence.length;
      })
      .slice(0, 6);
  }, [run.issues]);
  const analyzerRecommendations = useMemo(
    () => run.recommendations.filter((recommendation) => recommendation.source !== "source_review_gpt"),
    [run.recommendations],
  );
  const sourceRecommendations = useMemo(
    () => run.recommendations.filter((recommendation) => recommendation.source === "source_review_gpt"),
    [run.recommendations],
  );
  const topFetchEvaluations = useMemo(() => run.evaluations.slice(0, 3), [run.evaluations]);
  const topRecommendations = useMemo(
    () => [...analyzerRecommendations, ...sourceRecommendations].slice(0, 4),
    [analyzerRecommendations, sourceRecommendations],
  );

  async function handleRetryFetch() {
    try {
      setRetryingFetch(true);
      setFetchRetryError(null);
      await retryFetchReview(run.id);
    } catch (error) {
      setFetchRetryError(error instanceof Error ? error.message : "Failed to retry Fetch review.");
    } finally {
      setRetryingFetch(false);
    }
  }

  return (
    <>
      <div className="space-y-6">
        <section className="border hairline-border border-white/10 bg-[#0c0c0c] p-6 md:p-8">
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-4 py-2 text-xs font-medium uppercase tracking-[0.22em] ${statusTone(run.status)}`}>
                  {run.status}
                </span>
                <span className={`rounded-full px-4 py-2 text-xs font-medium uppercase tracking-[0.22em] ${statusTone(run.evaluation_status)}`}>
                  Fetch {run.evaluation_status}
                </span>
                <span className={`rounded-full px-4 py-2 text-xs font-medium uppercase tracking-[0.22em] ${statusTone(run.source_review_status)}`}>
                  Source {run.source_review_status}
                </span>
                {run.repo_build_status !== "not_requested" ? (
                  <span className={`rounded-full px-4 py-2 text-xs font-medium uppercase tracking-[0.22em] ${statusTone(run.repo_build_status)}`}>
                    Repo {run.repo_build_status}
                  </span>
                ) : null}
              </div>

              <div className="space-y-3">
                <p className="text-xs uppercase tracking-[0.22em] text-zinc-600">Audit run {run.id}</p>
                <h1 className="font-display text-4xl tracking-[-0.03em] text-white md:text-5xl">
                  Focused evidence, not an endless scroll.
                </h1>
                <p className="max-w-3xl text-sm leading-7 text-zinc-500">
                  Review the strongest issues first. Keep the live sessions visible and open logs or persona detail only when you need more context.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => setOverlaySection("logs")}
                  className="inline-flex items-center gap-2 border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Logs className="size-4" />
                  View logs
                </button>
                <button
                  type="button"
                  onClick={() => setOverlaySection("personas")}
                  className="inline-flex items-center gap-2 border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5"
                >
                  <Bot className="size-4" />
                  Persona detail
                </button>
                <button
                  type="button"
                  onClick={() => setOverlaySection("fetch")}
                  className="inline-flex items-center gap-2 border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5"
                >
                  <Sparkles className="size-4" />
                  Fetch review
                </button>
                <button
                  type="button"
                  onClick={() => setOverlaySection("source")}
                  disabled={run.source_review_status === "skipped" && sourceRecommendations.length === 0}
                  className="inline-flex items-center gap-2 border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5"
                >
                  <Bot className="size-4" />
                  Source review
                </button>
              </div>

              {liveSessions.length > 0 ? (
                <div className="grid gap-4 lg:grid-cols-3">
                  {liveSessions.map((session) => (
                    <div key={session.id} className="overflow-hidden border hairline-border border-white/10 bg-black/20">
                      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                        <div>
                          <p className="text-xs uppercase tracking-[0.18em] text-zinc-600">Live Browser Use session</p>
                          <p className="mt-1 text-sm text-zinc-500">{session.label}</p>
                        </div>
                        <a
                          href={session.liveUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 border border-white/10 px-3 py-2 text-[11px] uppercase tracking-[0.2em] text-white transition hover:bg-white/5"
                        >
                          Open live
                          <ArrowUpRight className="size-4" />
                        </a>
                      </div>
                      <iframe
                        src={session.liveUrl}
                        title={`Browser Use live session - ${session.label}`}
                        className="h-72 w-full bg-black"
                      />
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="border hairline-border border-white/10 bg-black/20 p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.22em] text-zinc-600">Fetch review</p>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{evaluationSummary(run)}</p>
                  </div>
                  {run.evaluation_status === "failed" ? (
                    <button
                      type="button"
                      onClick={() => void handleRetryFetch()}
                      disabled={retryingFetch}
                      className="inline-flex items-center gap-2 border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {retryingFetch ? "Retrying..." : "Retry Fetch review"}
                    </button>
                  ) : null}
                </div>
                {fetchRetryError ? <p className="mt-3 text-sm text-red-100">{fetchRetryError}</p> : null}
                {topFetchEvaluations.length > 0 ? (
                  <div className="mt-5 grid gap-3">
                    {topFetchEvaluations.map((evaluation) => (
                      <div key={evaluation.id} className="border hairline-border border-white/10 bg-white/[0.02] p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-white">{evaluation.issue_title}</p>
                          <span className="border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                            {evaluation.audience}
                          </span>
                          <span className="border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-slate-300">
                            {evaluation.priority}
                          </span>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-slate-300">{evaluation.impact_summary}</p>
                        <p className="mt-2 text-sm leading-6 text-slate-200">{evaluation.rationale}</p>
                      </div>
                    ))}
                    {run.evaluations.length > topFetchEvaluations.length ? (
                      <button
                        type="button"
                        onClick={() => setOverlaySection("fetch")}
                        className="inline-flex items-center gap-2 self-start border border-white/10 px-4 py-2 text-xs uppercase tracking-[0.18em] text-white transition hover:bg-white/5"
                      >
                        View full Fetch review
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>

              {run.repo_build_error ? (
                <div className="border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                  {run.repo_build_error}
                </div>
              ) : null}

              {run.source_review_status === "failed" ? (
                <div className="border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                  {sourceReviewSummary(run)}
                </div>
              ) : null}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="border hairline-border border-white/10 bg-black/20 p-5">
                <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-500">
                  <Layers3 className="size-4" />
                  Issues
                </div>
                <p className="mt-4 font-display text-4xl text-white">{run.issues.length}</p>
              </div>
              <div className="border hairline-border border-white/10 bg-black/20 p-5">
                <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-500">
                  <Sparkles className="size-4" />
                  Recommendations
                </div>
                <p className="mt-4 font-display text-4xl text-white">{run.recommendations.length}</p>
                <p className="mt-2 text-xs text-zinc-500">
                  {sourceRecommendations.length} from GPT source review
                </p>
              </div>
              <div className="border hairline-border border-white/10 bg-black/20 p-5">
                <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-500">
                  <Bot className="size-4" />
                  Persona sessions
                </div>
                <p className="mt-4 font-display text-4xl text-white">{run.persona_sessions.length}</p>
              </div>
              <div className="border hairline-border border-white/10 bg-black/20 p-5">
                <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-500">
                  <Clock3 className="size-4" />
                  Updated
                </div>
                <p className="mt-4 text-sm text-slate-300">{formatDate(run.completed_at ?? run.started_at ?? run.created_at)}</p>
                {run.target_url ? (
                  <div className="mt-2 space-y-1">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-600">
                      {run.target_source === "repo_preview" ? "Audited preview" : "Audited target"}
                    </p>
                    <p className="truncate text-xs text-zinc-500">{run.target_url}</p>
                    {run.target_source === "repo_preview" && run.local_preview_url ? (
                      <p className="truncate text-xs text-zinc-600">Local preview: {run.local_preview_url}</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <article className="border hairline-border border-white/10 bg-[#0c0c0c] p-6">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-500">
              <Flag className="size-4" />
              Top issues
            </div>
            <div className="mt-5 grid gap-4">
              {topIssues.length > 0 ? (
                topIssues.map((issue) => {
                  const imageCandidates = issueImageCandidates(run, issue);

                  return (
                    <div key={issue.id} className="border hairline-border border-white/10 bg-black/20 p-5">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="font-display text-2xl text-white">{issue.title}</h2>
                        <span className={`rounded-full px-3 py-1 text-xs font-medium ${severityTone(issue.severity)}`}>
                          {issue.severity}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-300">{issue.summary}</p>
                      {issue.evidence.length > 0 ? (
                        <ul className="mt-4 grid gap-2 text-sm text-slate-200">
                          {issue.evidence.slice(0, 4).map((entry) => (
                            <li key={entry} className="border hairline-border border-white/10 bg-white/[0.02] px-3 py-2">
                              {entry}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                      {imageCandidates.length > 0 ? (
                        <div className="mt-4 overflow-hidden rounded-[1.25rem] bg-black/30">
                          <SmartImage
                            src={imageCandidates[0]}
                            fallbackSrcs={imageCandidates.slice(1)}
                            alt={`${issue.title} evidence screenshot`}
                            className={`h-60 w-full object-cover transition-transform duration-300 ${issueImageFocus(issue)}`}
                          />
                        </div>
                      ) : null}
                    </div>
                  );
                })
              ) : (
                <p className="text-sm text-zinc-500">No aggregate issues were captured for this run.</p>
              )}
            </div>
          </article>

          <article className="border hairline-border border-white/10 bg-[#0c0c0c] p-6">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-zinc-500">
              <Sparkles className="size-4" />
              Recommended fixes
            </div>
            <div className="mt-5 grid gap-4">
              {topRecommendations.length > 0 ? (
                topRecommendations.map((recommendation) => (
                  <div key={recommendation.id} className="border hairline-border border-white/10 bg-black/20 p-5">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="font-display text-2xl text-white">{recommendation.title}</h2>
                      <span className="border hairline-border border-white/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-slate-300">
                        {recommendation.source === "source_review_gpt" ? "source review" : recommendation.source}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">{recommendation.summary}</p>
                    <div className="mt-4 border hairline-border border-white/10 bg-white/[0.02] p-4 text-sm text-slate-200">
                      {recommendation.likely_fix}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-zinc-500">No recommendations were generated for this run.</p>
              )}
            </div>
          </article>
        </section>

        {run.status === "failed" && run.error_message ? (
          <section className="border hairline-border border-red-400/15 bg-red-500/10 p-6">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.22em] text-red-200">
              <AlertTriangle className="size-4" />
              Run failure
            </div>
            <p className="mt-4 text-sm leading-6 text-red-50">{run.error_message}</p>
          </section>
        ) : null}

        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">
          <Link href="/app" className="transition hover:text-white">
            Back to workspace
          </Link>
        </div>
      </div>

      <DetailOverlay
        run={run}
        section={overlaySection}
        onClose={() => setOverlaySection(null)}
        onRetryFetch={() => void handleRetryFetch()}
        retryingFetch={retryingFetch}
      />
    </>
  );
}
