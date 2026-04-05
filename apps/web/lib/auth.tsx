"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";

import {
  clearDemoState,
  clearGuestSession,
  ensureGuestSession,
  readGuestSessionId,
} from "./browser-session";
import { getSupabaseBrowserClient, hasSupabaseAuthConfig } from "./supabase";

type AuthMode = "loading" | "signed_out" | "guest" | "authenticated";

type AuthContextValue = {
  mode: AuthMode;
  user: User | null;
  isSupabaseConfigured: boolean;
  error: string | null;
  continueAsGuest: () => void;
  signInWithGitHub: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function getGitHubOAuthMisconfigurationMessage(supabaseUrl: string) {
  const providerCallbackUrl = supabaseUrl
    ? `${supabaseUrl.replace(/\/$/, "")}/auth/v1/callback`
    : "https://<project-ref>.supabase.co/auth/v1/callback";

  return [
    "GitHub sign-in is misconfigured in Supabase.",
    "Set the GitHub provider Client ID and Client Secret from your GitHub OAuth App.",
    `GitHub OAuth App callback URL must be ${providerCallbackUrl}.`,
  ].join(" ");
}

export function getValidatedGitHubOAuthUrl(urlValue: string, supabaseUrl: string) {
  try {
    const authUrl = new URL(urlValue);
    const clientId = authUrl.searchParams.get("client_id");

    if (
      authUrl.hostname === "github.com" &&
      authUrl.pathname === "/login/oauth/authorize" &&
      (!clientId || clientId.includes("@"))
    ) {
      return {
        error: getGitHubOAuthMisconfigurationMessage(supabaseUrl),
        url: null,
      };
    }

    return {
      error: null,
      url: authUrl.toString(),
    };
  } catch {
    return {
      error: null,
      url: urlValue,
    };
  }
}

function createAuthErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Authentication failed.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<AuthMode>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isSupabaseConfigured = hasSupabaseAuthConfig();

  useEffect(() => {
    let mounted = true;
    let unsubscribe: (() => void) | undefined;

    async function initialize() {
      const guestSessionId = readGuestSessionId();

      if (!isSupabaseConfigured) {
        if (mounted) {
          setMode(guestSessionId ? "guest" : "signed_out");
          setUser(null);
        }
        return;
      }

      try {
        const client = getSupabaseBrowserClient();
        const [{ data }, listener] = await Promise.all([
          client.auth.getUser(),
          Promise.resolve(
            client.auth.onAuthStateChange((_event, session) => {
              if (!mounted) {
                return;
              }

              if (session?.user) {
                clearGuestSession();
                clearDemoState();
                setUser(session.user);
                setMode("authenticated");
                setError(null);
                return;
              }

              const nextGuestSessionId = readGuestSessionId();
              setUser(null);
              setMode(nextGuestSessionId ? "guest" : "signed_out");
            }),
          ),
        ]);

        unsubscribe = () => {
          listener.data.subscription.unsubscribe();
        };

        if (!mounted) {
          return;
        }

        if (data.user) {
          clearGuestSession();
          clearDemoState();
          setUser(data.user);
          setMode("authenticated");
          return;
        }

        setUser(null);
        setMode(guestSessionId ? "guest" : "signed_out");
      } catch (nextError) {
        if (!mounted) {
          return;
        }

        setError(createAuthErrorMessage(nextError));
        setMode(guestSessionId ? "guest" : "signed_out");
      }
    }

    void initialize();

    return () => {
      mounted = false;
      unsubscribe?.();
    };
  }, [isSupabaseConfigured]);

  const continueAsGuest = useCallback(() => {
    ensureGuestSession();
    setError(null);
    setUser(null);
    setMode("guest");
  }, []);

  const signInWithGitHub = useCallback(async () => {
    setError(null);

    if (!isSupabaseConfigured) {
      setError(
        "GitHub sign-in is not configured yet. Continue as guest for the demo, or add Supabase auth env vars.",
      );
      return;
    }

    try {
      clearGuestSession();
      clearDemoState();
      const client = getSupabaseBrowserClient();
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
      const redirectTo = `${window.location.origin}/auth/callback?next=/app`;
      const { data, error: authError } = await client.auth.signInWithOAuth({
        provider: "github",
        options: {
          redirectTo,
          skipBrowserRedirect: true,
        },
      });

      if (authError) {
        throw authError;
      }

      if (!data?.url) {
        throw new Error("GitHub sign-in could not start because no authorization URL was returned.");
      }

      const validatedRedirect = getValidatedGitHubOAuthUrl(data.url, supabaseUrl);
      if (validatedRedirect.error) {
        throw new Error(validatedRedirect.error);
      }

      if (!validatedRedirect.url) {
        throw new Error("GitHub sign-in could not start because the authorization URL was invalid.");
      }

      window.location.assign(validatedRedirect.url);
    } catch (nextError) {
      setError(createAuthErrorMessage(nextError));
    }
  }, [isSupabaseConfigured]);

  const signOut = useCallback(async () => {
    setError(null);
    clearGuestSession();
    clearDemoState();

    if (isSupabaseConfigured) {
      try {
        const client = getSupabaseBrowserClient();
        await client.auth.signOut();
      } catch (nextError) {
        setError(createAuthErrorMessage(nextError));
      }
    }

    setUser(null);
    setMode("signed_out");
  }, [isSupabaseConfigured]);

  const value = useMemo<AuthContextValue>(
    () => ({
      mode,
      user,
      isSupabaseConfigured,
      error,
      continueAsGuest,
      signInWithGitHub,
      signOut,
    }),
    [continueAsGuest, error, isSupabaseConfigured, mode, signInWithGitHub, signOut, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
