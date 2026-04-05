"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Globe, Github } from "lucide-react";

import type { ProjectInput } from "../lib/types";

type ProjectFormProps = {
  onCreate: (input: ProjectInput) => Promise<void>;
};

export function ProjectForm({ onCreate }: ProjectFormProps) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const trimmedUrl = url.trim();
    const trimmedRepoUrl = repoUrl.trim();

    if (!trimmedUrl && !trimmedRepoUrl) {
      setError("Add a website URL or a public repository URL.");
      setSubmitting(false);
      return;
    }

    try {
      await onCreate({
        name,
        ...(trimmedUrl ? { url: trimmedUrl } : {}),
        ...(trimmedRepoUrl ? { repo_url: trimmedRepoUrl } : {}),
      });
      setName("");
      setUrl("");
      setRepoUrl("");
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Failed to create project",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="border hairline-border border-white/10 bg-[#0c0c0c] p-6 md:p-8" onSubmit={handleSubmit}>
      <div className="space-y-5">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.22em] text-zinc-600">Create project</p>
          <h2 className="font-display text-3xl font-semibold tracking-[-0.03em] text-white md:text-4xl">
            Audit a live site or launch one from a public repo.
          </h2>
          <p className="max-w-2xl text-sm leading-7 text-zinc-500">
            Add a public site, a public GitHub repo, or both. If a supported repo is
            present, UXRay will try to build a local preview first.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <label className="block text-sm text-white">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-zinc-600">
              Project name
            </span>
            <input
              className="w-full border hairline-border border-white/10 bg-black/20 px-4 py-3 text-white outline-none transition focus:border-[#adc6ff]/50"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>

          <label className="block text-sm text-white">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-zinc-600">
              Website URL
            </span>
            <div className="flex items-center border hairline-border border-white/10 bg-black/20 px-4">
              <Globe className="size-4 text-zinc-600" />
              <input
                className="w-full bg-transparent px-3 py-3 text-white outline-none"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com"
              />
            </div>
          </label>

          <label className="block text-sm text-white">
            <span className="mb-2 block text-xs uppercase tracking-[0.18em] text-zinc-600">
              Public repository URL
            </span>
            <div className="flex items-center border hairline-border border-white/10 bg-black/20 px-4">
              <Github className="size-4 text-zinc-600" />
              <input
                className="w-full bg-transparent px-3 py-3 text-white outline-none"
                type="url"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
              />
            </div>
          </label>
        </div>

        {error ? <p className="text-sm text-red-300">{error}</p> : null}

        <button
          className="inline-flex cursor-pointer items-center gap-2 bg-white px-5 py-3 text-xs font-bold uppercase tracking-[0.22em] text-black transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={submitting}
          type="submit"
        >
          {submitting ? "Creating..." : "Create project"}
          <ArrowRight className="size-4" />
        </button>
      </div>
    </form>
  );
}
