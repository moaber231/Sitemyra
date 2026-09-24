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
    <section id={id} className="marketing-grid scroll-mt-24">
      {showHeading ? (
        <div className="mx-auto max-w-3xl">
          <p className="marketing-label text-xs font-medium uppercase">Pricing</p>
          <h2 className="mt-4 text-4xl sm:text-6xl">
            Start small. Upgrade when the signal is useful.
          </h2>
          <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground">
            Every account starts on the Free plan. Paid billing is optional and
            is handled through the configured checkout provider.
          </p>
        </div>
      ) : null}

      <div className="mx-auto mt-16 grid max-w-6xl items-stretch gap-0 border-2 border-border lg:grid-cols-3">
        {tiers.map((tier) => (
          <article
            key={tier.name}
            className={`group flex flex-col border-b-2 border-border p-6 transition-colors duration-100 last:border-b-0 hover:bg-black hover:text-white sm:p-8 lg:border-b-0 lg:border-r-2 lg:last:border-r-0 ${
              tier.featured
                ? "marketing-inverted relative z-10 border-2 border-black lg:-translate-y-4 lg:pb-12"
                : "bg-white"
            }`}
          >
            <div className="flex items-center justify-between gap-3 border-b border-current pb-5">
              <h3 className="font-mono text-sm uppercase tracking-[0.14em]">
                {tier.name}
              </h3>
              {tier.featured ? (
                <span className="border border-current px-2 py-1 font-mono text-[0.6rem] uppercase tracking-[0.12em]">
                  Most popular
                </span>
              ) : null}
            </div>
            <p className="mt-7 flex items-end gap-2">
              <span className="text-6xl tabular-nums leading-none">{tier.price}</span>
              <span className="pb-1 font-mono text-xs uppercase tracking-[0.1em] text-current/70">
                {tier.cadence}
              </span>
            </p>
            <p className="mt-5 min-h-14 text-sm leading-6 text-current/70">
              {tier.description}
            </p>
            <ul className="mt-8 flex-1 space-y-3 border-t border-current pt-6 text-sm">
              {tier.features.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <Check size={16} strokeWidth={1.5} className="mt-0.5 shrink-0" aria-hidden="true" />
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
              <ArrowRight size={15} strokeWidth={1.5} aria-hidden="true" />
            </Link>
          </article>
        ))}
      </div>

      <p className="mx-auto mt-8 max-w-3xl text-center font-mono text-[0.68rem] leading-5 uppercase tracking-[0.08em] text-muted-foreground">
        Prices are shown in USD. Create an account to start on Free; paid plan
        availability depends on the live billing configuration. See the{" "}
        <Link
          href="/terms#subscriptions"
          className="underline underline-offset-4 hover:text-foreground"
        >
          subscription terms
        </Link>{" "}
        for details.
      </p>
    </section>
  );
}
