"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Loader2, Radio } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { ConfidenceNote, Note, SectionLabel, relativeTime } from "@/components/intelligence/primitives";
import { getSignals, reviewSignal, type MarketSignal } from "@/lib/api/intelligence";

/**
 * Market signals (Feature 10).
 *
 * A MARKET SIGNAL, never an opportunity. Each one states what was observed,
 * attaches the evidence, and offers an interpretation phrased as a
 * possibility. A signal is only emitted once at least two competitors moved
 * together, so one company doing one thing stays an event.
 */
export default function SignalsPage() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["intelligence-signals"],
    queryFn: () => getSignals(),
    retry: false,
  });

  const review = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "reviewed" | "dismissed" }) =>
      reviewSignal(id, status),
    onSuccess: () => {
      toast.success("Signal updated.");
      void queryClient.invalidateQueries({ queryKey: ["intelligence-signals"] });
    },
    onError: (caught) =>
      toast.error(caught instanceof Error ? caught.message : "Could not update the signal."),
  });

  const signals = data?.signals ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Market signals" />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Patterns across the competitors you watch. Sitemyra only raises a signal when at
            least {data?.minimum_competitors ?? 2} competitors moved together, and it always
            shows the evidence.
          </p>
        </div>

        <div className="apeiro-stagger stagger-2 mt-6">
          {isLoading ? (
            <div className="apeiro-card space-y-3 p-6" aria-busy="true">
              {[0, 1].map((index) => (
                <div key={index} className="apeiro-skeleton h-24 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="apeiro-card p-8 text-center" role="alert">
              <p className="text-sm text-danger">
                {(error as Error)?.message ?? "Sitemyra could not load market signals."}
              </p>
            </div>
          ) : signals.length === 0 ? (
            <Note>
              <span className="font-semibold text-foreground">No market signals yet.</span>{" "}
              A signal needs a pattern across at least two competitors, which usually takes
              a few weeks of monitoring. Individual changes always appear in the{" "}
              <Link href="/dashboard/feed" className="font-semibold text-accent underline underline-offset-2">
                feed
              </Link>
              .
            </Note>
          ) : (
            <ol className="space-y-3">
              {signals.map((signal) => (
                <li key={signal.id}>
                  <SignalCard
                    signal={signal}
                    expanded={expanded === signal.id}
                    onToggle={() =>
                      setExpanded((current) => (current === signal.id ? null : signal.id))
                    }
                    onReview={(status) => review.mutate({ id: signal.id, status })}
                    busy={review.isPending}
                  />
                </li>
              ))}
            </ol>
          )}
        </div>

        <p className="mt-8 text-xs leading-5 text-muted-foreground">
          A market signal is an observation about public pages. It is not a forecast, not a
          recommendation, and never a claim about a competitor&apos;s revenue, customers or
          strategy.
        </p>
      </div>
    </AppShell>
  );
}

function SignalCard({
  signal,
  expanded,
  onToggle,
  onReview,
  busy,
}: {
  signal: MarketSignal;
  expanded: boolean;
  onToggle: () => void;
  onReview: (status: "reviewed" | "dismissed") => void;
  busy: boolean;
}) {
  return (
    <article className="apeiro-card overflow-hidden">
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="flex items-center gap-2 text-sm font-semibold tracking-tight text-foreground">
            <Radio size={15} className="text-accent" aria-hidden="true" />
            <span className="min-w-0">{signal.headline}</span>
          </p>
          <span className="shrink-0 text-xs text-muted-foreground">
            {relativeTime(signal.created_at)}
          </span>
        </div>

        <p className="mt-2.5 text-sm leading-6 text-foreground">{signal.statement}</p>

        <div className="mt-3 rounded-xl border border-border bg-muted/30 p-3.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Potential interpretation
          </p>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{signal.interpretation}</p>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <ConfidenceNote confidence={signal.confidence} />
          <p className="text-xs text-muted-foreground">
            {signal.evidence_count} piece{signal.evidence_count === 1 ? "" : "s"} of evidence
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border bg-muted/20 px-5 py-3">
        <button type="button" onClick={onToggle} className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs">
          {expanded ? "Hide evidence" : "Show evidence"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onReview("reviewed")}
          className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs"
        >
          {busy ? <Loader2 size={12} className="animate-spin" aria-hidden="true" /> : null}
          Mark reviewed
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onReview("dismissed")}
          className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs"
        >
          Not relevant
        </button>
      </div>

      {expanded ? (
        <ul className="divide-y divide-border border-t border-border">
          {signal.evidence.map((entry) => (
            <li key={entry.signal_event_id} className="px-5 py-3.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link
                  href={`/dashboard/feed/${entry.signal_event_id}`}
                  className="min-w-0 truncate text-sm font-medium text-foreground hover:text-accent"
                >
                  {entry.headline}
                </Link>
                <span className="text-xs text-muted-foreground">
                  {entry.competitor} · {relativeTime(entry.detected_at)}
                </span>
              </div>
              {entry.before || entry.after ? (
                <p className="mt-1 font-mono text-xs text-foreground">
                  <span className="text-muted-foreground line-through">{entry.before || "—"}</span>
                  <span className="mx-2" aria-label="changed to">→</span>
                  <span>{entry.after || "—"}</span>
                </p>
              ) : null}
              {entry.source_url ? (
                <a
                  href={entry.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-[0.7rem] text-muted-foreground underline decoration-border underline-offset-2 hover:text-accent"
                >
                  Source
                  <ExternalLink size={10} aria-hidden="true" />
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <p className="border-t border-border px-5 py-3">
        <SectionLabel>Window</SectionLabel>{" "}
        <span className="text-xs text-muted-foreground">last {signal.window_days} days</span>
      </p>
    </article>
  );
}
