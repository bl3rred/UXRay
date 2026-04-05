import { createServerClient } from "@supabase/ssr";
import type { NextRequest, NextResponse } from "next/server";

import { getSupabaseAuthConfig, hasSupabaseAuthConfig } from "./supabase-config";

type CookieAdapter = {
  getAll: () => { name: string; value: string }[];
  setAll: (
    cookiesToSet: { name: string; value: string; options?: Record<string, unknown> }[],
  ) => void;
};

function createCookieBoundSupabaseServerClient(cookies: CookieAdapter) {
  if (!hasSupabaseAuthConfig()) {
    return null;
  }

  const config = getSupabaseAuthConfig();

  return createServerClient(config.url, config.publishableKey, {
    cookies,
  });
}

export function createSupabaseRouteHandlerClient(
  request: NextRequest,
  response: NextResponse,
) {
  return createCookieBoundSupabaseServerClient({
    getAll() {
      return request.cookies.getAll();
    },
    setAll(cookiesToSet) {
      cookiesToSet.forEach(({ name, value, options }) => {
        response.cookies.set(name, value, options);
      });
    },
  });
}
