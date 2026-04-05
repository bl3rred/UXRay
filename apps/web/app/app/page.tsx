"use client";

import { useRouter } from "next/navigation";

import { ProjectForm } from "../../components/project-form";
import { createProject } from "../../lib/api";

export default function DashboardPage() {
  const router = useRouter();

  async function handleCreateProject(input: {
    name: string;
    url?: string;
    repo_url?: string;
  }) {
    const project = await createProject(input);
    router.push(`/app/projects/${project.id}`);
  }

  return (
    <div className="space-y-6">
      <ProjectForm onCreate={handleCreateProject} />
    </div>
  );
}
