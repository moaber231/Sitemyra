import Link from "next/link";
import { ArrowRight, Check } from "lucide-react";

const tiers = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    description: "A practical way to start monitoring a few important pages.",
    features: [
      "3 monitors",
      "15-minute checks",
      "HTTP content monitoring",
      "Email alerts",
      "7-day history",
    ],
    cta: "Start for free",
    featured: false,
  },
  {
    name: "Pro",
    price: "$19",
    cadence: "/month",
    description: "More frequent checks and deeper change detection for growing teams.",
    features: [
      "25 monitors",
      "5-minute checks",
      "Visual and DOM diffing",
      "Price tracking",
      "Slack and Discord alerts",
      "30-day history",
    ],
    cta: "Start with Free",
    featured: true,
  },
  {
    name: "Business",
    price: "$49",
    cadence: "/month",
    description: "More monitors, faster checks, and collaboration features.",
    features: [
      "100 monitors",
      "1-minute checks",
      "Up to 50 alert channels",
      "Team workspaces",
      "Compliance PDF/CSV exports",
      "90-day history",
    ],
    cta: "Start with Free",
    featured: false,
  },
];

export function PricingSection({
  id = "pricing",
  showHeading = true,
}: {
  id?: string;
  showHeading?: boolean;
}) {
  return (
    <section id={id} className="marketing-grid scroll-mt-24 rounded-3xl px-4 py-5 sm:px-6 lg:px-8">
      {showHeading ? (
        <div className="mx-auto max-w-3xl">
          <div className="section-label">
            <span aria-hidden="true" />
            Pricing
          </div>
          <h2 className="mt-5 text-4xl sm:text-6xl">
            Start small. Upgrade when the signal is{" "}
            <span className="gradient-text">useful.</span>
          </h2>
          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground">
            Every account starts on the Free plan. Paid billing is optional and
            is handled through the configured checkout provider.
          </p>
        </div>
      ) : null}

      <div className="mx-auto mt-14 grid max-w-6xl items-stretch gap-5 lg:grid-cols-3">
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={`group relative rounded-2xl p-[2px] transition-transform duration-300 hover:-translate-y-1 ${
              tier.featured
                ? "bg-gradient-to-br from-accent via-accent-secondary to-accent shadow-[0_18px_42px_rgb(0_82_255_/_0.2)] lg:-translate-y-4"
                : "border border-border bg-card shadow-sm hover:border-accent/30 hover:shadow-lg"
            }`}
          >
            <article
              className={`flex h-full flex-col rounded-[calc(1rem-2px)] bg-card p-6 sm:p-8 ${
                tier.featured ? "ring-1 ring-accent/10" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-foreground">
                  {tier.name}
                </h3>
                {tier.featured ? (
                  <span className="rounded-full border border-accent/20 bg-accent/5 px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-accent">
                    Most popular
                  </span>
                ) : null}
              </div>

              <p className="mt-7 flex items-end gap-2">
                <span className="text-6xl font-semibold leading-none tracking-tight tabular-nums text-foreground">
                  {tier.price}
                </span>
                <span className="pb-1 font-mono text-xs uppercase tracking-[0.08em] text-muted-foreground">
                  {tier.cadence}
                </span>
              </p>
              <p className="mt-5 min-h-14 text-sm leading-6 text-muted-foreground">
                {tier.description}
              </p>

              <ul className="mt-8 flex-1 space-y-3 border-t border-border pt-6 text-sm text-foreground">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
                      <Check size={13} strokeWidth={2.2} aria-hidden="true" />
                    </span>
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href="/register"
                className={`apeiro-btn mt-10 w-full ${
                  tier.featured ? "apeiro-btn-primary" : "apeiro-btn-outline"
                }`}
              >
                {tier.cta}
                <ArrowRight
                  size={15}
                  strokeWidth={1.8}
                  className="transition-transform duration-200 group-hover:translate-x-1"
                  aria-hidden="true"
                />
              </Link>
            </article>
          </div>
        ))}
      </div>

      <p className="mx-auto mt-8 max-w-3xl text-center font-mono text-[0.68rem] leading-5 text-muted-foreground">
        Prices are shown in USD. Create an account to start on Free; paid plan
        availability depends on the live billing configuration. See the{" "}
        <Link
          href="/terms#subscriptions"
          className="font-semibold text-accent underline underline-offset-4"
        >
          subscription terms
        </Link>{" "}
        for details.
      </p>
    </section>
  );
}
