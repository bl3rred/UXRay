"use client";

import { ArrowRight, Github } from "lucide-react";

import { Button } from "@/components/ui/button";

type AuthEntryPanelProps = {
  error: string | null;
  isSupabaseConfigured: boolean;
  onContinueAsGuest: () => void;
  onSignInWithGitHub: () => Promise<void>;
};

export function AuthEntryPanel({
  error,
  isSupabaseConfigured,
  onContinueAsGuest,
  onSignInWithGitHub,
}: AuthEntryPanelProps) {
  return (
    <section className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0c0c0c] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.32)] md:p-7">
      <div className="space-y-6">
        <div className="space-y-3 text-center">
          <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Access UXRay</p>
          <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-white">
            Sign in
          </h1>
          <p className="text-sm leading-7 text-zinc-500">
            Use GitHub to keep your audits, or continue as guest for a quick preview.
          </p>
        </div>

        <div className="space-y-3">
          <Button
            className="h-11 w-full justify-start border-white/10 px-4 text-white shadow-none hover:bg-white/5 focus-visible:outline-white/20"
            onClick={() => void onSignInWithGitHub()}
            type="button"
            variant="outline"
          >
            <span className="pointer-events-none mr-3 flex-1">
              <Github className="size-4 opacity-70" />
            </span>
            Login with GitHub
            <span className="flex-1" />
          </Button>

          <Button
            className="h-11 w-full justify-start px-4"
            onClick={onContinueAsGuest}
            type="button"
            variant="outline"
          >
            <span className="pointer-events-none mr-3 flex-1" />
            Continue as guest
            <ArrowRight className="size-4 opacity-70" />
            <span className="flex-1" />
          </Button>
        </div>

        {error ? <p className="text-sm text-red-300">{error}</p> : null}

        {!isSupabaseConfigured ? (
          <p className="text-xs leading-6 text-zinc-600">
            GitHub sign-in is not configured in this environment yet. Guest mode is still
            available.
          </p>
        ) : null}
      </div>
    </section>
  );
}
