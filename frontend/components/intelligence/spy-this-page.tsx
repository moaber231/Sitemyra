"use client";

import { useEffect, useState } from "react";
import { BookmarkPlus, Check, Copy, ShieldCheck } from "lucide-react";

/**
 * "Spy this page" — Feature 7, minus the extension.
 *
 * The bookmarklet holds no token and calls no API: it only opens Sitemyra
 * with the current page's URL pre-filled. Authentication happens in the
 * app, in the user's own session. See
 * `frontend/public/sitemyra-bookmarklet.js` for the reasoning.
 */
export function SpyThisPage() {
  const [copied, setCopied] = useState(false);
  const [origin, setOrigin] = useState("");

  useEffect(() => {
    setOrigin(window.location.origin);
  }, []);

  const href = origin
    ? `/dashboard/monitors/new?url=${encodeURIComponent(
        typeof window !== "undefined" ? window.location.href : "",
      )}`
    : "#";
  const javascript = origin
    ? `javascript:(()=>{window.open('${origin}/dashboard/monitors/new?url='+encodeURIComponent(location.href),'_blank','noopener')})()`
    : "";

  async function copy() {
    if (!javascript) return;
    try {
      await navigator.clipboard.writeText(javascript);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="apeiro-card p-5">
      <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <BookmarkPlus size={15} className="text-accent" aria-hidden="true" />
        Spy this page
      </p>
      <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
        Already on a competitor&apos;s product page? Add the{" "}
        <strong className="text-foreground">Monitor with Sitemyra</strong> bookmark and one click
        sends that page straight to the intake flow.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <a
          href={href}
          draggable
          onClick={(event) => event.preventDefault()}
          className="apeiro-btn apeiro-btn-primary !min-h-0 !cursor-grab !py-2 text-xs active:!cursor-grabbing"
          title="Drag me to your bookmarks bar"
        >
          🔖 Monitor with Sitemyra
        </a>
        <button type="button" onClick={copy} className="apeiro-btn apeiro-btn-outline !min-h-0 !py-2 text-xs">
          {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
          {copied ? "Copied" : "Copy the bookmarklet code"}
        </button>
      </div>

      <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-muted-foreground">
        <ShieldCheck size={13} className="mt-0.5 shrink-0 text-success" aria-hidden="true" />
        The bookmarklet contains no token and no API key. It only opens Sitemyra with the
        page&apos;s URL — sign-in happens in your own browser session.
      </p>
    </div>
  );
}
