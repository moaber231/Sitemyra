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

      <section className="marketing-noise relative overflow-hidden border-b-4 px-5 pb-24 pt-16 sm:px-6 sm:pt-24 lg:px-8 lg:pb-32 lg:pt-32">
        <div className="mx-auto max-w-6xl">
          <div className="marketing-hero-mark" aria-hidden="true" />
          <div className="mt-10 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="marketing-label text-xs font-medium uppercase">
                Competitor and website monitoring
              </p>
              <p className="mt-3 font-mono text-xs uppercase tracking-[0.12em] text-muted-foreground">
                A focused watchlist for the pages that matter
              </p>
            </div>
            <p className="max-w-xs text-sm leading-6 text-muted-foreground sm:text-right">
              Real product. Real founder. Early-stage and transparent.
            </p>
          </div>

          <h1 className="marketing-display mt-10 max-w-6xl text-[clamp(3.5rem,10vw,10rem)]">
            Know when
            <br />
            <span className="italic">your competitors</span>
            <br />
            change.
          </h1>

          <div className="mt-10 grid gap-8 border-t-2 border-border pt-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <p className="marketing-body-large max-w-2xl">
              Monitor competitor pricing, pages, and content automatically. Get
              alerted when something changes.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
              <Link href="/register" className="apeiro-btn apeiro-btn-primary w-full sm:w-auto">
                Start monitoring free
                <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </Link>
              <Link href="/how-it-works" className="apeiro-btn apeiro-btn-outline w-full sm:w-auto">
                See how it works
              </Link>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 border-t border-border pt-5 font-mono text-[0.68rem] uppercase tracking-[0.12em] text-muted-foreground">
            <span className="inline-flex items-center gap-2">
              <Check size={14} strokeWidth={1.5} aria-hidden="true" />
              Free plan available
            </span>
            <span className="inline-flex items-center gap-2">
              <Check size={14} strokeWidth={1.5} aria-hidden="true" />
              No credit card to start
            </span>
            <span className="inline-flex items-center gap-2">
              <Check size={14} strokeWidth={1.5} aria-hidden="true" />
              Publicly accessible pages
            </span>
          </div>

          <div className="mt-20">
            <DemoMonitor />
          </div>
        </div>
      </section>

      <section
        id="how-it-works"
        className="marketing-diagonal scroll-mt-24 border-b-4 px-5 py-24 sm:px-6 md:py-32 lg:px-8"
        aria-labelledby="workflow-heading"
      >
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
            <div>
              <p className="marketing-label text-xs font-medium uppercase">A simple workflow</p>
              <h2 id="workflow-heading" className="mt-4 max-w-xl text-4xl sm:text-6xl">
                Set it once. See the signal when it matters.
              </h2>
            </div>
            <p className="max-w-lg text-base leading-7 text-muted-foreground lg:justify-self-end">
              Sitemyra is designed for a focused job: notice meaningful changes
              on pages you choose, without turning your workday into a browser
              tab.
            </p>
          </div>

          <ol className="mt-16 grid gap-0 border-y-2 border-border md:grid-cols-3">
            {workflow.map((step, index) => (
              <li
                key={step.number}
                className={`group border-border p-6 transition-colors duration-100 hover:bg-black hover:text-white sm:p-8 ${
                  index < workflow.length - 1 ? "border-b-2 md:border-b-0 md:border-r-2" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm">{step.number}</span>
                  <span className="h-3 w-3 border border-current" aria-hidden="true" />
                </div>
                <h3 className="mt-16 text-2xl">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground transition-colors duration-100 group-hover:text-white">
                  {step.text}
                </p>
              </li>
            ))}
          </ol>

          <div className="mt-8 text-right">
            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.12em] underline decoration-1 underline-offset-4 transition-colors duration-100 hover:bg-black hover:text-white"
            >
              See monitoring modes and examples
              <ArrowRight size={15} strokeWidth={1.5} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>

      <section
        id="features"
        className="marketing-grid scroll-mt-24 border-b-4 px-5 py-24 sm:px-6 md:py-32 lg:px-8"
        aria-labelledby="features-heading"
      >
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <p className="marketing-label text-xs font-medium uppercase">What you can monitor</p>
            <h2 id="features-heading" className="mt-4 text-4xl sm:text-6xl">
              Choose the level of detail that fits the question.
            </h2>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground">
              Start with a simple content check. Add visual, DOM, or price
              detail when the question calls for it.
            </p>
          </div>

          <div className="mt-16 grid border-t-2 border-border sm:grid-cols-2">
            {capabilities.map((capability, index) => (
              <article
                key={capability.title}
                className={`group border-b-2 border-border p-6 transition-colors duration-100 hover:bg-black hover:text-white sm:p-8 ${
                  index % 2 === 0 ? "sm:border-r-2" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <capability.icon size={23} strokeWidth={1.5} aria-hidden="true" />
                  <span className="font-mono text-[0.65rem] text-muted-foreground transition-colors duration-100 group-hover:text-white">
                    0{index + 1}
                  </span>
                </div>
                <h3 className="mt-16 text-2xl">{capability.title}</h3>
                <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground transition-colors duration-100 group-hover:text-white">
                  {capability.text}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-inverted border-b-4 px-5 py-24 sm:px-6 md:py-32 lg:px-8" aria-labelledby="alerts-heading">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-col gap-8 border-b border-white pb-10 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="marketing-label text-xs font-medium uppercase text-white">Notifications</p>
              <h2 id="alerts-heading" className="mt-4 max-w-2xl text-4xl text-white sm:text-6xl">
                Put the alert where you will see it.
              </h2>
            </div>
            <p className="max-w-md text-base leading-7 text-white/70 sm:text-right">
              Sitemyra supports owner email alerts plus the destinations you
              configure. Review the result first, then route the signal.
            </p>
          </div>

          <div className="mt-12 grid border-t border-white sm:grid-cols-2 lg:grid-cols-5">
            {channels.map((channel, index) => (
              <div
                key={channel.label}
                className={`flex items-center gap-3 border-b border-white p-5 transition-colors duration-100 hover:bg-white hover:text-black ${
                  index < channels.length - 1 ? "lg:border-r" : ""
                }`}
              >
                <channel.icon size={20} strokeWidth={1.5} aria-hidden="true" />
                <span className="font-mono text-[0.68rem] uppercase tracking-[0.1em]">
                  {channel.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b-4 px-5 py-24 sm:px-6 md:py-32 lg:px-8" aria-labelledby="audiences-heading">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <p className="marketing-label text-xs font-medium uppercase">Who it is for</p>
            <h2 id="audiences-heading" className="mt-4 text-4xl sm:text-6xl">
              A useful watchlist for teams that need to stay informed.
            </h2>
            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground">
              Sitemyra is intended for small teams, agencies, and businesses
              that want a focused view of important pages.
            </p>
          </div>

          <div className="mt-16 grid border-t-2 border-border sm:grid-cols-2 lg:grid-cols-4">
            {audiences.map((audience, index) => (
              <article
                key={audience.title}
                className={`group border-b-2 border-border p-6 transition-colors duration-100 hover:bg-black hover:text-white ${
                  index < audiences.length - 1 ? "lg:border-r-2" : ""
                }`}
              >
                <audience.icon size={22} strokeWidth={1.5} aria-hidden="true" />
                <h3 className="mt-12 text-xl">{audience.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground transition-colors duration-100 group-hover:text-white">
                  {audience.text}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-rule-light border-b-4 px-5 py-24 sm:px-6 md:py-32 lg:px-8">
        <PricingSection />
      </section>

      <section className="marketing-inverted border-b-4 px-5 py-24 sm:px-6 md:py-32 lg:px-8" aria-labelledby="founder-heading">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-12 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <p className="marketing-label text-xs font-medium uppercase text-white">Built independently in Greece</p>
              <h2 id="founder-heading" className="mt-4 max-w-4xl text-4xl text-white sm:text-6xl">
                Real product. Real founder. Early-stage and transparent.
              </h2>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-white/75">
                Sitemyra started as an independent project by Konstantinos
                Gkogkos, a student developer in Greece. The goal is simple: make
                competitor monitoring accessible to smaller businesses without
                pretending to be a large company.
              </p>
              <div className="mt-8 flex flex-wrap gap-6 font-mono text-xs uppercase tracking-[0.12em]">
                <Link href="/about" className="underline underline-offset-4 hover:bg-white hover:text-black">
                  Read the founder story
                </Link>
                <a
                  href="https://github.com/moaber231"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 underline underline-offset-4 hover:bg-white hover:text-black"
                >
                  <ExternalLink size={15} strokeWidth={1.5} aria-hidden="true" />
                  View GitHub
                </a>
              </div>
            </div>
            <div className="border-2 border-white p-6">
              <div className="flex h-16 w-16 items-center justify-center border border-white font-mono text-xl">
                KG
                <span className="sr-only">Konstantinos Gkogkos</span>
              </div>
              <p className="mt-6 font-mono text-xs uppercase tracking-[0.12em] text-white/60">
                Founder / independent developer
              </p>
            </div>
          </div>

          <div className="mt-20 grid border-t border-white sm:grid-cols-3">
            {operatingFacts.map(([number, title, text]) => (
              <div key={number} className="border-b border-white p-5 sm:border-b-0 sm:border-r sm:p-6 last:border-r-0">
                <span className="font-mono text-xs text-white/60">{number}</span>
                <h3 className="mt-8 text-xl text-white">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/65">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="marketing-noise px-5 py-24 text-center sm:px-6 md:py-32 lg:px-8">
        <div className="mx-auto max-w-3xl">
          <div className="marketing-hero-mark mx-auto" aria-hidden="true" />
          <ShieldCheck size={28} strokeWidth={1.5} className="mx-auto mt-10" aria-hidden="true" />
          <h2 className="mt-6 text-4xl sm:text-6xl">
            Stop checking competitor pages manually.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground">
            Start with the Free plan and build a watchlist that gives you a
            clearer view of the market.
          </p>
          <Link href="/register" className="apeiro-btn apeiro-btn-primary mt-8">
            Create your free account
            <ArrowUpRight size={16} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}
