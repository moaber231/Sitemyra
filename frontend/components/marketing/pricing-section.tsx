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
    <section id={id} className="scroll-mt-24">
      {showHeading ? (
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Pricing
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Start small. Upgrade when the signal is useful.
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Every account starts on the Free plan. Paid billing is optional and
            is handled through the configured checkout provider.
          </p>
        </div>
      ) : null}

      <div className="mx-auto mt-10 grid max-w-5xl gap-4 lg:grid-cols-3">
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={`apeiro-card flex flex-col p-6 ${
              tier.featured
                ? "border-accent shadow-[0_0_0_2px_color-mix(in_srgb,var(--accent)_40%,transparent)]"
                : ""
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold uppercase tracking-wide">
                {tier.name}
              </h3>
              {tier.featured ? (
                <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-semibold text-accent-foreground">
                  Most popular
                </span>
              ) : null}
            </div>
            <p className="mt-4">
              <span className="text-4xl font-semibold tracking-tight tabular-nums">
                {tier.price}
              </span>
              <span className="ml-1 text-sm text-muted-foreground">
                {tier.cadence}
              </span>
            </p>
            <p className="mt-3 min-h-10 text-sm leading-6 text-muted-foreground">
              {tier.description}
            </p>
            <ul className="mt-5 flex-1 space-y-2.5 text-sm">
              {tier.features.map((feature) => (
                <li key={feature} className="flex items-start gap-2">
                  <Check
                    size={15}
                    className="mt-0.5 shrink-0 text-success"
                    aria-hidden="true"
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
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        ))}
      </div>

      <p className="mx-auto mt-5 max-w-3xl text-center text-xs leading-5 text-muted-foreground">
        Prices are shown in USD. Create an account to start on Free; paid plan
        availability depends on the live billing configuration. See the{" "}
        <Link href="/terms#subscriptions" className="underline underline-offset-4 hover:text-foreground">
          subscription terms
        </Link>{" "}
        for details.
      </p>
    </section>
  );
}
