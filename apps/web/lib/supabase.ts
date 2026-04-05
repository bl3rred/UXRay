"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseAuthConfig, hasSupabaseAuthConfig } from "./supabase-config";

let browserClient: SupabaseClient | null = null;

export function getSupabaseBrowserClient() {
  if (!hasSupabaseAuthConfig()) {
    throw new Error(
      "Supabase auth is not configured. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.",
    );
  }

  if (!browserClient) {
    const config = getSupabaseAuthConfig();
    browserClient = createBrowserClient(config.url, config.publishableKey);
  }

  return browserClient;
}

export { getSupabaseAuthConfig, hasSupabaseAuthConfig };
