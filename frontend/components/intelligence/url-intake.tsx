"use client";

import { useState } from "react";
import { ArrowRight, Globe2, Loader2, Search } from "lucide-react";

/**
 * The primary intake control: one field, one verb.
 *
 * The SMB user should never have to think about intervals, selectors or
 * monitoring modes here — they paste a URL and Sitemyra does the rest.
 */
export function UrlIntake({
  onAnalyze,
  loading,
  initialUrl = "",
  cta = "Analyze this URL",
  hint = "Paste a competitor or product URL. Sitemyra works out what is worth watching.",
  size = "lg",
}: {
  onAnalyze: (url: string) => void;
  loading: boolean;
  initialUrl?: string;
  cta?: string;
  hint?: string;
  size?: "lg" | "md";
}) {
  const [url, setUrl] = useState(initialUrl);
  const looksValid = /^https?:\/\/.+/i.test(url.trim()) || /^[a-z0-9-]+(\.[a-z0-9-]+)+(\/.*)?$/i.test(url.trim());

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (loading || !looksValid) return;
    onAnalyze(url.trim());
  }

  const tall = size === "lg";

  return (
    <form onSubmit={submit} className="w-full">
      <label htmlFor="intake-url" className="sr-only">
        Competitor or product URL
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Globe2
            size={tall ? 18 : 16}
            aria-hidden="true"
            className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            id="intake-url"
            name="url"
            type="text"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://competitor.com/products/product-x"
            aria-invalid={url.length > 0 && !looksValid ? true : undefined}
            aria-describedby="intake-hint"
            className={`apeiro-input w-full !pl-10 ${tall ? "!h-14 !text-base" : ""}`}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !looksValid}
          className={`apeiro-btn apeiro-btn-primary shrink-0 ${tall ? "!min-h-14 !px-6" : ""}`}
        >
          {loading ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Search size={16} aria-hidden="true" />}
          {loading ? "Analyzing…" : cta}
        </button>
      </div>
      <p id="intake-hint" className="mt-2.5 text-xs leading-5 text-muted-foreground">
        {url.length > 0 && !looksValid ? "That does not look like a valid URL yet." : hint}
      </p>
    </form>
  );
}

export function AnalyzeAgainButton({ onReset }: { onReset: () => void }) {
  return (
    <button type="button" onClick={onReset} className="apeiro-btn apeiro-btn-ghost !min-h-0 !py-1.5 text-xs">
      Watch a different URL
      <ArrowRight size={13} aria-hidden="true" />
    </button>
  );
}
