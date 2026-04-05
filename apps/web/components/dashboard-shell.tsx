"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "../lib/auth";
import { AuthEntryPanel } from "./auth-entry-panel";
import { ProjectSidebar } from "./project-sidebar";

type DashboardShellProps = {
  children: React.ReactNode;
};

export function DashboardShell({ children }: DashboardShellProps) {
  const router = useRouter();
  const {
    mode,
    error,
    isSupabaseConfigured,
    continueAsGuest,
    signInWithGitHub,
  } = useAuth();

  useEffect(() => {
    if (mode === "guest" || mode === "authenticated") {
      router.prefetch("/app");
    }
  }, [mode, router]);

  if (mode === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <p className="text-sm text-body">Checking session...</p>
      </main>
    );
  }

  if (mode === "signed_out") {
    return (
      <main className="min-h-screen px-5 py-6 md:px-8 lg:px-10">
        <AuthEntryPanel
          error={error}
          isSupabaseConfigured={isSupabaseConfigured}
          onContinueAsGuest={continueAsGuest}
          onSignInWithGitHub={signInWithGitHub}
        />
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[#080808] px-3 py-3 md:px-4 md:py-4">
      <div className="mx-auto grid min-h-[calc(100vh-1.5rem)] max-w-[1660px] overflow-hidden rounded-sm border hairline-border border-white/10 bg-[#0c0c0c] lg:grid-cols-[280px_1fr]">
        <ProjectSidebar />
        <main className="min-w-0 border-l hairline-border border-white/5 bg-[#080808] px-5 py-5 md:px-8 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
