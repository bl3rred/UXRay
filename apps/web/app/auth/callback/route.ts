import { NextRequest, NextResponse } from "next/server";

import { createSupabaseRouteHandlerClient } from "../../../lib/supabase-server";

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const origin = requestUrl.origin;

  try {
    const code = requestUrl.searchParams.get("code");
    let next = requestUrl.searchParams.get("next") ?? "/app";

    if (!next.startsWith("/")) {
      next = "/app";
    }

    if (!code) {
      return NextResponse.redirect(`${origin}/auth/auth-code-error`);
    }

    const forwardedHost = request.headers.get("x-forwarded-host");
    const isLocalEnv = process.env.NODE_ENV === "development";
    const redirectTarget =
      isLocalEnv || !forwardedHost ? `${origin}${next}` : `https://${forwardedHost}${next}`;
    const response = NextResponse.redirect(redirectTarget);
    const supabase = createSupabaseRouteHandlerClient(request, response);

    if (!supabase) {
      return NextResponse.redirect(`${origin}/auth/auth-code-error`);
    }

    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (error) {
      console.error("Supabase auth callback exchange failed", error);
      return NextResponse.redirect(`${origin}/auth/auth-code-error`);
    }

    return response;
  } catch (error) {
    console.error("Supabase auth callback threw", error);
    return NextResponse.redirect(`${origin}/auth/auth-code-error`);
  }
}
