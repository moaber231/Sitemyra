"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, Check, Loader2, Sparkles, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { Note, SectionLabel } from "@/components/intelligence/primitives";
import {
  approveCandidate,
  discoverCompetitors,
  type CompetitorCandidate,
} from "@/lib/api/intelligence";

/**
 * Competitor discovery (Feature 2).
 *
 * The user submits their OWN site. Sitemyra reads the comparison page that
 * site publishes and proposes the competitors listed there — or says plainly
 * that it found none. Nothing is monitored until approved.
 */
export default function DiscoveryPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [candidates, setCandidates] = useState<CompetitorCandidate[]>([]);
  const [detail, setDetail] = useState("");
  const [own, setOwn] = useState<{ name: string; domain: string } | null>(null);
  const [approving, setApproving] = useState<string | null>(null);

  async function discover(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    setCandidates([]);
    setDetail("");
    try {
      const result = await discoverCompetitors(url.trim());
      setOwn(result.competitor);
      setCandidates(result.candidates);
      setDetail(result.detail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sitemyra could not read that site.");
    } finally {
      setLoading(false);
    }
  }

  async function approve(candidate: CompetitorCandidate) {
    setApproving(candidate.id);
    try {
      const result = await approveCandidate({ candidate_id: candidate.id, recipe: "everything" });
      if (result.limit_reached) {
        toast.error(result.detail ?? "Plan limit reached.");
      } else {
        toast.success(`Now monitoring ${result.competitor.name}.`);
      }
      setCandidates((current) => current.filter((item) => item.id !== candidate.id));
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Could not approve this competitor.");
    } finally {
      setApproving(null);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Find competitors" />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Give Sitemyra your own website. If you publish a page naming your alternatives or
            who you compare against, it reads that page and proposes who to watch — with
            the reason for each suggestion.
          </p>
        </div>

        <form onSubmit={discover} className="apeiro-stagger stagger-2 apeiro-card mt-6 p-6">
          <label htmlFor="own-site" className="mb-2 block text-sm font-medium text-foreground">
            Your website or product URL
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="own-site"
              type="text"
              inputMode="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://yoursite.com"
              className="apeiro-input flex-1"
            />
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="apeiro-btn apeiro-btn-primary shrink-0"
            >
              {loading ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Sparkles size={15} aria-hidden="true" />}
              {loading ? "Reading…" : "Suggest competitors"}
            </button>
          </div>
          {error ? (
            <p role="alert" className="mt-3 rounded-xl border border-danger/30 bg-danger-muted px-3.5 py-3 text-sm text-danger">
              {error}
            </p>
          ) : null}
        </form>

        {own && candidates.length === 0 && !loading ? (
          <div className="apeiro-stagger stagger-3 mt-6">
            <Note>
              <span className="font-semibold text-foreground">No public competitor signals found on {own.domain}.</span>{" "}
              Sitemyra only proposes companies that your own site links to from a page
              describing alternatives, integrations or partners. It does not guess. You can
              still add any page as a monitor from the{" "}
              <Link href="/dashboard/monitors/new" className="font-semibold text-accent underline underline-offset-2">
                intake flow
              </Link>
              .
            </Note>
          </div>
        ) : null}

        {candidates.length > 0 ? (
          <div className="apeiro-stagger stagger-3 mt-6 space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <SectionLabel>
                {candidates.length} proposal{candidates.length === 1 ? "" : "s"}
              </SectionLabel>
              <p className="text-xs text-muted-foreground">{detail}</p>
            </div>
            {candidates.map((candidate) => (
              <article key={candidate.id} className="apeiro-card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">
                      {candidate.domain}
                    </p>
                    <p className="mt-0.5 text-xs capitalize text-muted-foreground">
                      {candidate.relationship} · confidence {candidate.confidence}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => approve(candidate)}
                    disabled={approving === candidate.id}
                    className="apeiro-btn apeiro-btn-primary !min-h-0 shrink-0 !py-2 text-xs"
                  >
                    {approving === candidate.id ? (
                      <Loader2 size={13} className="animate-spin" aria-hidden="true" />
                    ) : (
                      <Check size={13} aria-hidden="true" />
                    )}
                    Approve &amp; monitor
                  </button>
                </div>
                <ul className="mt-3 space-y-1.5">
                  {candidate.reason_list.map((reason) => (
                    <li key={reason} className="flex items-start gap-2 text-xs leading-5 text-muted-foreground">
                      <Building2 size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
                      {reason}
                    </li>
                  ))}
                </ul>
                <p className="mt-3 truncate font-mono text-[0.7rem] text-muted-foreground">
                  {candidate.url}
                </p>
              </article>
            ))}
            <Note>
              <UserPlus size={12} className="mr-1 inline" aria-hidden="true" />
              Nothing is monitored until you approve it. Sitemyra proposes; you decide.
            </Note>
          </div>
        ) : null}

        <p className="mt-8 text-xs leading-5 text-muted-foreground">
          Sitemyra reads public pages only. It does not access private systems, and a
          competitor can see the request in their own server logs, exactly as they would
          see a visitor.
        </p>
      </div>
    </AppShell>
  );
}
