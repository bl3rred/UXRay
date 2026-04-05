import type {
  ProjectDetail,
  ProjectInput,
  ProjectSummary,
  RunDetail,
  RunInput,
  RunSummary,
} from "./types";
import {
  createDemoProject,
  createDemoRun,
  getDemoProject,
  getDemoRun,
  listDemoProjects,
} from "./demo-data";
import { readGuestSessionId } from "./browser-session";
import { getSupabaseBrowserClient, hasSupabaseAuthConfig } from "./supabase";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const REQUEST_TIMEOUT_MS = 10000;

export function resolveAssetUrl(pathOrUrl: string) {
  if (/^(https?:|data:|blob:)/i.test(pathOrUrl)) {
    return pathOrUrl;
  }

  const normalized = pathOrUrl.replace(/^\/+/, "");
  if (!normalized) {
    return "";
  }

  if (normalized.startsWith("artifacts/")) {
    return `${API_BASE_URL}/${normalized}`;
  }

  const encodedPath = normalized
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${API_BASE_URL}/artifacts/${encodedPath}`;
}

type Envelope<T> = {
  success: boolean;
  data: T;
  error: string | null;
};

function canUseDemoFallback() {
  return Boolean(readGuestSessionId());
}

async function buildHeaders(init?: RequestInit) {
  const headers = new Headers(init?.headers ?? {});
  headers.set("Content-Type", "application/json");

  const guestSessionId = readGuestSessionId();
  if (guestSessionId) {
    headers.set("X-Guest-Session", guestSessionId);
  }

  if (hasSupabaseAuthConfig()) {
    try {
      const client = getSupabaseBrowserClient();
      const {
        data: { session },
      } = await client.auth.getSession();

      if (session?.access_token) {
        headers.set("Authorization", `Bearer ${session.access_token}`);
      }
    } catch {
      // Keep requests working even when auth is not active yet.
    }
  }

  return headers;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: await buildHeaders(init),
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed with ${response.status}`);
    }

    const payload = (await response.json()) as Envelope<T>;
    return payload.data;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function resolveWithDemoFallback<T>(
  liveRequest: () => Promise<T>,
  demoRequest: () => T,
) {
  try {
    return await liveRequest();
  } catch (error) {
    if (canUseDemoFallback()) {
      return demoRequest();
    }

    throw error;
  }
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return resolveWithDemoFallback(
    () => apiFetch<ProjectSummary[]>("/projects"),
    () => listDemoProjects(),
  );
}

export async function createProject(input: ProjectInput): Promise<ProjectDetail> {
  return resolveWithDemoFallback(
    () =>
      apiFetch<ProjectDetail>("/projects", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    () => createDemoProject(input),
  );
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
  return resolveWithDemoFallback(
    () => apiFetch<ProjectDetail>(`/projects/${projectId}`),
    () => getDemoProject(projectId),
  );
}

export async function createRun(projectId: string, input?: RunInput): Promise<RunSummary> {
  return resolveWithDemoFallback(
    () =>
      apiFetch<RunSummary>(`/projects/${projectId}/runs`, {
        method: "POST",
        body: JSON.stringify(input ?? {}),
      }),
    () => createDemoRun(projectId, input),
  );
}

export async function getRun(runId: string): Promise<RunDetail> {
  return resolveWithDemoFallback(
    () => apiFetch<RunDetail>(`/runs/${runId}`),
    () => getDemoRun(runId),
  );
}

export async function retryFetchReview(runId: string): Promise<RunDetail> {
  return apiFetch<RunDetail>(`/runs/${runId}/retry-fetch`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
