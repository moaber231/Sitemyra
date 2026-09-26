"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { CircleAlert, Loader2, Wand2 } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { AnalysisResult } from "@/components/intelligence/analysis-result";
import { ManualMonitorForm } from "@/components/intelligence/manual-monitor-form";
import { SpyThisPage } from "@/components/intelligence/spy-this-page";
import { UrlIntake } from "@/components/intelligence/url-intake";
import { analyzeUrl, getRecipes, type Recipe, type UrlAnalysis } from "@/lib/api/intelligence";

type Step = "intake" | "result" | "manual";

/**
 * Phase 1 intake. The whole page answers one question — "what should I
 * watch?" — and the technical form is still there for anyone who wants it.
 *
 * `useSearchParams` (the bookmarklet / extension hand-off) is read inside a
 * Suspense boundary so the route can stay statically prerendered.
 */
export default function NewMonitorPage() {
  return (
    <AppShell>
      <Suspense fallback={<IntakeSkeleton />}>
        <NewMonitorFlow />
      </Suspense>
    </AppShell>
  );
}

function IntakeSkeleton() {
  return (
    <div className="mx-auto max-w-4xl" aria-busy="true" aria-label="Loading">
      <div className="apeiro-card h-64 animate-pulse bg-muted/40" />
    </div>
  );
}

function NewMonitorFlow() {
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>("intake");
  const [url, setUrl] = useState("");
  const [analysis, setAnalysis] = useState<UrlAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [consumed, setConsumed] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionStorage.getItem("apeiro_access")) {
      window.location.href = "/login";
    }
  }, []);

  const { data: recipeData } = useQuery({
    queryKey: ["intelligence-recipes"],
    queryFn: getRecipes,
    retry: false,
  });

  const recipes: Recipe[] = recipeData?.recipes ?? [];
  const plan = recipeData?.plan ?? "free";

  async function handleAnalyze(nextUrl: string) {
    setLoading(true);
    setError("");
    setUrl(nextUrl);
    try {
      const result = await analyzeUrl(nextUrl);
      setAnalysis(result);
      setStep("result");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sitemyra could not read that URL.");
    } finally {
      setLoading(false);
    }
  }

  // "Monitor with Sitemyra" bookmarklet / extension hand-off: ?url=… is
  // analysed automatically so one click does the whole job. Guarded by
  // `consumed` so a re-render never fires the analysis twice.
  useEffect(() => {
    const incoming = searchParams.get("url");
    if (!incoming || consumed === incoming) return;
    setConsumed(incoming);
    void handleAnalyze(incoming);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, consumed]);

  function reset() {
    setAnalysis(null);
    setUrl("");
    setError("");
    setStep("intake");
  }

  return (
    <div className="relative mx-auto max-w-4xl">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -z-10 -top-16 right-0 h-64 w-64 rounded-full bg-accent/10 blur-3xl"
      />

      <div className="apeiro-stagger stagger-1">
        <DashboardHeader
          title={step === "manual" ? "Manual monitor" : "Watch a competitor"}
          parentHref="/dashboard/monitors"
          parentLabel="Monitors"
        />
      </div>

      {step === "intake" ? (
        <div className="apeiro-stagger stagger-2 mt-6 space-y-6">
          <p className="max-w-2xl text-base leading-7 text-muted-foreground">
            Paste a competitor or product URL. Sitemyra reads the page, works out what is
            worth watching, and sets it up for you. You do not need to know anything about
            monitoring.
          </p>

          <div className="apeiro-card p-6 sm:p-8">
            <UrlIntake onAnalyze={handleAnalyze} loading={loading} initialUrl={url} />
          </div>

          {error ? (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-muted px-3.5 py-3 text-sm text-danger"
            >
              <CircleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setStep("manual")}
              className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs"
            >
              <Wand2 size={14} aria-hidden="true" />
              Prefer to set up a monitor yourself?
            </button>
          </div>

          <SpyThisPage />

          {recipes.length > 0 ? (
            <div className="apeiro-card p-6">
              <p className="text-sm font-semibold text-foreground">What you can watch</p>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {recipes.map((recipe) => (
                  <li key={recipe.slug} className="rounded-xl border border-border bg-muted/30 p-3">
                    <p className="text-sm font-medium text-foreground">{recipe.name}</p>
                    <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                      {recipe.description}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {step === "result" && analysis ? (
        <div className="apeiro-stagger stagger-2 mt-6">
          {loading ? (
            <div className="apeiro-card flex items-center gap-3 p-8 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" aria-hidden="true" />
              Reading the page…
            </div>
          ) : (
            <AnalysisResult
              analysis={analysis}
              recipes={recipes}
              plan={plan}
              onReset={reset}
              onManual={() => setStep("manual")}
            />
          )}
        </div>
      ) : null}

      {step === "manual" ? (
        <div className="apeiro-stagger stagger-2 mt-6 space-y-4">
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
            Advanced setup. Choose the name, frequency and timeout yourself — product and
            competitor intelligence is still available once the monitor exists.
          </p>
          <ManualMonitorForm initialUrl={url} />
          <button
            type="button"
            onClick={() => setStep(analysis ? "result" : "intake")}
            className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs"
          >
            Back to URL intelligence
          </button>
        </div>
      ) : null}
    </div>
  );
}
