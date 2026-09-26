"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";

import { analyzeUrlPublic, type PublicAnalysis } from "@/lib/api/intelligence";

import { UrlIntake } from "@/components/intelligence/url-intake";
import { KIND_ICONS, SectionLabel, formatMoney } from "@/components/intelligence/primitives";

/**
 * The product-led loop from the homepage.
 *
 * A visitor pastes any public URL and sees what Sitemyra understood,
 * before being asked to create an account. The analysis runs through the
 * same extraction the product uses — it is not a canned screenshot — and
 * nothing about the visitor is stored.
 *
 * The static example exists so the page is never empty: it is explicitly
 * labelled as illustrative, and it never names a real company.
 */
export function UrlDemo() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PublicAnalysis | null>(null);
  const [showExample, setShowExample] = useState(false);

  async function run(rawUrl: string) {
    setLoading(true);
    setError("");
    setShowExample(false);
    try {
      const analysis = await analyzeUrlPublic(rawUrl);
      setResult(analysis);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Sitemyra could not read that page. It may block automated requests.",
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const display = result ?? (showExample ? EXAMPLE : null);

  return (
    <section
      className="modern-gradient-border overflow-hidden rounded-2xl"
      aria-label="Try Sitemyra on a competitor or product URL"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 bg-card/80 px-4 py-3 backdrop-blur sm:px-5">
        <div className="flex items-center gap-3">
          <span className="modern-pulse-dot h-2.5 w-2.5 rounded-full bg-accent" aria-hidden="true" />
          <span className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-foreground">
            Try it now
          </span>
        </div>
        <span className="flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">
          <ShieldCheck size={12} aria-hidden="true" />
          No account needed
        </span>
      </div>

      <div className="p-5 sm:p-8">
        <UrlIntake
          onAnalyze={run}
          loading={loading}
          cta="Analyze"
          size="md"
          hint="We read the public page and show you what Sitemyra would watch. Nothing is stored and no account is created."
        />

        {error ? (
          <p role="alert" className="mt-4 rounded-xl border border-danger/30 bg-danger-muted px-3.5 py-3 text-sm text-danger">
            {error}
          </p>
        ) : null}

        {!display && !error ? (
          <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <button
              type="button"
              onClick={() => setShowExample(true)}
              className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs"
            >
              <Sparkles size={13} aria-hidden="true" />
              See an example result instead
            </button>
            <p className="text-xs text-muted-foreground">
              Or paste any public product page above.
            </p>
          </div>
        ) : null}

        {display ? (
          <div className="mt-6 border-t border-border pt-5">
            {result ? <RealResult result={result} /> : <ExampleResult />}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function RealResult({ result }: { result: PublicAnalysis }) {
  const facts = result.facts ?? {};
  const currency = typeof facts.currency === "string" ? facts.currency : "";
  const price = typeof facts.price === "string" ? facts.price : null;
  const listPrice = typeof facts.list_price === "string" ? facts.list_price : null;
  const availability = typeof facts.availability === "string" ? facts.availability : "";
  const discount =
    price && listPrice && Number(listPrice) > Number(price)
      ? Math.round(((Number(listPrice) - Number(price)) / Number(listPrice)) * 100)
      : null;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <SectionLabel>
            {result.page_kind_label} · confidence {result.classification_confidence}
          </SectionLabel>
          <p className="mt-1.5 text-lg font-semibold tracking-tight text-foreground">
            {result.product_detected
              ? `This is a product page — ${String(facts.name ?? "unnamed product")}`
              : `We found ${result.found_count} thing${result.found_count === 1 ? "" : "s"} worth monitoring.`}
          </p>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {result.classification_rationale}
          </p>
        </div>
      </div>

      {result.product_detected ? (
        <dl className="mt-5 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-4">
          <Cell label="Price" value={formatMoney(price, currency)} hint={discount ? `${discount}% off` : undefined} />
          <Cell label="Availability" value={availability ? availability.replace(/_/g, " ") : "not published"} />
          <Cell label="Rating" value={String(facts.rating ?? "not published")} hint={facts.review_count ? `${facts.review_count} reviews` : undefined} />
          <Cell label="Would watch" value={`${result.found_count} pages`} />
        </dl>
      ) : null}

      {result.targets.length > 0 ? (
        <ul className="mt-5 space-y-1.5">
          {result.targets.map((target) => (
            <li key={target.url} className="flex items-center gap-2 text-sm text-foreground">
              <span aria-hidden="true" className="text-xs text-muted-foreground">
                {KIND_ICONS[target.kind] ?? KIND_ICONS.other}
              </span>
              <span className="truncate">{target.label}</span>
            </li>
          ))}
          {result.found_count > result.targets.length ? (
            <li className="text-xs text-muted-foreground">
              +{result.found_count - result.targets.length} more pages on this site
            </li>
          ) : null}
        </ul>
      ) : null}

      <p className="mt-5 text-sm leading-6 text-foreground">
        Want Sitemyra to watch this for you?
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href={`/register?url=${encodeURIComponent(result.url)}`} className="apeiro-btn apeiro-btn-primary">
          Start monitoring free
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
        <Link href="/how-it-works" className="apeiro-btn apeiro-btn-outline">
          See how it works
        </Link>
      </div>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        Read from the page&apos;s own published data. Sitemyra does not access private systems.
      </p>
    </div>
  );
}

function ExampleResult() {
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <SectionLabel>Illustrative example</SectionLabel>
          <p className="mt-1.5 text-lg font-semibold tracking-tight text-foreground">
            This is what a product page analysis looks like
          </p>
        </div>
        <span className="rounded-full border border-border px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">
          Example data
        </span>
      </div>

      <dl className="mt-5 grid gap-px overflow-hidden rounded-2xl border border-border bg-border sm:grid-cols-4">
        <Cell label="Product" value="Acme Pro Widget" />
        <Cell label="Price" value="EUR 99.00" hint="was 129.00 · 23% off" />
        <Cell label="Availability" value="low stock" />
        <Cell label="Rating" value="4.6" hint="128 reviews" />
      </dl>

      <ul className="mt-5 space-y-1.5">
        {[
          "Product — Acme Pro Widget",
          "Pricing — competitor.com/pricing",
          "Changelog — competitor.com/changelog",
          "Careers — competitor.com/careers",
        ].map((label) => (
          <li key={label} className="flex items-center gap-2 text-sm text-foreground">
            <span aria-hidden="true" className="text-xs text-muted-foreground">
              ▣
            </span>
            <span>{label}</span>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-xs leading-5 text-muted-foreground">
        Fictional example. Paste a real public URL above to see Sitemyra read that page for
        yourself.
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        <Link href="/register" className="apeiro-btn apeiro-btn-primary">
          Start monitoring free
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}

function Cell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-card px-4 py-3.5">
      <dt className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-base font-semibold capitalize tracking-tight text-foreground">{value}</dd>
      {hint ? <dd className="mt-0.5 text-xs text-muted-foreground">{hint}</dd> : null}
    </div>
  );
}

const EXAMPLE: PublicAnalysis = {
  url: "https://example.com/products/pro-widget",
  page_kind: "product",
  page_kind_label: "Product",
  classification_confidence: "high",
  classification_rationale:
    'The URL path contains "/products", and the page publishes schema.org Product structured data.',
  product_detected: true,
  facts: {},
  found_count: 4,
  targets: [],
  sign_in_url: "/register",
};
