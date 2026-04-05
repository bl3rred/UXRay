"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FolderOpen, LogOut, Plus } from "lucide-react";
import { useCallback } from "react";

import { listProjects } from "../lib/api";
import { useAuth } from "../lib/auth";
import { usePolling } from "../lib/hooks";

export function ProjectSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { mode, user, signOut } = useAuth();
  const loader = useCallback(() => listProjects(), []);
  const { data: projects, error } = usePolling(loader, 5000, true);

  async function handleSignOut() {
    await signOut();
    router.replace("/login");
  }

  return (
    <aside className="flex min-h-full flex-col border-b hairline-border border-white/10 bg-[#0c0c0c] px-5 py-5 lg:border-b-0 lg:border-r">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <Link href="/app" className="block">
            <img
              alt="UXRay"
              src="/logo transparent background.png"
              className="h-14 w-[220px] object-contain object-left"
            />
          </Link>
          <button
            className="inline-flex cursor-pointer items-center gap-2 border border-white/10 px-3 py-2 text-[11px] uppercase tracking-[0.2em] text-white transition hover:bg-white/5"
            onClick={() => void handleSignOut()}
            type="button"
          >
            <LogOut className="size-3.5" />
            {mode === "guest" ? "Exit" : "Sign out"}
          </button>
        </div>

        <div className="border hairline-border border-white/10 bg-white/[0.02] p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-zinc-600">Projects</p>
              <p className="mt-1 text-sm text-zinc-500">{mode === "guest" ? "Guest workspace" : user?.email ?? "Saved audits"}</p>
            </div>
            <Link
              href="/app"
              className="inline-flex items-center gap-1 border border-white/10 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-white transition hover:bg-white/5"
            >
              <Plus className="size-3.5" />
              New
            </Link>
          </div>

          {error ? <p className="mt-4 text-sm text-red-400">{error}</p> : null}

          {!projects?.length ? (
            <div className="mt-4 border border-dashed border-white/10 px-4 py-6 text-sm text-zinc-500">
              No projects yet. Create one or use the demo preview.
            </div>
          ) : (
            <nav className="mt-4 space-y-2">
              {projects.map((project) => {
                const href = `/app/projects/${project.id}`;
                const active = pathname === href;
                return (
                  <Link
                    key={project.id}
                    href={href}
                    className={`block border px-4 py-3 transition ${
                      active
                        ? "border-blue-400/20 bg-blue-500/10"
                        : "border-white/6 bg-white/[0.02] hover:border-white/12 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex size-9 items-center justify-center border hairline-border border-white/10 bg-black/20 text-[#adc6ff]">
                        <FolderOpen className="size-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white">
                          {project.name}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {project.url ?? project.repo_url ?? "Repo-backed project"}
                        </p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </nav>
          )}
        </div>
      </div>
    </aside>
  );
}
