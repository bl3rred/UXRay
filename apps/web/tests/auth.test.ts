import { describe, expect, it } from "vitest";

import { getValidatedGitHubOAuthUrl } from "../lib/auth";

describe("getValidatedGitHubOAuthUrl", () => {
  it("rejects GitHub OAuth URLs with an email-shaped client id", () => {
    const result = getValidatedGitHubOAuthUrl(
      "https://github.com/login/oauth/authorize?client_id=rfarrales25%40gmail.com&redirect_uri=https%3A%2F%2Fwqdbzhnmbklaerzdijnj.supabase.co%2Fauth%2Fv1%2Fcallback",
      "https://wqdbzhnmbklaerzdijnj.supabase.co",
    );

    expect(result.url).toBeNull();
    expect(result.error).toContain("GitHub sign-in is misconfigured in Supabase.");
    expect(result.error).toContain(
      "https://wqdbzhnmbklaerzdijnj.supabase.co/auth/v1/callback",
    );
  });

  it("allows valid GitHub OAuth URLs through unchanged", () => {
    const url =
      "https://github.com/login/oauth/authorize?client_id=Iv1.1234567890abcdef&redirect_uri=https%3A%2F%2Fwqdbzhnmbklaerzdijnj.supabase.co%2Fauth%2Fv1%2Fcallback";
    const result = getValidatedGitHubOAuthUrl(
      url,
      "https://wqdbzhnmbklaerzdijnj.supabase.co",
    );

    expect(result.error).toBeNull();
    expect(result.url).toBe(url);
  });
});
