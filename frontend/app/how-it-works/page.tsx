import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Code2,
  FileSearch,
  Globe2,
  ScanSearch,
  Zap,
} from "lucide-react";

import { DemoMonitor } from "@/components/marketing/demo-monitor";
import { MarketingShell } from "@/components/marketing/marketing-shell";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "How Sitemyra works",
  description:
    "See how Sitemyra monitors public competitor pages, detects supported changes, and sends alerts.",
  path: "/how-it-works",
});

const steps = [
  {
    number: "01",
    icon: Globe2,
    title: "Choose a page to monitor",
    text: "Add a public pricing, product, landing, or content page. Sitemyra is designed for pages you are allowed to access.",
  },
  {
    number: "02",
    icon: FileSearch,
    title: "Sitemyra checks it automatically",
    text: "The monitor runs on a schedule determined by your plan. The lightweight HTTP engine checks content and records the response status.",
  },
  {
    number: "03",
    icon: Code2,
    title: "Sitemyra detects a change",
    text: "Depending on the mode you choose, Sitemyra can compare content, DOM structure, screenshots, or a selected price.",
  },
  {
    number: "04",
    icon: BellRing,
    title: "You receive an alert",
    text: "Review the result in the dashboard. Email and configured Slack, Discord, or generic webhook channels can be notified.",
  },
];

const examples = [
  {
    icon: Zap,
    label: "Price tracking",
    title: "€49/month → €59/month",
    text: "A price monitor can show the previous and current value when the selected price changes.",
  },
  {
    icon: FileSearch,
    label: "Content monitoring",
    title: "A page message changes",
    text: "HTTP checks can flag meaningful content changes and retain response status in a history of checks.",
  },
  {
    icon: ScanSearch,
    label: "Visual and DOM monitoring",
    title: "A layout or element changes",
    text: "Supported browser modes can compare a screenshot or selected DOM content for a closer look.",
  },
];

export default function HowItWorksPage() {
  return (
    <MarketingShell>
      <section className="relative overflow-hidden px-5 pb-16 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <div className="pointer-events-none absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 rounded-full bg-accent opacity-10 blur-3xl" />
        <div className="relative mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            How it works
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-6xl">
            From page to signal in four steps.
          </h1>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Sitemyra keeps the monitoring workflow visible: you choose the page,
            Sitemyra checks it, and you decide how you want to be alerted.
          </p>
        </div>
      </section>

      <section className="border-y border-border bg-card/50 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <ol className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {steps.map((step) => (
              <li key={step.number} className="apeiro-card p-6">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold tabular-nums text-accent">
                    {step.number}
                  </span>
                  <step.icon size={19} className="text-muted-foreground" aria-hidden="true" />
                </div>
                <h2 className="mt-6 text-lg font-semibold">{step.title}</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {step.text}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="examples" className="scroll-mt-24 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Supported examples
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">
              Choose the kind of change you care about.
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              The examples below are illustrative. They are not reports about a
              real customer or a real company.
            </p>
          </div>
          <div className="mt-9 grid gap-4 md:grid-cols-3">
            {examples.map((example) => (
              <article key={example.title} className="apeiro-card p-6">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-accent">
                  <example.icon size={19} aria-hidden="true" />
                </span>
                <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {example.label}
                </p>
                <h3 className="mt-2 text-xl font-semibold">{example.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {example.text}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-card/50 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <DemoMonitor />
        </div>
      </section>

      <section className="px-5 py-16 text-center sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight">
            Start with one page. Expand when it is useful.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            The Free plan is a simple way to see whether scheduled monitoring
            fits your workflow.
          </p>
          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/register" className="apeiro-btn apeiro-btn-primary">
              Start monitoring free
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <Link href="/pricing" className="apeiro-btn apeiro-btn-outline">
              Compare plans
            </Link>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
