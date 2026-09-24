import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Check,
  Code2,
  ExternalLink,
  FileSearch,
  Globe2,
  LayoutDashboard,
  Mail,
  MessageCircle,
  ScanSearch,
  ShieldCheck,
  Users,
  Webhook,
  Zap,
} from "lucide-react";

import { DemoMonitor } from "@/components/marketing/demo-monitor";
import { MarketingShell } from "@/components/marketing/marketing-shell";
import { PricingSection } from "@/components/marketing/pricing-section";
import { StructuredData } from "@/components/marketing/structured-data";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "Sitemyra — Know when your competitors change.",
  description:
    "Sitemyra monitors competitor pricing, pages, and content automatically and alerts you when something changes.",
  path: "/",
});

const workflow = [
  {
    number: "01",
    title: "Add a competitor page",
    text: "Choose a public pricing, product, or content page you want to keep an eye on.",
  },
  {
    number: "02",
    title: "Sitemyra checks it",
    text: "Scheduled checks compare the page using the monitoring mode you choose.",
  },
  {
    number: "03",
    title: "Get alerted",
    text: "Review the change in your dashboard and receive an email or webhook alert.",
  },
];

const capabilities = [
  {
    icon: FileSearch,
    title: "Content changes",
    text: "Use HTTP checks to notice meaningful content changes and record the response status for review.",
  },
  {
    icon: Code2,
    title: "DOM changes",
    text: "Compare selected page structure when you need a closer look at what changed.",
  },
  {
    icon: ScanSearch,
    title: "Visual changes",
    text: "Capture screenshots and review visual differences on supported plans.",
  },
  {
    icon: Zap,
    title: "Price changes",
    text: "Track a selected price value and get a clear before-and-after example.",
  },
];

const audiences = [
  {
    icon: Globe2,
    title: "SaaS companies",
    text: "Keep an eye on competitor pricing pages and product messaging.",
  },
  {
    icon: LayoutDashboard,
    title: "E-commerce businesses",
    text: "Watch product and pricing pages that matter to your customers.",
  },
  {
    icon: Users,
    title: "Digital and SEO agencies",
    text: "Monitor a focused watchlist for multiple clients or projects.",
  },
  {
    icon: FileSearch,
    title: "Marketing and research teams",
    text: "Catch landing-page, offer, and content changes without manual checks.",
  },
];

const channels = [
  { icon: Mail, label: "Email alerts" },
  { icon: BellRing, label: "Slack" },
  { icon: MessageCircle, label: "Discord" },
  { icon: Webhook, label: "Generic webhooks" },
  { icon: Code2, label: "Developer API keys" },
];

export default function HomePage() {
  return (
    <MarketingShell>
      <StructuredData />

      <section className="relative overflow-hidden px-5 pb-20 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-28 lg:pt-28">
        <div className="pointer-events-none absolute left-1/2 top-0 h-[34rem] w-[34rem] -translate-x-1/2 rounded-full bg-accent opacity-15 blur-[110px]" />
        <div className="relative mx-auto max-w-4xl text-center">
          <div className="animate-apeiro-fade-up inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3.5 py-1.5 text-xs font-semibold shadow-sm backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden="true" />
            Competitor and website monitoring
          </div>

          <h1 className="animate-apeiro-fade-up mt-7 text-5xl font-semibold tracking-[-0.05em] sm:text-6xl lg:text-7xl">
            Know when your competitors change.
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Monitor competitor pricing, pages, and content automatically. Get
            alerted when something changes.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="apeiro-btn apeiro-btn-primary w-full !py-3 sm:w-auto"
            >
              Start monitoring free
              <ArrowRight size={17} aria-hidden="true" />
            </Link>
            <Link
              href="/how-it-works"
              className="apeiro-btn apeiro-btn-outline w-full !py-3 sm:w-auto"
            >
              See how it works
            </Link>
          </div>

          <div className="mt-6 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Check size={13} className="text-success" aria-hidden="true" />
              Free plan available
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check size={13} className="text-success" aria-hidden="true" />
              No credit card to start
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check size={13} className="text-success" aria-hidden="true" />
              Publicly accessible pages
            </span>
          </div>
        </div>

        <div className="relative mx-auto mt-16 max-w-5xl">
          <DemoMonitor />
        </div>
      </section>

      <section
        id="how-it-works"
        className="scroll-mt-24 border-y border-border bg-card/50 px-5 py-20 sm:px-6 lg:px-8"
        aria-labelledby="workflow-heading"
      >
        <div className="mx-auto max-w-7xl">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              A simple workflow
            </p>
            <h2
              id="workflow-heading"
              className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl"
            >
              Set it once. See the signal when it matters.
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Sitemyra is designed for a focused job: notice meaningful changes
              on pages you choose.
            </p>
          </div>

          <ol className="mx-auto mt-10 grid max-w-5xl gap-4 md:grid-cols-3">
            {workflow.map((step) => (
              <li key={step.number} className="apeiro-card p-6">
                <span className="text-sm font-semibold tabular-nums text-accent">
                  {step.number}
                </span>
                <h3 className="mt-5 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {step.text}
                </p>
              </li>
            ))}
          </ol>

          <div className="mt-8 text-center">
            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-2 text-sm font-semibold text-foreground underline decoration-border underline-offset-4 transition hover:text-accent"
            >
              See the monitoring modes and examples
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <section
        id="features"
        className="scroll-mt-24 px-5 py-20 sm:px-6 lg:px-8"
        aria-labelledby="features-heading"
      >
        <div className="mx-auto max-w-7xl">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              What you can monitor
            </p>
            <h2
              id="features-heading"
              className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl"
            >
              Choose the level of detail that fits the question.
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              The available mode and check frequency depend on your plan. Start
              with a simple content check, then add depth when you need it.
            </p>
          </div>

          <div className="mx-auto mt-10 grid max-w-6xl gap-4 sm:grid-cols-2">
            {capabilities.map((capability) => (
              <div key={capability.title} className="apeiro-card p-6">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-accent">
                  <capability.icon size={19} aria-hidden="true" />
                </span>
                <h3 className="mt-5 font-semibold">{capability.title}</h3>
                <p className="mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
                  {capability.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-card px-5 py-16 sm:px-6 lg:px-8" aria-labelledby="alerts-heading">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Notifications
              </p>
              <h2 id="alerts-heading" className="mt-2 text-3xl font-semibold tracking-tight">
                Put the alert where you will see it.
              </h2>
            </div>
            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              Sitemyra supports owner email alerts plus the destinations you
              configure. There is no need to check every page by hand.
            </p>
          </div>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {channels.map((channel) => (
              <div key={channel.label} className="flex items-center gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-4">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-card text-accent">
                  <channel.icon size={17} aria-hidden="true" />
                </span>
                <span className="text-sm font-medium">{channel.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-6 lg:px-8" aria-labelledby="audiences-heading">
        <div className="mx-auto max-w-7xl">
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Who it is for
            </p>
            <h2 id="audiences-heading" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              A useful watchlist for teams that need to stay informed.
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Sitemyra is intended for small teams, agencies, and businesses
              that want a focused view of important pages.
            </p>
          </div>

          <div className="mx-auto mt-10 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {audiences.map((audience) => (
              <div key={audience.title} className="apeiro-card p-5">
                <audience.icon size={19} className="text-accent" aria-hidden="true" />
                <h3 className="mt-4 text-sm font-semibold">{audience.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {audience.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-card/50 px-5 py-20 sm:px-6 lg:px-8">
        <PricingSection />
      </section>

      <section className="px-5 py-20 sm:px-6 lg:px-8" aria-labelledby="founder-heading">
        <div className="mx-auto grid max-w-6xl gap-8 rounded-2xl border border-border bg-secondary/30 p-6 sm:p-8 lg:grid-cols-[1fr_auto] lg:items-center lg:p-10">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Built independently in Greece
            </p>
            <h2 id="founder-heading" className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
              Real product. Real founder. Early-stage and transparent.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Sitemyra started as an independent project by Konstantinos
              Gkogkos, a student developer in Greece. The goal is simple: make
              competitor monitoring accessible to smaller businesses without
              pretending to be a large company.
            </p>
            <div className="mt-5 flex flex-wrap gap-4 text-sm font-semibold">
              <Link href="/about" className="underline underline-offset-4 hover:text-accent">
                Read the founder story
              </Link>
              <a
                href="https://github.com/moaber231"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 underline underline-offset-4 hover:text-accent"
              >
                <ExternalLink size={15} aria-hidden="true" />
                View GitHub
              </a>
            </div>
          </div>
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl border border-border bg-card text-xl font-semibold text-accent shadow-lg">
            KG
            <span className="sr-only">Konstantinos Gkogkos</span>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 text-center sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl">
          <ShieldCheck size={28} className="mx-auto text-accent" aria-hidden="true" />
          <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
            Stop checking competitor pages manually.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Start with the Free plan and build a watchlist that gives you a
            clearer view of the market.
          </p>
          <Link href="/register" className="apeiro-btn apeiro-btn-primary mt-7">
            Create your free account
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}
