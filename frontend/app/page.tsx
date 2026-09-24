import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
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
    text: "Review the result in your dashboard and receive an email or webhook alert.",
  },
];

const capabilities = [
  {
    icon: FileSearch,
    title: "Content changes",
    text: "Use HTTP checks to notice meaningful content changes and record response status for review.",
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

const operatingFacts = [
  ["01", "Public pages", "Monitoring is designed for pages you are authorized to access."],
  ["02", "Scheduled checks", "Frequency and depth follow the plan you choose."],
  ["03", "Clear alerts", "Review the result first, then route the signal where you work."],
];

export default function HomePage() {
  return (
    <MarketingShell>
      <StructuredData />

      <section className="marketing-noise relative overflow-hidden px-5 pb-24 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-32 lg:pt-28">
        <div className="marketing-orb" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-[1.1fr_0.9fr] lg:gap-10">
          <div>
            <div className="section-label">
              <span aria-hidden="true" />
              Competitor and website monitoring
            </div>

            <h1 className="marketing-display relative mt-7 max-w-3xl text-[clamp(3.25rem,7vw,5.25rem)]">
              Know when your competitors <span className="gradient-text">change.</span>
              <span className="gradient-underline" aria-hidden="true" />
            </h1>

            <p className="marketing-body-large mt-7 max-w-xl text-muted-foreground">
              Monitor competitor pricing, pages, and content automatically. Get
              alerted when something changes.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href="/register" className="apeiro-btn apeiro-btn-primary group w-full sm:w-auto">
                Start monitoring free
                <ArrowRight size={16} strokeWidth={1.8} className="transition-transform duration-200 group-hover:translate-x-1" aria-hidden="true" />
              </Link>
              <Link href="/how-it-works" className="apeiro-btn apeiro-btn-outline w-full sm:w-auto">
                See how it works
              </Link>
            </div>

            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 border-t border-border pt-5 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <Check size={14} className="text-accent" aria-hidden="true" />
                Free plan available
              </span>
              <span className="inline-flex items-center gap-2">
                <Check size={14} className="text-accent" aria-hidden="true" />
                No credit card to start
              </span>
              <span className="inline-flex items-center gap-2">
                <Check size={14} className="text-accent" aria-hidden="true" />
                Publicly accessible pages
              </span>
            </div>
          </div>

          <HeroVisual />
        </div>

        <div className="relative mx-auto mt-20 max-w-6xl">
          <DemoMonitor />
        </div>
      </section>

      <section
        id="how-it-works"
        className="marketing-diagonal scroll-mt-24 border-y border-border px-5 py-24 sm:px-6 md:py-32 lg:px-8"
        aria-labelledby="workflow-heading"
      >
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
            <div>
              <div className="section-label">
                <span aria-hidden="true" />
                A simple workflow
              </div>
              <h2 id="workflow-heading" className="mt-5 max-w-xl text-4xl sm:text-6xl">
                Set it once. See the signal when it matters.
              </h2>
            </div>
            <p className="max-w-lg text-base leading-7 text-muted-foreground lg:justify-self-end">
              Sitemyra is designed for a focused job: notice meaningful changes
              on pages you choose, without turning your workday into a browser
              tab.
            </p>
          </div>

          <ol className="mt-16 grid gap-5 md:grid-cols-3">
            {workflow.map((step) => (
              <li
                key={step.number}
                className="group rounded-2xl border border-border bg-card p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-accent/30 hover:shadow-lg sm:p-8"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm text-accent">{step.number}</span>
                  <span className="h-3 w-3 rounded-full border border-accent/30 bg-accent/10" aria-hidden="true" />
                </div>
                <h3 className="mt-16 text-2xl text-foreground">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{step.text}</p>
              </li>
            ))}
          </ol>

          <div className="mt-8 text-right">
            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-2 text-sm font-semibold text-accent underline decoration-accent/30 underline-offset-4 transition hover:text-accent-secondary"
            >
              See monitoring modes and examples
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <section
        id="features"
        className="marketing-grid scroll-mt-24 border-b border-border px-5 py-24 sm:px-6 md:py-32 lg:px-8"
        aria-labelledby="features-heading"
      >
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <div className="section-label">
              <span aria-hidden="true" />
              What you can monitor
            </div>
            <h2 id="features-heading" className="mt-5 text-4xl sm:text-6xl">
              Choose the level of detail that fits the question.
            </h2>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground">
              Start with a simple content check. Add visual, DOM, or price
              detail when the question calls for it.
            </p>
          </div>

          <div className="mt-16 grid gap-5 sm:grid-cols-2">
            {capabilities.map((capability, index) => (
              <article
                key={capability.title}
                className="group rounded-2xl border border-border bg-card p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-accent/30 hover:shadow-lg sm:p-8"
              >
                <div className="flex items-start justify-between gap-4">
                  <span className="modern-icon h-11 w-11 rounded-xl transition duration-300 group-hover:scale-105">
                    <capability.icon size={20} strokeWidth={1.7} aria-hidden="true" />
                  </span>
                  <span className="font-mono text-[0.65rem] text-muted-foreground">0{index + 1}</span>
                </div>
                <h3 className="mt-14 text-2xl text-foreground">{capability.title}</h3>
                <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">{capability.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-inverted px-5 py-24 sm:px-6 md:py-32 lg:px-8" aria-labelledby="alerts-heading">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-8 border-b border-white/15 pb-10 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="section-label section-label--dark">
                <span aria-hidden="true" />
                Notifications
              </div>
              <h2 id="alerts-heading" className="mt-5 max-w-2xl text-4xl text-white sm:text-6xl">
                Put the alert where you will see it.
              </h2>
            </div>
            <p className="max-w-md text-base leading-7 text-slate-300 sm:text-right">
              Sitemyra supports owner email alerts plus the destinations you
              configure. Review the result first, then route the signal.
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {channels.map((channel) => (
              <div
                key={channel.label}
                className="flex items-center gap-3 rounded-xl border border-white/15 bg-white/5 p-4 text-white transition duration-300 hover:-translate-y-1 hover:border-blue-300/50 hover:bg-white/10"
              >
                <channel.icon size={20} strokeWidth={1.7} className="text-blue-300" aria-hidden="true" />
                <span className="font-mono text-[0.68rem] uppercase tracking-[0.08em]">
                  {channel.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-border px-5 py-24 sm:px-6 md:py-32 lg:px-8" aria-labelledby="audiences-heading">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <div className="section-label">
              <span aria-hidden="true" />
              Who it is for
            </div>
            <h2 id="audiences-heading" className="mt-5 text-4xl sm:text-6xl">
              A useful watchlist for teams that need to stay informed.
            </h2>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground">
              Sitemyra is intended for small teams, agencies, and businesses
              that want a focused view of important pages.
            </p>
          </div>

          <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {audiences.map((audience) => (
              <article
                key={audience.title}
                className="group rounded-2xl border border-border bg-card p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-accent/30 hover:shadow-lg"
              >
                <span className="modern-icon h-10 w-10 rounded-xl transition duration-300 group-hover:scale-105">
                  <audience.icon size={19} strokeWidth={1.7} aria-hidden="true" />
                </span>
                <h3 className="mt-12 text-xl text-foreground">{audience.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{audience.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-border px-5 py-24 sm:px-6 md:py-32 lg:px-8">
        <PricingSection />
      </section>

      <section className="marketing-inverted px-5 py-24 sm:px-6 md:py-32 lg:px-8" aria-labelledby="founder-heading">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-12 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <div className="section-label section-label--dark">
                <span aria-hidden="true" />
                Built independently in Greece
              </div>
              <h2 id="founder-heading" className="mt-5 max-w-4xl text-4xl text-white sm:text-6xl">
                Real product. Real founder. Early-stage and transparent.
              </h2>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
                Sitemyra started as an independent project by Konstantinos
                Gkogkos, a student developer in Greece. The goal is simple: make
                competitor monitoring accessible to smaller businesses without
                pretending to be a large company.
              </p>
              <div className="mt-8 flex flex-wrap gap-6 font-mono text-xs uppercase tracking-[0.1em]">
                <Link href="/about" className="text-blue-200 underline underline-offset-4 hover:text-white">
                  Read the founder story
                </Link>
                <a
                  href="https://github.com/moaber231"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-blue-200 underline underline-offset-4 hover:text-white"
                >
                  <ExternalLink size={15} aria-hidden="true" />
                  View GitHub
                </a>
              </div>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/5 p-6 backdrop-blur">
              <div className="modern-icon h-16 w-16 rounded-2xl font-mono text-xl">KG</div>
              <p className="mt-6 font-mono text-xs uppercase tracking-[0.12em] text-slate-400">
                Founder / independent developer
              </p>
            </div>
          </div>

          <div className="mt-20 grid gap-4 sm:grid-cols-3">
            {operatingFacts.map(([number, title, text]) => (
              <div key={number} className="rounded-2xl border border-white/15 bg-white/5 p-5 backdrop-blur sm:p-6">
                <span className="font-mono text-xs text-blue-300">{number}</span>
                <h3 className="mt-8 text-xl text-white">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-noise px-5 py-24 text-center sm:px-6 md:py-32 lg:px-8">
        <div className="mx-auto max-w-3xl">
          <div className="section-label mx-auto">
            <span aria-hidden="true" />
            Start watching smarter
          </div>
          <ShieldCheck size={30} strokeWidth={1.6} className="mx-auto mt-8 text-accent" aria-hidden="true" />
          <h2 className="mt-6 text-4xl sm:text-6xl">
            Stop checking competitor pages manually.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground">
            Start with the Free plan and build a watchlist that gives you a
            clearer view of the market.
          </p>
          <Link href="/register" className="apeiro-btn apeiro-btn-primary mt-8">
            Create your free account
            <ArrowUpRight size={16} strokeWidth={1.8} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}

function HeroVisual() {
  return (
    <div className="relative mx-auto hidden aspect-square w-full max-w-[30rem] lg:block" role="img" aria-label="Sitemyra monitoring workflow illustration">
      <div className="marketing-grid absolute inset-0 rounded-[2.5rem] border border-border/80 bg-card shadow-xl" />
      <div className="modern-orbit absolute inset-[12%] rounded-full border-dashed border-accent/30" />
      <div className="absolute left-[18%] top-[17%] h-3 w-3 rounded-full bg-accent shadow-[0_0_0_8px_rgb(0_82_255_/_0.12)]" />
      <div className="absolute bottom-[19%] right-[16%] h-2.5 w-2.5 rounded-full bg-accent-secondary shadow-[0_0_0_7px_rgb(77_124_255_/_0.12)]" />

      <div className="modern-float-card absolute left-[12%] top-[18%] w-44 rounded-2xl border border-border bg-card/95 p-4 backdrop-blur sm:w-48">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">Monitor</span>
          <span className="modern-pulse-dot h-2 w-2 rounded-full bg-success" />
        </div>
        <p className="mt-5 text-2xl font-semibold tracking-tight text-foreground">Pricing page</p>
        <p className="mt-1 font-mono text-[0.68rem] text-muted-foreground">scheduled check</p>
      </div>

      <div className="modern-float-card-delayed absolute bottom-[14%] right-[8%] w-48 rounded-2xl border border-accent/20 bg-card/95 p-4 shadow-xl backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="modern-icon h-8 w-8 rounded-lg"><BellRing size={15} aria-hidden="true" /></span>
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-accent">Alert routed</span>
        </div>
        <p className="mt-4 text-sm leading-6 text-foreground">A meaningful change is ready to review.</p>
      </div>

      <div className="absolute left-[42%] top-[43%] rounded-2xl border border-border bg-background/90 p-4 shadow-lg backdrop-blur">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent" />
          <span className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-foreground">Sitemyra</span>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">Signal → clarity</p>
      </div>
    </div>
  );
}
