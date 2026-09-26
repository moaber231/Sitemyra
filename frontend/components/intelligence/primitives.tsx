"use client";

import type { ReactNode } from "react";

import type { Confidence, Severity } from "@/lib/api/intelligence";

/* ------------------------------------------------------------------ *
 * Severity + confidence badges
 *
 * These are DESCRIPTIVE states, never scores. Nothing here claims a
 * competitor is "healthy", "risky" or "winning".
 * ------------------------------------------------------------------ */

const SEVERITY_STYLES: Record<Severity, { label: string; className: string; dot: string }> = {
  critical: {
    label: "Critical",
    className: "bg-danger-muted text-danger",
    dot: "bg-danger",
  },
  important: {
    label: "Important",
    className: "bg-warning-muted text-warning",
    dot: "bg-warning",
  },
  minor: {
    label: "Minor",
    className: "bg-secondary text-secondary-foreground",
    dot: "bg-muted-foreground",
  },
  informational: {
    label: "Informational",
    className: "bg-muted text-muted-foreground",
    dot: "bg-muted-foreground",
  },
};

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const config = SEVERITY_STYLES[severity as Severity] ?? SEVERITY_STYLES.informational;
  return (
    <span className={`apeiro-badge ${config.className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} aria-hidden="true" />
      {config.label}
    </span>
  );
}

const CONFIDENCE_COPY: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export function ConfidenceNote({ confidence }: { confidence: Confidence | string }) {
  const level = (confidence as Confidence) ?? "medium";
  const detail =
    level === "high"
      ? "Read from the page's own structured product data."
      : level === "medium"
        ? "Read from page metadata or tags, so confirm on the page before acting."
        : "Inferred from page text. Confirm on the page before acting.";

  return (
    <p className="text-xs leading-5 text-muted-foreground">
      <span className="font-semibold text-foreground">{CONFIDENCE_COPY[level] ?? CONFIDENCE_COPY.medium}.</span>{" "}
      {detail}
    </p>
  );
}

/* ------------------------------------------------------------------ *
 * Small shared pieces
 * ------------------------------------------------------------------ */

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-muted-foreground">
      {children}
    </p>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-border bg-muted/40 px-3.5 py-3 text-xs leading-5 text-muted-foreground">
      {children}
    </p>
  );
}

export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map((item) => formatValue(item)).join(", ") : "—";
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    return entries.length ? entries.map(([key, item]) => `${key}: ${formatValue(item)}`).join(" · ") : "—";
  }
  return String(value);
}

export function formatMoney(value: string | null | undefined, currency: string): string {
  if (!value) return "—";
  const code = currency ? `${currency} ` : "";
  return `${code}${value}`;
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "never";
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "unknown";
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(value).toLocaleDateString();
}

export const KIND_ICONS: Record<string, string> = {
  product: "▣",
  pricing: "¤",
  features: "✦",
  variants: "◫",
  reviews: "★",
  faq: "?",
  docs: "▤",
  changelog: "↻",
  blog: "✎",
  careers: "☗",
  promotions: "%",
  homepage: "⌂",
  legal: "§",
  support: "✆",
  other: "○",
};
