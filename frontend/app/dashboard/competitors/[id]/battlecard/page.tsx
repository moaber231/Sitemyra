"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2, RefreshCw, TriangleAlert } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { SectionLabel, formatMoney, relativeTime } from "@/components/intelligence/primitives";
import { getBattlecard, type Battlecard as BattlecardData } from "@/lib/api/intelligence";

/**
 * The living competitor battlecard (Feature 9).
 *
 * Assembled from what the pages actually publish, and labelled STALE when a
 * newer change exists than the figures below. A battlecard that looks
 * current but is not would be worse than no battlecard.
 */
export default function BattlecardPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [competitorId, setCompetitorId] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(false);

  useEffect(() => {
    void params.then(({ id }) => setCompetitorId(id));
  }, [params]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["intelligence-battlecard", competitorId, refresh],
    queryFn: () => getBattlecard(competitorId!, refresh),
    enabled: Boolean(competitorId),
    retry: false,
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Battlecard" />
        </div>

        {isLoading ? (
          <div className="apeiro-card mt-6 flex items-center gap-3 p-8 text-sm text-muted-foreground" aria-busy="true">
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
            Assembling the profile…
          </div>
        ) : isError || !data ? (
          <div className="apeiro-card mt-6 p-8" role="alert">
            <p className="text-sm text-danger">
              {(error as Error)?.message ?? "Sitemyra could not build a battlecard."}
            </p>
          </div>
        ) : (
          <BattlecardBody data={data} onRefresh={() => setRefresh((value) => !value)} refreshing={refresh} />
        )}
      </div>
    </AppShell>
  );
}

function BattlecardBody({
  data,
  onRefresh,
  refreshing,
}: {
  data: BattlecardData;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <div className="apeiro-stagger stagger-2 mt-6 space-y-4">
      {data.is_stale ? (
        <p className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning-muted px-3.5 py-3 text-sm text-foreground">
          <TriangleAlert size={15} className="mt-0.5 shrink-0 text-warning" aria-hidden="true" />
          {data.stale_note}
        </p>
      ) : null}

      <header className="apeiro-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold tracking-tight text-foreground">
              {data.competitor.name}
            </h2>
            <a
              href={data.competitor.website}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-accent"
            >
              {data.competitor.website}
              <ExternalLink size={12} aria-hidden="true" />
            </a>
            <p className="mt-2 text-xs capitalize text-muted-foreground">
              {data.competitor.relationship} · {data.state}
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="apeiro-btn apeiro-btn-outline !min-h-0 shrink-0 !py-2 text-xs"
          >
            {refreshing ? <Loader2 size={13} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={13} aria-hidden="true" />}
            Refresh
          </button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          {data.stale_note} Generated {relativeTime(data.generated_at)}.
        </p>
      </header>

      {data.pricing.length > 0 ? (
        <SectionCard title="Pricing" count={data.pricing.length}>
          <ul className="divide-y divide-border">
            {data.pricing.map((entry) => (
              <li key={`${entry.name}-${entry.captured_at}`} className="px-5 py-3.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-medium text-foreground">{entry.name}</span>
                  <span className="text-sm font-semibold text-foreground">
                    {formatMoney(entry.price, entry.currency)}
                    {entry.discount_percent ? (
                      <span className="ml-2 text-xs font-normal text-success">
                        {entry.discount_percent}% off {formatMoney(entry.list_price, entry.currency)}
                      </span>
                    ) : null}
                  </span>
                </div>
                <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
                  Read {relativeTime(entry.captured_at)} from{" "}
                  <a href={entry.source_url} target="_blank" rel="noopener noreferrer" className="underline decoration-border underline-offset-2 hover:text-accent">
                    the source page
                  </a>
                </p>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {data.products.length > 0 ? (
        <SectionCard title="Products" count={data.products.length}>
          <ul className="divide-y divide-border">
            {data.products.map((product) => (
              <li key={String(product.url)} className="px-5 py-3.5">
                <p className="text-sm font-medium text-foreground">{String(product.name)}</p>
                {product.state ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{String(product.state)}</p>
                ) : (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {String(product.availability)} · {String(product.variants)} variant
                    { Number(product.variants) === 1 ? "" : "s"} · rating {String(product.rating ?? "not published")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      {data.recent_changes.length > 0 ? (
        <SectionCard title="Recent changes" count={data.recent_changes.length}>
          <ul className="divide-y divide-border">
            {data.recent_changes.map((change) => (
              <li key={change.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
                <span className="min-w-0 truncate text-sm text-foreground">{change.headline}</span>
                <span className="text-xs capitalize text-muted-foreground">
                  {change.kind} · {relativeTime(change.detected_at)}
                </span>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      <section className="apeiro-card p-5">
        <SectionLabel>Positioning</SectionLabel>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{data.positioning}</p>
      </section>

      <section className="apeiro-card p-5">
        <SectionLabel>Sources</SectionLabel>
        <ul className="mt-2 space-y-1.5">
          {data.sources.map((source) => (
            <li key={source}>
              <a
                href={source}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 break-all font-mono text-xs text-muted-foreground underline decoration-border underline-offset-2 hover:text-accent"
              >
                {source}
                <ExternalLink size={10} aria-hidden="true" />
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">{data.note}</p>
      </section>
    </div>
  );
}

function SectionCard({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <section className="apeiro-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-5 py-3">
        <SectionLabel>{title}</SectionLabel>
        <span className="text-xs text-muted-foreground">{count}</span>
      </div>
      {children}
    </section>
  );
}
