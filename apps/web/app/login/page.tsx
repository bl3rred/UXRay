"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthEntryPanel } from "../../components/auth-entry-panel";
import { useAuth } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const {
    mode,
    error,
    isSupabaseConfigured,
    continueAsGuest,
    signInWithGitHub,
  } = useAuth();

  useEffect(() => {
    if (mode === "authenticated") {
      router.replace("/app");
    }
  }, [mode, router]);

  return (
    <main className="flex min-h-screen items-center justify-center px-5 py-10 md:px-8">
      <div className="w-full max-w-md">
        <AuthEntryPanel
          error={error}
          isSupabaseConfigured={isSupabaseConfigured}
          onContinueAsGuest={() => {
            continueAsGuest();
            router.replace("/app");
          }}
          onSignInWithGitHub={signInWithGitHub}
        />
      </div>
    </main>
  );
}
