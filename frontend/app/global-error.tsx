"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="bg-background text-foreground">
        <main className="auth-shell flex min-h-screen items-center justify-center px-6">
          <div className="apeiro-card w-full max-w-md p-8 text-center shadow-lg">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-danger-muted text-danger">
              <span className="h-3 w-3 rounded-full bg-danger" aria-hidden="true" />
            </div>

            <h1 className="font-display text-3xl font-normal text-foreground">
              Something went wrong
            </h1>

            <p className="mt-2 text-sm text-muted-foreground">
              Sitemyra encountered an unexpected error.
            </p>

            <button
              type="button"
              onClick={reset}
              className="apeiro-btn apeiro-btn-primary mt-6"
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}