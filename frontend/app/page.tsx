import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Check,
  DollarSign,
  Hash,
  KeyRound,
  Mail,
  MessageCircle,
  ScanSearch,
  ShieldCheck,
  Webhook,
} from "lucide-react";

const CHANNELS = [
  { icon: <Hash size={16} />, label: "Slack Webhooks" },
  { icon: <MessageCircle size={16} />, label: "Discord Webhooks" },
  { icon: <Webhook size={16} />, label: "Generic Webhooks" },
  { icon: <Mail size={16} />, label: "Email Alerts" },
  { icon: <KeyRound size={16} />, label: "Developer API Keys" },
];

const TIERS = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    cta: "Start for free",
    featured: false,
    features: [
      "3 Monitors",
      "15-min checks",
      "HTTP content monitoring",
      "Email alerts",
      "7-day retention",
    ],
  },
  {
    name: "Pro",
    price: "$19",
    cadence: "/mo",
    cta: "Upgrade to Pro",
    featured: true,
    features: [
      "25 Monitors",
      "5-min checks",
      "Visual & DOM diffing",
      "Price tracking",
      "Slack & Discord alerts",
      "30-day retention",
    ],
  },
  {
    name: "Business",
    price: "$49",
    cadence: "/mo",
    cta: "Upgrade to Business",
    featured: false,
    features: [
      "100 Monitors",
      "1-min checks",
      "Unlimited webhooks",
      "Team Workspaces (3 seats)",
      "Compliance PDF/CSV exports",
      "90-day retention",
    ],
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen overflow-hidden bg-background">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-6 lg:px-8">
        <Link href="/" className="group flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-accent shadow-sm transition-transform duration-200 group-hover:rotate-3">
            <ShieldCheck size={19} />
          </span>
          <span className="text-lg font-semibold tracking-tight">
            Apeiro
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="apeiro-btn apeiro-btn-ghost"
          >
            Sign in
          </Link>

          <Link
            href="/register"
            className="apeiro-btn apeiro-btn-primary"
          >
            Start monitoring
            <ArrowRight size={15} />
          </Link>
        </div>
      </nav>

      <section className="relative mx-auto max-w-7xl px-5 pb-20 pt-14 sm:px-6 sm:pt-20 lg:px-8 lg:pb-28 lg:pt-28">
        <div className="pointer-events-none absolute left-1/2 top-0 h-[32rem] w-[32rem] -translate-x-1/2 rounded-full bg-accent opacity-15 blur-[100px]" />

        <div className="relative mx-auto max-w-4xl text-center">
          <div className="animate-apeiro-fade-up inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3.5 py-1.5 text-xs font-semibold shadow-sm backdrop-blur">
            <span className="h-1.5 w-1.5 animate-apeiro-pulse rounded-full bg-success" />
            Competitor &amp; website monitoring
          </div>

          <h1 className="animate-apeiro-fade-up mt-7 text-5xl font-semibold tracking-[-0.045em] sm:text-6xl lg:text-7xl">
            Know the instant your competitors change their{" "}
            <span className="relative mx-2 inline-block">
              pricing or page content.
              <span className="absolute -bottom-1 left-0 right-0 -z-10 h-3 rounded-full bg-accent opacity-70" />
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Apeiro watches competitor pricing pages and the content that
            matters to you — then fires a Slack or email alert the moment
            something moves. Set it once. Never miss a price change again.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="apeiro-btn apeiro-btn-primary w-full !py-3 sm:w-auto"
            >
              Start monitoring for free
              <ArrowRight size={17} />
            </Link>

            <Link
              href="/login"
              className="apeiro-btn apeiro-btn-outline w-full !py-3 sm:w-auto"
            >
              Sign in
            </Link>
          </div>

          <div className="mt-5 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Check size={13} className="text-success" />
              No credit card
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check size={13} className="text-success" />
              Price tracking included
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check size={13} className="text-success" />
              Slack &amp; email alerts
            </span>
          </div>
        </div>

        <div className="relative mx-auto mt-16 max-w-5xl">
          <div className="apeiro-card overflow-hidden">
            <div className="flex items-center gap-2 border-b border-border px-5 py-3">
              <span className="h-2.5 w-2.5 rounded-full bg-[#ef8c8c]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#e5c46c]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#8bc98e]" />
              <div className="ml-3 h-7 flex-1 rounded-md bg-muted" />
            </div>

            <div className="grid gap-0 lg:grid-cols-2">
              <div className="border-b border-border p-6 sm:p-8 lg:border-b-0 lg:border-r">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-medium text-muted-foreground">
                    PRICE CHANGE DETECTED
                  </p>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-danger-muted px-2.5 py-1 text-xs font-semibold text-danger">
                    <span className="h-1.5 w-1.5 animate-apeiro-pulse rounded-full bg-danger" />
                    Live
                  </span>
                </div>

                <p className="mt-2 text-sm font-medium">
                  Competitor pricing — competitor.com/pricing
                </p>

                <div className="mt-4 flex items-end gap-3">
                  <span className="text-2xl font-semibold tabular-nums text-muted-foreground line-through">
                    €49
                  </span>
                  <ArrowRight size={18} className="mb-1 text-muted-foreground" />
                  <span className="text-4xl font-semibold tabular-nums text-success">
                    €59
                  </span>
                  <span className="mb-1 rounded-full bg-warning-muted px-2 py-0.5 text-xs font-semibold text-warning">
                    +20.4%
                  </span>
                </div>

                <div className="mt-4 rounded-xl border border-border bg-secondary/40 p-3 font-mono text-xs leading-6">
                  <p>
                    <span className="mr-2 select-none font-semibold text-rose-400">
                      −
                    </span>
                    <span className="text-rose-300">
                      &lt;span class=&quot;price&quot;&gt;€49&lt;/span&gt;
                    </span>
                  </p>
                  <p>
                    <span className="mr-2 select-none font-semibold text-emerald-400">
                      +
                    </span>
                    <span className="text-emerald-300">
                      &lt;span class=&quot;price&quot;&gt;€59&lt;/span&gt;
                    </span>
                  </p>
                </div>
              </div>

              <div className="space-y-4 bg-muted/30 p-6 sm:p-8">
                <p className="text-xs font-medium text-muted-foreground">
                  ALERTS FIRED INSTANTLY
                </p>

                <div className="rounded-xl border border-border bg-card p-4">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/15 text-sky-300">
                      <Hash size={15} />
                    </span>
                    <div>
                      <p className="text-sm font-semibold">Slack — #pricing</p>
                      <p className="text-xs text-muted-foreground">
                        webhook · just now
                      </p>
                    </div>
                  </div>
                  <p className="mt-3 rounded-lg bg-muted/60 px-3 py-2.5 text-sm leading-6">
                    <DollarSign size={13} className="mr-1 inline text-success" />
                    Price changed from <strong>€49</strong> to{" "}
                    <strong>€59 EUR</strong> on Competitor pricing.
                  </p>
                </div>

                <div className="rounded-xl border border-border bg-card p-4">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-300">
                      <Mail size={15} />
                    </span>
                    <div>
                      <p className="text-sm font-semibold">
                        Email — you@company.com
                      </p>
                      <p className="text-xs text-muted-foreground">
                        alert · just now
                      </p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm font-medium">
                    Apeiro: Price changed — Competitor pricing
                  </p>
                  <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                    The tracked price moved €49 → €59. Review the diff in
                    your dashboard.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-card">
        <div className="mx-auto max-w-7xl px-5 py-14 sm:px-6 lg:px-8">
          <p className="text-center text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Alerts go where your team already works
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {CHANNELS.map((channel) => (
              <span
                key={channel.label}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-2 text-sm font-medium"
              >
                {channel.icon}
                {channel.label}
              </span>
            ))}
          </div>
        </div>
        <div className="mx-auto grid max-w-7xl gap-px bg-border sm:grid-cols-3">
          <Feature
            icon={<DollarSign size={19} />}
            title="Competitor price tracking"
            text="Point Apeiro at any pricing page. Get alerted the instant a price moves."
          />
          <Feature
            icon={<ScanSearch size={19} />}
            title="Visual & DOM diffing"
            text="Screenshots and content diffs show exactly what changed on the page."
          />
          <Feature
            icon={<BellRing size={19} />}
            title="Slack, Discord & email alerts"
            text="Route alerts to Slack, Discord, any webhook, or email — plus API keys for automation."
          />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Pricing
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Start free. Upgrade when pricing intel pays for itself.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            One caught competitor price change covers months of Pro. No
            credit card to start.
          </p>
        </div>

        <div className="mx-auto mt-10 grid max-w-5xl gap-4 lg:grid-cols-3">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`apeiro-card flex flex-col p-6 ${
                tier.featured
                  ? "border-accent shadow-[0_0_0_2px_color-mix(in_srgb,var(--accent)_40%,transparent)]"
                  : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-wide">
                  {tier.name}
                </h3>
                {tier.featured && (
                  <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-semibold text-primary-foreground">
                    Most popular
                  </span>
                )}
              </div>
              <p className="mt-3">
                <span className="text-4xl font-semibold tracking-tight tabular-nums">
                  {tier.price}
                </span>
                <span className="ml-1 text-sm text-muted-foreground">
                  {tier.cadence}
                </span>
              </p>
              <ul className="mt-5 flex-1 space-y-2.5 text-sm">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check
                      size={15}
                      className="mt-0.5 shrink-0 text-success"
                    />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              <Link
                href="/register"
                className={`apeiro-btn mt-6 w-full ${
                  tier.featured
                    ? "apeiro-btn-primary"
                    : "apeiro-btn-outline"
                }`}
              >
                {tier.cta}
                <ArrowRight size={15} />
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 text-center sm:px-6 lg:px-8">
        <p className="text-sm font-medium text-muted-foreground">
          Ready to stop checking competitor pages manually?
        </p>

        <h2 className="mt-2 text-3xl font-semibold tracking-tight">
          Catch the next price change first.
        </h2>

        <Link
          href="/register"
          className="apeiro-btn apeiro-btn-primary mt-6"
        >
          Create your free account
          <ArrowRight size={16} />
        </Link>
      </section>

      <footer className="border-t border-border px-5 py-7 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} Apeiro Monitor. Know the instant
        competitors change pricing or page content.
      </footer>
    </main>
  );
}

function Feature({
  icon,
  title,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <div className="bg-card px-6 py-8 text-center">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-foreground">
        {icon}
      </div>

      <h3 className="mt-4 text-sm font-semibold">{title}</h3>

      <p className="mx-auto mt-1.5 max-w-xs text-sm leading-6 text-muted-foreground">
        {text}
      </p>
    </div>
  );
}
