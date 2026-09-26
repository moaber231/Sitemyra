"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  CircleAlert,
  Loader2,
  Sparkles,
  Star,
} from "lucide-react";

import { activateAnalysis, type Recipe, type UrlAnalysis } from "@/lib/api/intelligence";

import { RecipePicker } from "./recipe-picker";
import { Note, SectionLabel, formatMoney, relativeTime } from "./primitives";
import { SkippedList, TargetChecklist } from "./target-checklist";

type Status = "idle" | "analyzing" | "ready" | "activating" | "done";

/**
 * The whole Phase 1 intake journey in one component:
 *
 *   paste URL → see what Sitemyra understood → choose a recipe or pick
 *   pages → monitoring starts
 *
 * Nothing here asks the user about intervals, selectors or monitoring
 * modes. The advanced controls live one click away, behind a disclosure.
 */
export function AnalysisResult({
  analysis,
  recipes,
  plan,
  onReset,
  onManual,
}: {
  analysis: UrlAnalysis;
  recipes: Recipe[];
  plan: string;
  onReset: () => void;
  onManual: () => void;
}) {
  const [status, setStatus] = useState<Status>("ready");
  const [recipe, setRecipe] = useState("");
  const [customized, setCustomized] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(analysis.targets.map((target) => target.id)),
  );
  const [error, setError] = useState("");
  const [result, setResult] = useState<Awaited<ReturnType<typeof activateAnalysis>> | null>(null);

  const summary = analysis.summary ?? {};
  const isProduct = analysis.product_detected;
  const currency = typeof summary.currency === "string" ? summary.currency : "";
  const headline = useMemo(() => {
    if (isProduct) {
      const name = typeof summary.name === "string" ? summary.name : "this product";
      return `This is a product page — ${name}`;
    }
    if (analysis.found_count > 0) {
      return `We found ${analysis.found_count} thing${analysis.found_count === 1 ? "" : "s"} worth monitoring.`;
    }
    return "Sitemyra read this page but found nothing to track yet.";
  }, [analysis.found_count, isProduct, summary.name]);

  function toggle(id: string) {
    setCustomized(true);
    setRecipe("");
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(selectAll: boolean) {
    setCustomized(true);
    setRecipe("");
    setSelected(selectAll ? new Set(analysis.targets.map((target) => target.id)) : new Set());
  }

  async function activate(useRecipe: string, targetIds: string[]) {
    setStatus("activating");
    setError("");
    try {
      const response = await activateAnalysis({
        analysis_id: analysis.id,
        recipe: useRecipe || undefined,
        target_ids: useRecipe ? undefined : targetIds,
      });
      setResult(response);
      setStatus("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sitemyra could not start monitoring.");
      setStatus("ready");
    }
  }

  if (status === "done" && result) {
    return (
      <ActivationSummary
        result={result}
        onWatchAnother={onReset}
      />
    );
  }

  const busy = status === "activating";

  return (
    <div className="space-y-6">
      {/* ---- headline ------------------------------------------------ */}
      <section className="apeiro-card overflow-hidden p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <SectionLabel>
              {analysis.page_kind_label} · confidence {analysis.classification_confidence}
            </SectionLabel>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {headline}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              {analysis.classification_rationale}
            </p>
          </div>
          <button type="button" onClick={onReset} className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs">
            Watch a different URL
          </button>
        </div>

        <dl className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border pt-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <dt>Source</dt>
            <dd className="truncate font-mono text-foreground">{analysis.url}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <dt>Read in</dt>
            <dd className="font-mono text-foreground">{analysis.response_time_ms ?? "—"} ms</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <dt>Checked</dt>
            <dd className="font-mono text-foreground">{relativeTime(analysis.fetched_at)}</dd>
          </div>
          {analysis.cached ? (
            <div className="flex items-center gap-1.5">
              <dt>Result</dt>
              <dd className="font-mono text-foreground">reused cached analysis</dd>
            </div>
          ) : null}
        </dl>
      </section>

      {/* ---- product card -------------------------------------------- */}
      {isProduct ? (
        <ProductSummary summary={summary} currency={currency} sourceUrl={analysis.url} />
      ) : (
        <Note>
          Sitemyra did not find product data on this page, so it will be monitored as a content
          page. That is still useful — you will be told when the page changes.
        </Note>
      )}

      {/* ---- actions -------------------------------------------------- */}
      <section className="apeiro-glass p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
              <Sparkles size={17} className="text-accent" aria-hidden="true" />
              {analysis.found_count > 0
                ? `We found ${analysis.found_count} thing${analysis.found_count === 1 ? "" : "s"} worth monitoring.`
                : "Nothing else on this site looks worth monitoring."}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Plan <span className="font-semibold capitalize text-foreground">{plan}</span> ·{" "}
              {analysis.found_count} target{analysis.found_count === 1 ? "" : "s"} found.
            </p>
          </div>
          <button
            type="button"
            disabled={busy || analysis.found_count === 0}
            onClick={() => activate("", analysis.targets.map((target) => target.id))}
            className="apeiro-btn apeiro-btn-accent shrink-0 !min-h-12"
          >
            {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
            {busy ? "Starting…" : "Monitor everything"}
          </button>
        </div>

        {error ? (
          <p role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-danger/30 bg-danger-muted px-3.5 py-3 text-sm text-danger">
            <CircleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            {error}
          </p>
        ) : null}

        <details
          className="mt-5 border-t border-border pt-4"
          open={customized}
          onToggle={(event) => setCustomized((event.currentTarget as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer list-none text-sm font-semibold text-accent underline decoration-accent/30 underline-offset-4 hover:text-accent-secondary">
            Customize what Sitemyra watches
          </summary>

          <div className="mt-5 space-y-6">
            <RecipePicker recipes={recipes} selected={recipe} onSelect={setRecipe} />

            {analysis.targets.length > 0 ? (
              <TargetChecklist
                targets={analysis.targets}
                selected={selected}
                onToggle={toggle}
                onToggleAll={toggleAll}
                disabled={busy}
              />
            ) : null}

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                disabled={busy || selected.size === 0}
                onClick={() => activate(recipe, [...selected])}
                className="apeiro-btn apeiro-btn-primary"
              >
                {busy ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : null}
                {busy
                  ? "Starting…"
                  : recipe
                    ? `Start ${recipes.find((entry) => entry.slug === recipe)?.name ?? "recipe"}`
                    : `Monitor ${selected.size} selected page${selected.size === 1 ? "" : "s"}`}
              </button>
              <button type="button" onClick={onManual} className="apeiro-btn apeiro-btn-outline">
                Set up a monitor manually
              </button>
            </div>
          </div>
        </details>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Product summary card
 * ------------------------------------------------------------------ */

function ProductSummary({
  summary,
  currency,
  sourceUrl,
}: {
  summary: Record<string, unknown>;
  currency: string;
  sourceUrl: string;
}) {
  const price = typeof summary.price === "string" ? summary.price : null;
  const listPrice = typeof summary.list_price === "string" ? summary.list_price : null;
  const availability = typeof summary.availability === "string" ? summary.availability : "";
  const rating = typeof summary.rating === "string" ? summary.rating : null;
  const reviews = typeof summary.review_count === "number" ? summary.review_count : null;
  const brand = typeof summary.brand === "string" ? summary.brand : "";
  const badges = Array.isArray(summary.badges) ? (summary.badges as string[]) : [];
  const variants = Array.isArray(summary.variants) ? (summary.variants as { label?: string }[]) : [];

  const discount =
    price && listPrice && Number(listPrice) > Number(price)
      ? Math.round(((Number(listPrice) - Number(price)) / Number(listPrice)) * 100)
      : null;

  return (
    <section className="apeiro-card overflow-hidden">
      <div className="border-b border-border bg-muted/30 px-6 py-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Star size={15} className="text-accent" aria-hidden="true" />
          What Sitemyra read from this page
        </p>
      </div>
      <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="Price" value={formatMoney(price, currency)} hint={discount ? `${discount}% off ${formatMoney(listPrice, currency)}` : undefined} />
        <Fact
          label="Availability"
          value={availability ? availability.replace(/_/g, " ") : "not published"}
          hint={availability ? undefined : "The page does not state availability."}
        />
        <Fact
          label="Rating"
          value={rating ?? "not published"}
          hint={reviews ? `${reviews} review${reviews === 1 ? "" : "s"}` : undefined}
        />
        <Fact
          label="Variants"
          value={variants.length ? `${variants.length} published` : "not published"}
          hint={brand || undefined}
        />
      </div>
      {badges.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-6 py-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Badges</span>
          {badges.map((badge) => (
            <span key={badge} className="apeiro-badge bg-secondary text-secondary-foreground">
              {badge}
            </span>
          ))}
        </div>
      ) : null}
      <div className="border-t border-border px-6 py-4">
        <p className="text-xs leading-5 text-muted-foreground">
          Read from the page&apos;s own published data.{" "}
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-accent underline decoration-accent/30 underline-offset-2"
          >
            Open the source page
          </a>{" "}
          to confirm before you act on it.
        </p>
      </div>
    </section>
  );
}

function Fact({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-card px-6 py-4">
      <p className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-1.5 text-lg font-semibold capitalize tracking-tight text-foreground">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Post-activation summary
 * ------------------------------------------------------------------ */

function ActivationSummary({
  result,
  onWatchAnother,
}: {
  result: Awaited<ReturnType<typeof activateAnalysis>>;
  onWatchAnother: () => void;
}) {
  const first = result.monitors[0];

  return (
    <div className="space-y-6">
      <section className="apeiro-card p-6 sm:p-8">
        <p className="flex items-center gap-2 text-sm font-semibold text-success">
          <BadgeCheck size={16} aria-hidden="true" />
          Monitoring started
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
          {result.created} page{result.created === 1 ? "" : "s"} now watched
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          {result.detail ??
            "Sitemyra will check each page and tell you what changed, why it might matter, and where the evidence is."}
        </p>

        <ul className="mt-5 divide-y divide-border overflow-hidden rounded-2xl border border-border">
          {result.monitors.map((monitor) => (
            <li key={monitor.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-foreground">{monitor.name}</span>
                <span className="block truncate text-xs text-muted-foreground">{monitor.url}</span>
              </span>
              <Link
                href={`/dashboard/monitors/${monitor.id}`}
                className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs"
              >
                Open
                <ArrowRight size={13} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>

        <div className="mt-5 flex flex-wrap gap-2">
          {first ? (
            <Link href={`/dashboard/monitors/${first.id}`} className="apeiro-btn apeiro-btn-primary">
              See the first monitor
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          ) : null}
          <button type="button" onClick={onWatchAnother} className="apeiro-btn apeiro-btn-outline">
            Watch another URL
          </button>
        </div>
      </section>

      {result.product_watches.length > 0 ? (
        <Note>
          Sitemyra is also tracking product data on{" "}
          <span className="font-semibold text-foreground">{result.product_watches[0].name}</span>.{" "}
          Price, availability, variants and reviews will appear on the monitor&apos;s Product tab.
        </Note>
      ) : null}

      <SkippedList skipped={result.skipped} />
    </div>
  );
}
