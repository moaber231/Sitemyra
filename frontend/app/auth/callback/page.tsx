"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { oauthCallback, type OAuthProvider } from "@/lib/api/developer";

/** Provider redirect target: completes the OAuth code+state exchange. */
export default function OAuthCallbackPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const provider = (
      sessionStorage.getItem("apeiro_oauth_provider") ?? ""
    ).toLowerCase();
    const code = params.get("code") ?? "";
    const state = params.get("state") ?? "";
    const providerError = params.get("error") ?? "";
    sessionStorage.removeItem("apeiro_oauth_provider");

    if (
      providerError ||
      !code ||
      (provider !== "google" && provider !== "github")
    ) {
      const message =
        providerError === "access_denied"
          ? "Authorization was not granted."
          : "Invalid OAuth callback. Please try signing in again.";
      window.location.href = `/login?oauth_error=${encodeURIComponent(message)}`;
      return;
    }

    oauthCallback(provider as OAuthProvider, { code, state })
      .then((result) => {
        sessionStorage.setItem("apeiro_access", result.access);
        sessionStorage.setItem("apeiro_refresh", result.refresh);
        window.location.href = "/dashboard";
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "SSO sign-in failed.",
        );
      });
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-5">
      <div className="apeiro-card w-full max-w-md p-6 text-center sm:p-8">
        {error ? (
          <>
            <h1 className="text-lg font-semibold">Sign-in failed</h1>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
            <Link
              href="/login"
              className="apeiro-btn apeiro-btn-primary mt-6 w-full"
            >
              Back to sign-in
            </Link>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" />
            Completing sign-in…
          </div>
        )}
      </div>
    </main>
  );
}
