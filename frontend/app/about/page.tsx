import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Code2,
  ExternalLink,
  ShieldCheck,
} from "lucide-react";

import { MarketingShell } from "@/components/marketing/marketing-shell";
import { StructuredData } from "@/components/marketing/structured-data";
import { FOUNDER_LINKS } from "@/lib/site";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "About Sitemyra",
  description:
    "Learn how Sitemyra is being built as an independent SaaS project in Greece.",
  path: "/about",
});

const principles = [
  {
    title: "Useful before impressive",
    text: "A focused alert is more valuable than a dashboard full of noise.",
  },
  {
    title: "Clear about limits",
    text: "The product explains what it checks, what it stores, and where it can fail.",
  },
  {
    title: "Small and sustainable",
    text: "Sitemyra is being grown deliberately by its founder, without pretending to be a large company.",
  },
];

export default function AboutPage() {
  return (
    <MarketingShell>
      <StructuredData />

      <section className="relative overflow-hidden px-5 pb-16 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <div className="pointer-events-none absolute right-0 top-0 h-80 w-80 rounded-full bg-accent opacity-10 blur-3xl" />
        <div className="relative mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            About Sitemyra
          </p>
          <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">
            Built independently in Greece.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground">
            Sitemyra is an independent SaaS project built in Greece by
            Konstantinos Gkogkos. It is a focused tool for noticing changes on
            the public web pages that matter to a business.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/register" className="apeiro-btn apeiro-btn-primary">
              Start monitoring free
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link href="/how-it-works" className="apeiro-btn apeiro-btn-outline">
              See the product
            </Link>
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-card/50 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              The founder
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">
              A student developer building in public.
            </h2>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              Sitemyra started as an independent project by Konstantinos
              Gkogkos, a student developer in Greece. The goal is simple: build
              useful software that helps smaller businesses keep track of their
              competitive landscape without expensive enterprise tools.
            </p>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              Konstantinos is building and growing the product, and users can
              contact him directly through the links below. There is no
              fabricated team, customer list, or company story here.
            </p>
          </div>

          <div className="apeiro-card p-6 sm:p-8">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-border bg-secondary text-xl font-semibold text-accent">
                KG
              </div>
              <div>
                <p className="text-lg font-semibold">Konstantinos Gkogkos</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Founder · Independent developer
                </p>
              </div>
            </div>
            <div className="mt-6 grid gap-3 border-t border-border pt-5">
              <a
                href={FOUNDER_LINKS[0].href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm transition hover:border-accent/50 hover:bg-secondary"
              >
                <span className="inline-flex items-center gap-2">
                  <Code2 size={16} aria-hidden="true" />
                  GitHub
                </span>
                <ArrowUpRight size={15} className="text-muted-foreground" aria-hidden="true" />
              </a>
              <a
                href={FOUNDER_LINKS[1].href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm transition hover:border-accent/50 hover:bg-secondary"
              >
                <span className="inline-flex items-center gap-2">
                  <ExternalLink size={16} aria-hidden="true" />
                  LinkedIn
                </span>
                <ArrowUpRight size={15} className="text-muted-foreground" aria-hidden="true" />
              </a>
              <a
                href={FOUNDER_LINKS[2].href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm transition hover:border-accent/50 hover:bg-secondary"
              >
                <span>Portfolio</span>
                <ArrowUpRight size={15} className="text-muted-foreground" aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              How the project is guided
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">
              Early-stage does not have to mean vague.
            </h2>
          </div>
          <div className="mt-9 grid gap-4 md:grid-cols-3">
            {principles.map((principle) => (
              <div key={principle.title} className="apeiro-card p-6">
                <ShieldCheck size={19} className="text-accent" aria-hidden="true" />
                <h3 className="mt-4 font-semibold">{principle.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {principle.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-card/50 px-5 py-16 text-center sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight">
            Want to try the product or ask a question?
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Start with the free plan, or visit the contact page and use the
            founder links if email is not published yet.
          </p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/register" className="apeiro-btn apeiro-btn-primary">
              Create a free account
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link href="/contact" className="apeiro-btn apeiro-btn-outline">
              Contact Sitemyra
            </Link>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
