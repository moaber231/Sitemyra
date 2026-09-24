import Link from "next/link";
import { ArrowRight, Check, HelpCircle } from "lucide-react";

import { MarketingShell } from "@/components/marketing/marketing-shell";
import { PricingSection } from "@/components/marketing/pricing-section";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "Pricing",
  description:
    "Compare Sitemyra Free, Pro, and Business plans for competitor price, page, and content monitoring.",
  path: "/pricing",
});

const notes = [
  "Every new account starts on Free.",
  "No credit card is requested during account creation.",
  "Paid plan availability depends on the live billing configuration.",
];

export default function PricingPage() {
  return (
    <MarketingShell>
      <section className="relative overflow-hidden px-5 pb-12 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <div className="pointer-events-none absolute left-1/2 top-0 h-80 w-80 -translate-x-1/2 rounded-full bg-accent opacity-10 blur-3xl" />
        <div className="relative mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Pricing
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-6xl">
            A clear place to start.
          </h1>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Begin with a small watchlist. Move to faster checks and deeper
            comparison modes when your monitoring needs grow.
          </p>
        </div>
      </section>

      <section className="px-5 pb-20 sm:px-6 lg:px-8">
        <PricingSection showHeading={false} />
      </section>

      <section className="border-y border-border bg-card/50 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[0.85fr_1.15fr]">
          <div>
            <HelpCircle size={22} className="text-accent" aria-hidden="true" />
            <h2 className="mt-4 text-2xl font-semibold tracking-tight">
              A few pricing notes.
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Sitemyra is an early-stage product. The plan limits below reflect
              the current application configuration.
            </p>
          </div>
          <ul className="space-y-3">
            {notes.map((note) => (
              <li key={note} className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-sm leading-6 text-muted-foreground">
                <Check size={16} className="mt-1 shrink-0 text-success" aria-hidden="true" />
                {note}
              </li>
            ))}
            <li className="rounded-xl border border-border bg-card p-4 text-sm leading-6 text-muted-foreground">
              For cancellation, billing, and refund questions, read the{" "}
              <Link href="/terms#subscriptions" className="font-semibold text-foreground underline underline-offset-4 hover:text-accent">
                subscription terms
              </Link>
              . The operator should publish a verified refund policy before
              relying on one.
            </li>
          </ul>
        </div>
      </section>

      <section className="px-5 py-16 text-center sm:px-6 lg:px-8">
        <h2 className="text-3xl font-semibold tracking-tight">
          Ready to build your watchlist?
        </h2>
        <Link href="/register" className="apeiro-btn apeiro-btn-primary mt-6">
          Start monitoring free
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </MarketingShell>
  );
}
