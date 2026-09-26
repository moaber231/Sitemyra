"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, Search } from "lucide-react";

import type { DiscoveredTarget } from "@/lib/api/intelligence";

import { KIND_ICONS } from "./primitives";

const KIND_ORDER = [
  "product",
  "pricing",
  "promotions",
  "features",
  "variants",
  "reviews",
  "changelog",
  "docs",
  "homepage",
  "faq",
  "careers",
  "blog",
  "support",
  "other",
] as const;

const SKIP_REASON: Record<string, string> = {
  plan_limit: "Your plan’s URL limit was reached.",
  already_monitored: "You already monitor this page.",
  invalid_url: "Sitemyra could not normalize this URL.",
  workspace_forbidden: "You need an admin role in that workspace.",
};

/**
 * The discovered-target checklist.
 *
 * Every row shows *why* Sitemyra proposes it, so the user can judge the
 * suggestion instead of trusting a black box.
 */
export function TargetChecklist({
  targets,
  selected,
  onToggle,
  onToggleAll,
  disabled,
}: {
  targets: DiscoveredTarget[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (selectAll: boolean) => void;
  disabled?: boolean;
}) {
  const [filter, setFilter] = useState("");

  const grouped = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const matching = needle
      ? targets.filter(
          (target) =>
            target.label.toLowerCase().includes(needle) ||
            target.url.toLowerCase().includes(needle) ||
            target.kind_label.toLowerCase().includes(needle),
        )
      : targets;

    const buckets = new Map<string, DiscoveredTarget[]>();
    for (const target of matching) {
      const list = buckets.get(target.kind) ?? [];
      list.push(target);
      buckets.set(target.kind, list);
    }
    return [...buckets.entries()].sort((left, right) => {
      const leftIndex = KIND_ORDER.indexOf(left[0] as (typeof KIND_ORDER)[number]);
      const rightIndex = KIND_ORDER.indexOf(right[0] as (typeof KIND_ORDER)[number]);
      return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex);
    });
  }, [filter, targets]);

  const allSelected = targets.length > 0 && targets.every((target) => selected.has(target.id));

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold tracking-tight text-foreground">
            {selected.size} of {targets.length} selected
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            The page you pasted is always kept first.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              size={14}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <label htmlFor="target-filter" className="sr-only">
              Filter discovered pages
            </label>
            <input
              id="target-filter"
              type="search"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Filter"
              className="apeiro-input !h-9 !w-36 !pl-8 text-sm"
            />
          </div>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onToggleAll(!allSelected)}
            className="apeiro-btn apeiro-btn-ghost !min-h-9 !py-1.5 text-xs"
          >
            {allSelected ? "Clear all" : "Select all"}
          </button>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        {grouped.map(([kind, items]) => (
          <div key={kind}>
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted-foreground">
              {items[0]?.kind_label ?? kind}
            </p>
            <ul className="mt-2 divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card">
              {items.map((target) => {
                const checked = selected.has(target.id);
                return (
                  <li key={target.id} className="px-4 py-3">
                    <label className="flex cursor-pointer items-start gap-3">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => onToggle(target.id)}
                        className="mt-1 h-4 w-4 shrink-0 rounded border-input accent-[#0052ff]"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <span
                            aria-hidden="true"
                            className="text-xs text-muted-foreground"
                          >
                            {KIND_ICONS[target.kind] ?? KIND_ICONS.other}
                          </span>
                          <span className="truncate text-sm font-medium text-foreground">
                            {target.label}
                          </span>
                          {target.is_primary ? (
                            <span className="apeiro-badge bg-accent/10 text-accent">Pasted URL</span>
                          ) : null}
                        </span>
                        <span className="mt-1 block truncate text-xs text-muted-foreground">
                          {target.why}
                        </span>
                        <a
                          href={target.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 inline-flex max-w-full items-center gap-1 truncate text-[0.7rem] text-muted-foreground underline decoration-border underline-offset-2 hover:text-accent"
                        >
                          {target.url}
                          <ArrowUpRight size={11} aria-hidden="true" className="shrink-0" />
                        </a>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        {grouped.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            Nothing matches “{filter}”.
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function SkippedList({
  skipped,
}: {
  skipped: { url: string; label: string; reason: string }[];
}) {
  if (skipped.length === 0) return null;
  return (
    <div className="rounded-2xl border border-warning/25 bg-warning-muted/50 p-4">
      <p className="text-sm font-semibold text-foreground">
        {skipped.length} page{skipped.length === 1 ? "" : "s"} not monitored
      </p>
      <ul className="mt-2 space-y-1.5">
        {skipped.slice(0, 8).map((row) => (
          <li key={row.url} className="flex flex-wrap items-baseline gap-x-2 text-xs text-muted-foreground">
            <span className="truncate font-medium text-foreground">{row.label}</span>
            <span>{SKIP_REASON[row.reason] ?? row.reason}</span>
          </li>
        ))}
        {skipped.length > 8 ? (
          <li className="text-xs text-muted-foreground">+{skipped.length - 8} more</li>
        ) : null}
      </ul>
    </div>
  );
}
