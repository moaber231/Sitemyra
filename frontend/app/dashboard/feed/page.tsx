"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ExternalLink, Loader2, Rss } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { SeverityBadge, SectionLabel, relativeTime } from "@/components/intelligence/primitives";
import { getFeed, type FeedEvent } from "@/lib/api/intelligence";

/**
 * The market feed — the reason to come back.
 *
 * Chronological, filterable, and every row clickable through to the exact
 * evidence. No scores: a row says what changed and where it was read.
 */
export default function FeedPage() {
  const [kind, setKind] = useState("all");
  const [items, setItems] = useState<FeedEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const query = useQuery({
    queryKey: ["intelligence-feed", kind],
    queryFn: () => getFeed({ kind, limit: 25 }),
    retry: false,
  });

  // The first page is server-driven; "load more" appends with the cursor.
  const rows = items.length > 0 ? items : (query.data?.results ?? []);
  const counts = query.data?.counts_by_kind ?? {};
  const kinds = query.data?.available_kinds ?? [
    { value: "all", label: "All" },
    { value: "pricing", label: "Pricing" },
    { value: "products", label: "Products" },
    { value: "features", label: "Features" },
    { value: "marketing", label: "Marketing" },
    { value: "content", label: "Content" },
    { value: "hiring", label: "Hiring" },
    { value: "other", label: "Other" },
  ];

  const loadMore = useCallback(async () => {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const next = await getFeed({ kind, cursor, limit: 25 });
      setItems((current) => {
        const base = current.length > 0 ? current : (query.data?.results ?? []);
        const seen = new Set(base.map((row) => row.id));
        return [...base, ...next.results.filter((row) => !seen.has(row.id))];
      });
      setCursor(next.next_cursor);
      setHasMore(next.has_more);
    } finally {
      setLoadingMore(false);
    }
  }, [cursor, kind, loadingMore, query.data]);

  function changeFilter(next: string) {
    setKind(next);
    setItems([]);
    setCursor(null);
    setHasMore(false);
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Market feed" />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Everything your monitored competitors have published, newest first. Every row
            links to the page it was read from.
          </p>
        </div>

        <div
          role="group"
          aria-label="Filter the feed by category"
          className="apeiro-stagger stagger-2 mt-5 flex flex-wrap gap-2"
        >
          {kinds.map((entry) => {
            const active = kind === entry.value;
            const count = entry.value === "all" ? undefined : counts[entry.value];
            return (
              <button
                key={entry.value}
                type="button"
                onClick={() => changeFilter(entry.value)}
                aria-pressed={active}
                className={`apeiro-btn !min-h-0 !py-1.5 text-xs ${
                  active ? "apeiro-btn-primary" : "apeiro-btn-ghost"
                }`}
              >
                {entry.label}
                {count !== undefined ? (
                  <span className="ml-1.5 tabular-nums text-muted-foreground">{count}</span>
                ) : null}
              </button>
            );
          })}
        </div>

        <div className="apeiro-stagger stagger-3 mt-6">
          {query.isLoading ? (
            <div className="apeiro-card space-y-3 p-6" aria-busy="true">
              {[0, 1, 2].map((index) => (
                <div key={index} className="apeiro-skeleton h-16 w-full" />
              ))}
            </div>
          ) : query.isError ? (
            <div className="apeiro-card p-8 text-center" role="alert">
              <p className="text-sm text-danger">
                {(query.error as Error)?.message ?? "Sitemyra could not load your feed."}
              </p>
              <button type="button" onClick={() => query.refetch()} className="apeiro-btn apeiro-btn-outline mt-4">
                Try again
              </button>
            </div>
          ) : rows.length === 0 ? (
            <EmptyFeed kind={kind} />
          ) : (
            <>
              <ol className="space-y-3">
                {rows.map((row) => (
                  <li key={row.id}>
                    <FeedRow row={row} />
                  </li>
                ))}
              </ol>
              {hasMore || cursor ? (
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="apeiro-btn apeiro-btn-outline mt-4 w-full"
                >
                  {loadingMore ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Rss size={15} aria-hidden="true" />}
                  {loadingMore ? "Loading…" : "Load older changes"}
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function FeedRow({ row }: { row: FeedEvent }) {
  return (
    <article className="apeiro-card apeiro-interactive p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="flex min-w-0 items-center gap-2 text-sm font-semibold tracking-tight text-foreground">
          <span aria-hidden="true">{row.icon}</span>
          <span className="truncate">{row.headline}</span>
        </p>
        <div className="flex shrink-0 items-center gap-2">
          <SeverityBadge severity={row.severity} />
          <span className="whitespace-nowrap text-xs text-muted-foreground">
            {relativeTime(row.detected_at)}
          </span>
        </div>
      </div>

      {(row.before || row.after) ? (
        <p className="mt-2 font-mono text-sm text-foreground">
          {row.before ? (
            <>
              <span className="text-muted-foreground line-through">{row.before}</span>
              <span className="mx-2 text-muted-foreground" aria-label="changed to">→</span>
            </>
          ) : null}
          <span>{row.after || "—"}</span>
        </p>
      ) : null}

      {row.summary ? (
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{row.summary}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
        <Link
          href={`/dashboard/feed/${row.id}`}
          className="font-semibold text-accent underline decoration-accent/30 underline-offset-4 hover:text-accent-secondary"
        >
          See what changed and why
        </Link>
        {row.competitor_name ? (
          <span className="text-muted-foreground">Competitor: {row.competitor_name}</span>
        ) : null}
        {row.source_url ? (
          <a
            href={row.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-muted-foreground underline decoration-border underline-offset-2 hover:text-accent"
          >
            Source
            <ExternalLink size={11} aria-hidden="true" />
          </a>
        ) : null}
        {row.monitor_id ? (
          <Link href={`/dashboard/monitors/${row.monitor_id}`} className="inline-flex items-center gap-1 text-muted-foreground hover:text-accent">
            Monitor
            <ArrowUpRight size={11} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </article>
  );
}

function EmptyFeed({ kind }: { kind: string }) {
  return (
    <div className="apeiro-card p-10 text-center">
      <SectionLabel>{kind === "all" ? "Nothing yet" : "Nothing in this category"}</SectionLabel>
      <h2 className="mt-2 text-lg font-semibold tracking-tight text-foreground">
        No changes recorded yet
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        Sitemyra only writes a feed entry when a published value actually differs, so an
        empty feed means your monitored pages have not moved. That is the expected state
        right after you start watching.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Link href="/dashboard/monitors/new" className="apeiro-btn apeiro-btn-primary">
          Watch a competitor
        </Link>
        <Link href="/dashboard/pulse" className="apeiro-btn apeiro-btn-outline">
          See your competitors
        </Link>
      </div>
    </div>
  );
}
