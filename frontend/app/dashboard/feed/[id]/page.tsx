"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, Loader2 } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { ChangeExplanation } from "@/components/intelligence/product-watch-panel";
import {
  SectionLabel,
  SeverityBadge,
  formatValue,
  relativeTime,
} from "@/components/intelligence/primitives";
import { getEventDetail, type EventDetail } from "@/lib/api/intelligence";

/**
 * The alert deep link — the screen an alert must land on.
 *
 * What changed · why it may matter · what to check · source · before/after ·
 * detected at · confidence · evidence. Nothing is asserted that the evidence
 * does not show.
 */
export default function EventDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const [eventId, setEventId] = useState<string | null>(null);

  useEffect(() => {
    void params.then(({ id }) => setEventId(id));
  }, [params]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["intelligence-event", eventId],
    queryFn: () => getEventDetail(eventId!),
    enabled: Boolean(eventId),
    retry: false,
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <Link
          href="/dashboard/feed"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition hover:text-accent"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Back to the feed
        </Link>

        {isLoading ? (
          <div className="apeiro-card mt-5 flex items-center gap-3 p-8 text-sm text-muted-foreground" aria-busy="true">
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
            Loading the evidence…
          </div>
        ) : isError || !data ? (
          <div className="apeiro-card mt-5 p-8" role="alert">
            <p className="text-sm text-danger">
              {(error as Error)?.message ?? "Sitemyra could not load this change."}
            </p>
          </div>
        ) : (
          <EventBody data={data} />
        )}
      </div>
    </AppShell>
  );
}

function EventBody({ data }: { data: EventDetail }) {
  return (
    <div className="mt-5 space-y-6">
      <header className="apeiro-card p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>
            {data.kind} · {data.competitor_name ?? "Monitored page"}
          </SectionLabel>
          <div className="flex items-center gap-2">
            <SeverityBadge severity={data.severity} />
            <span className="text-xs text-muted-foreground">
              Detected {relativeTime(data.detected_at)}
            </span>
          </div>
        </div>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
          {data.headline}
        </h1>
        <p className="mt-1.5 font-mono text-xs text-muted-foreground">{data.source_url}</p>
        {data.explanation.is_fallback ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Explanation written by Sitemyra&apos;s fixed rules. Nothing was inferred.
          </p>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            This explanation was written by an AI model from the same stored evidence, and
            every sentence had to cite it. The rule-based version is kept alongside it.
          </p>
        )}
      </header>

      <ChangeExplanation explanation={data.explanation} productName={data.competitor_name ?? ""} />

      {data.context.length > 0 ? (
        <section className="apeiro-card overflow-hidden">
          <div className="border-b border-border bg-muted/30 px-5 py-3">
            <SectionLabel>Also happened recently</SectionLabel>
          </div>
          <ul className="divide-y divide-border">
            {data.context.map((row) => (
              <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
                <Link
                  href={`/dashboard/feed/${row.id}`}
                  className="min-w-0 truncate text-sm text-foreground hover:text-accent"
                >
                  {row.headline}
                </Link>
                <span className="flex items-center gap-2">
                  <SeverityBadge severity={row.severity} />
                  <span className="text-xs text-muted-foreground">
                    {relativeTime(row.detected_at)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="apeiro-card p-5">
        <SectionLabel>Export this change</SectionLabel>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(data.export).map(([label, url]) => (
            <a
              key={label}
              href={`${process.env.NEXT_PUBLIC_API_URL ?? ""}${url}`}
              className="apeiro-btn apeiro-btn-outline !min-h-0 !py-2 text-xs"
            >
              <Download size={13} aria-hidden="true" />
              {label.toUpperCase()}
            </a>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Every exported row carries its source URL and detection time.
        </p>
        {data.timeline_url ? (
          <Link href={data.timeline_url} className="apeiro-btn apeiro-btn-ghost mt-2 !min-h-0 !py-1.5 text-xs">
            Open the full product timeline
          </Link>
        ) : null}
      </section>

      <details className="apeiro-card p-5">
        <summary className="cursor-pointer text-sm font-semibold text-foreground">
          Raw observation
        </summary>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-muted/40 p-4 font-mono text-xs text-muted-foreground">
          {JSON.stringify(
            {
              before: data.before,
              after: data.after,
              evidence: data.evidence,
            },
            null,
            2,
          ).slice(0, 4000)}
        </pre>
        <p className="mt-2 text-xs text-muted-foreground">
          Detected at {data.detected_at || "unknown"} ·{" "}
          {formatValue(data.explanation.basis.join(", "))}
        </p>
      </details>
    </div>
  );
}
