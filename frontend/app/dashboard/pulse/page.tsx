"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Building2, Loader2, Search } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { Note, SectionLabel, relativeTime } from "@/components/intelligence/primitives";
import { getPulse, type PulseState } from "@/lib/api/intelligence";

const WINDOWS = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
];

/**
 * Competitor pulse.
 *
 * Descriptive states only. A competitor is "changed recently" or "no
 * significant change detected" — never scored, rated or ranked by a
 * number, because nothing in public page data supports one.
 */
export default function PulsePage() {
  const [windowDays, setWindowDays] = useState(30);
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["intelligence-pulse", windowDays],
    queryFn: () => getPulse(windowDays),
    retry: false,
  });

  const competitors = data?.competitors ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader
            title="Competitor pulse"
            children={
              <button
                type="button"
                onClick={() => refetch()}
                className="apeiro-btn apeiro-btn-outline !min-h-[2.25rem] !py-2 text-[0.8125rem]"
              >
                {isLoading ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Search size={15} aria-hidden="true" />}
                Refresh
              </button>
            }
          />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            What each tracked competitor has published, described in words rather than scored.
          </p>
        </div>

        <div role="group" aria-label="Pulse window" className="apeiro-stagger stagger-2 mt-5 flex flex-wrap gap-2">
          {WINDOWS.map((entry) => (
            <button
              key={entry.value}
              type="button"
              onClick={() => setWindowDays(entry.value)}
              aria-pressed={windowDays === entry.value}
              className={`apeiro-btn !min-h-0 !py-1.5 text-xs ${
                windowDays === entry.value ? "apeiro-btn-primary" : "apeiro-btn-ghost"
              }`}
            >
              Last {entry.label}
            </button>
          ))}
          <Link href="/dashboard/discover" className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs">
            <Building2 size={13} aria-hidden="true" />
            Add a competitor
          </Link>
        </div>

        <div className="apeiro-stagger stagger-3 mt-6">
          {isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2" aria-busy="true">
              {[0, 1, 2, 3].map((index) => (
                <div key={index} className="apeiro-card h-40 animate-pulse bg-muted/40" />
              ))}
            </div>
          ) : isError ? (
            <div className="apeiro-card p-8 text-center" role="alert">
              <p className="text-sm text-danger">
                {(error as Error)?.message ?? "Sitemyra could not load your competitors."}
              </p>
            </div>
          ) : competitors.length === 0 ? (
            <Note>
              <span className="font-semibold text-foreground">No competitors tracked yet.</span>{" "}
              Paste a competitor URL to get started — Sitemyra groups the pages you monitor
              by company, so the pulse fills in automatically.
            </Note>
          ) : (
            <>
              <p className="mb-3 text-xs text-muted-foreground">
                {data?.totals.competitors} competitor
                {data?.totals.competitors === 1 ? "" : "s"} ·{" "}
                {data?.totals.with_activity} changed in this window
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {competitors.map((competitor) => (
                  <CompetitorCard key={competitor.competitor_id} competitor={competitor} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}

const STATE_TONE: Record<string, string> = {
  no_significant_change_detected: "bg-muted text-muted-foreground",
  changed_recently: "bg-warning-muted text-warning",
  multiple_changes_detected: "bg-warning-muted text-warning",
  pricing_changed: "bg-accent/10 text-accent",
  product_change_detected: "bg-accent/10 text-accent",
  feature_change_detected: "bg-accent/10 text-accent",
  hiring_change_detected: "bg-secondary text-secondary-foreground",
  marketing_change_detected: "bg-secondary text-secondary-foreground",
};

function CompetitorCard({ competitor }: { competitor: PulseState }) {
  return (
    <article className="apeiro-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold tracking-tight text-foreground">
            {competitor.name}
          </h2>
          <a
            href={competitor.homepage_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 inline-flex items-center gap-1 truncate text-xs text-muted-foreground hover:text-accent"
          >
            {competitor.domain}
            <ArrowUpRight size={11} aria-hidden="true" />
          </a>
        </div>
        <span className="apeiro-badge bg-secondary text-secondary-foreground capitalize">
          {competitor.relationship}
        </span>
      </div>

      <p className="mt-3 text-sm font-medium text-foreground">{competitor.state_label}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {competitor.states.map((state) => (
          <span key={state} className={`apeiro-badge ${STATE_TONE[state] ?? "bg-muted text-muted-foreground"}`}>
            {state.replace(/_/g, " ")}
          </span>
        ))}
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
        <div>
          <dt className="text-muted-foreground">Changes</dt>
          <dd className="tabular-nums text-base font-semibold text-foreground">
            {competitor.events_in_window}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Pages</dt>
          <dd className="tabular-nums text-base font-semibold text-foreground">
            {competitor.monitor_count}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Product data</dt>
          <dd className="text-sm font-semibold text-foreground">
            {competitor.tracks_product ? "Tracked" : "—"}
          </dd>
        </div>
      </dl>

      {Object.keys(competitor.events_by_kind).length > 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          {Object.entries(competitor.events_by_kind)
            .sort((left, right) => right[1] - left[1])
            .map(([kind, total]) => `${kind} (${total})`)
            .join(" · ")}
        </p>
      ) : null}

      {competitor.relationship_reasons.length > 0 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-semibold text-accent">
            Why Sitemyra thinks this is a {competitor.relationship}
          </summary>
          <ul className="mt-2 space-y-1">
            {competitor.relationship_reasons.map((reason) => (
              <li key={reason} className="text-xs leading-5 text-muted-foreground">
                {reason}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <p className="mt-3 text-[0.7rem] text-muted-foreground">
        <SectionLabel>Last activity</SectionLabel> {relativeTime(competitor.last_activity_at)}
      </p>
    </article>
  );
}
