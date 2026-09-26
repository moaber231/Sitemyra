"use client";

import { ArrowUpRight, ExternalLink, Loader2, ShieldQuestion } from "lucide-react";

import type { ChangeEvidence, Explanation, ProductChange, ProductSnapshot } from "@/lib/api/intelligence";

import { ConfidenceNote, Note, SectionLabel, SeverityBadge, formatMoney, relativeTime } from "./primitives";

/**
 * The alert deep link, in card form: what changed, why it may matter, what
 * to check, and the evidence behind all three.
 *
 * Every claim here is traceable to a stored observation. The "why" is
 * phrased as something a public page change *may* mean, never as advice.
 */
export function ChangeExplanation({
  explanation,
  productName,
  className = "",
}: {
  explanation: Explanation | null | undefined;
  productName: string;
  className?: string;
}) {
  if (!explanation || !explanation.evidence.length) {
    return (
      <Note>
        No field-level change has been recorded for this product yet. Sitemyra stores a snapshot on
        every check and only reports a change when a published value actually differs.
      </Note>
    );
  }

  return (
    <div className={`apeiro-card overflow-hidden ${className}`}>
      <div className="border-b border-border bg-muted/30 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionLabel>Latest change</SectionLabel>
          <ConfidenceNote confidence={explanation.confidence} />
        </div>
        <p className="mt-2 text-base font-semibold leading-6 tracking-tight text-foreground">
          {explanation.what_changed}
        </p>
      </div>

      <div className="divide-y divide-border">
        <ExplainRow label="Why it may matter" body={explanation.why_it_may_matter} />
        <ExplainRow label="What to check" body={explanation.what_to_check} />
      </div>

      <div className="border-t border-border px-5 py-4 sm:px-6">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <ShieldQuestion size={13} aria-hidden="true" />
          Evidence
        </p>
        <ul className="mt-2.5 space-y-2">
          {explanation.evidence.map((entry) => (
            <EvidenceRow key={`${entry.field}-${entry.detected_at ?? ""}`} entry={entry} />
          ))}
        </ul>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Classification rules used:{" "}
          <span className="font-mono">{explanation.basis.join(", ") || "—"}</span>. Every rule is a
          fixed threshold in Sitemyra&apos;s code, not a judgement about the competitor.
        </p>
      </div>
    </div>
  );
}

function ExplainRow({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div className="px-5 py-4 sm:px-6">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1.5 text-sm leading-6 text-foreground">{body}</p>
    </div>
  );
}

function EvidenceRow({ entry }: { entry: ChangeEvidence }) {
  return (
    <li className="rounded-xl border border-border bg-muted/20 px-3.5 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-foreground">{entry.label}</span>
        <SeverityBadge severity={entry.severity} />
      </div>
      <p className="mt-1.5 font-mono text-xs text-foreground">
        <span className="text-muted-foreground line-through">{entry.before || "—"}</span>
        <span className="mx-1.5 text-muted-foreground" aria-label="changed to">
          →
        </span>
        <span>{entry.after || "—"}</span>
      </p>
      {entry.basis ? <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{entry.basis}</p> : null}
      <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.7rem] text-muted-foreground">
        {entry.source_url ? (
          <a
            href={entry.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 underline decoration-border underline-offset-2 hover:text-accent"
          >
            Source
            <ArrowUpRight size={11} aria-hidden="true" />
          </a>
        ) : null}
        {entry.detected_at ? <span>Detected {relativeTime(entry.detected_at)}</span> : null}
        <span className="font-mono">{entry.rule}</span>
      </p>
    </li>
  );
}

/* ------------------------------------------------------------------ *
 * Current product state
 * ------------------------------------------------------------------ */

export function CurrentProduct({
  snapshot,
  currency,
  productDetected,
  detectionNote,
}: {
  snapshot: ProductSnapshot | null;
  currency: string;
  productDetected: boolean;
  detectionNote: string;
}) {
  if (!snapshot) {
    return (
      <Note>
        Waiting for this page&apos;s first check to complete. Once it does, Sitemyra stores the
        price, availability and variants it can see and starts comparing them.
      </Note>
    );
  }

  const code = snapshot.currency || currency;

  return (
    <div className="apeiro-card overflow-hidden">
      {!productDetected ? (
        <div className="border-b border-warning/25 bg-warning-muted/40 px-5 py-3 text-xs leading-5 text-foreground sm:px-6">
          <span className="font-semibold">Unconfirmed product data.</span> {detectionNote}
        </div>
      ) : null}

      <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-4">
        <Cell
          label="Price"
          value={formatMoney(snapshot.price, code)}
          hint={
            snapshot.list_price
              ? `List ${formatMoney(snapshot.list_price, code)} · ${snapshot.discount_percent ?? 0}% off`
              : undefined
          }
        />
        <Cell label="Availability" value={snapshot.availability_label || "not published"} />
        <Cell
          label="Rating"
          value={snapshot.rating ?? "not published"}
          hint={
            snapshot.review_count
              ? `${snapshot.review_count} review${snapshot.review_count === 1 ? "" : "s"}`
              : undefined
          }
        />
        <Cell
          label="Variants"
          value={snapshot.variants.length ? `${snapshot.variants.length} published` : "not published"}
        />
      </div>

      {snapshot.badges.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-4 sm:px-6">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Badges
          </span>
          {snapshot.badges.map((badge) => (
            <span key={badge} className="apeiro-badge bg-secondary text-secondary-foreground">
              {badge}
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4 text-xs text-muted-foreground sm:px-6">
        <span>
          Snapshot taken {relativeTime(snapshot.captured_at)} · read via{" "}
          <span className="font-mono">{Object.values(snapshot.extraction).join(", ") || "page text"}</span>
        </span>
        {snapshot.source_url ? (
          <a
            href={snapshot.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-accent underline decoration-accent/30 underline-offset-2"
          >
            View source
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        ) : null}
      </div>
    </div>
  );
}

function Cell({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="bg-card px-5 py-4 sm:px-6">
      <p className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-1.5 text-lg font-semibold capitalize tracking-tight text-foreground">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Timeline
 * ------------------------------------------------------------------ */

export function ChangeTimeline({ changes }: { changes: ProductChange[] }) {
  if (changes.length === 0) {
    return (
      <Note>
        No changes recorded yet. Sitemyra only writes a timeline entry when a published value
        actually differs, so an empty timeline means the page has not moved.
      </Note>
    );
  }

  return (
    <ol className="space-y-3">
      {changes.map((change) => (
        <li key={change.id} className="apeiro-card p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-foreground">{change.label}</span>
            <SeverityBadge severity={change.severity} />
          </div>
          <p className="mt-1.5 font-mono text-sm text-foreground">
            <span className="text-muted-foreground line-through">{change.before || "—"}</span>
            <span className="mx-2 text-muted-foreground" aria-label="changed to">
              →
            </span>
            <span>{change.after || "—"}</span>
          </p>
          {change.basis ? (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{change.basis}</p>
          ) : null}
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.7rem] text-muted-foreground">
            <span>{relativeTime(change.created_at)}</span>
            <span className="apeiro-badge bg-muted text-muted-foreground">{change.category_label}</span>
            {change.source_url ? (
              <a
                href={change.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 underline decoration-border underline-offset-2 hover:text-accent"
              >
                Source
                <ArrowUpRight size={11} aria-hidden="true" />
              </a>
            ) : null}
            <span className="font-mono">{change.rule}</span>
          </p>
        </li>
      ))}
    </ol>
  );
}

export function ProductTabSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading product intelligence">
      <div className="apeiro-card h-32 animate-pulse bg-muted/40" />
      <div className="apeiro-card h-48 animate-pulse bg-muted/40" />
    </div>
  );
}

export function ProductTabError({ message }: { message: string }) {
  return (
    <div className="apeiro-card flex items-center gap-3 p-6 text-sm text-danger" role="alert">
      <Loader2 size={16} aria-hidden="true" />
      {message}
    </div>
  );
}
