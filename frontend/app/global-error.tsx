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
        <main className="flex min-h-screen items-center justify-center px-6">
          <div className="apeiro-card w-full max-w-md p-8 text-center">
            <div className="mx-auto mb-4 h-3 w-3 rounded-full bg-danger" />

            <h1 className="text-xl font-semibold">
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