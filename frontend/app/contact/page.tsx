import Link from "next/link";
import {
  ArrowRight,
  BriefcaseBusiness,
  Code2,
  ExternalLink,
  Handshake,
  Mail,
  MessageSquareText,
  ShieldAlert,
} from "lucide-react";

import { MarketingShell } from "@/components/marketing/marketing-shell";
import { FOUNDER_LINKS, getPublicContactEmail } from "@/lib/site";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "Contact Sitemyra",
  description:
    "Contact the independent founder of Sitemyra with questions, feedback, support, or partnership inquiries.",
  path: "/contact",
});

const topics = [
  {
    icon: MessageSquareText,
    title: "General questions",
    text: "Ask about the product, the free plan, or how monitoring works.",
  },
  {
    icon: ShieldAlert,
    title: "Product and support",
    text: "Report a problem with a monitor, alert, account, or billing flow.",
  },
  {
    icon: Handshake,
    title: "Feedback",
    text: "Tell us what would make Sitemyra more useful for your workflow.",
  },
  {
    icon: BriefcaseBusiness,
    title: "Partnership and business inquiries",
    text: "Discuss a relevant collaboration or business conversation.",
  },
];

export default function ContactPage() {
  const contactEmail = getPublicContactEmail();
  const mailto = contactEmail
    ? `mailto:${contactEmail}?subject=Sitemyra%20contact`
    : "";

  return (
    <MarketingShell>
      <section className="marketing-noise relative overflow-hidden border-b-4 px-5 pb-16 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <div className="marketing-orb" aria-hidden="true" />
        <div className="relative mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Contact
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-6xl">
            Talk to the person building Sitemyra.
          </h1>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Sitemyra is an independent project. Questions, feedback, and
            business inquiries are welcome.
          </p>

          {mailto ? (
            <a href={mailto} className="apeiro-btn apeiro-btn-primary mt-8">
              <Mail size={16} aria-hidden="true" />
              Email Sitemyra
            </a>
          ) : (
            <div className="mx-auto mt-8 max-w-xl rounded-xl border border-warning/30 bg-warning-muted/30 p-4 text-left text-sm leading-6 text-muted-foreground">
              <strong className="text-foreground">A dedicated contact address is not published yet.</strong>{" "}
              The founder can be reached through the verified links below. The
              page is ready for a Sitemyra address once one is configured.
            </div>
          )}
        </div>
      </section>

      <section className="marketing-diagonal border-y-4 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              What can you write about?
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">
              Choose the topic that fits.
            </h2>
          </div>
          <div className="mt-9 grid gap-4 sm:grid-cols-2">
            {topics.map((topic) => (
              <div key={topic.title} className="apeiro-card p-6">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary text-accent">
                  <topic.icon size={19} aria-hidden="true" />
                </span>
                <h3 className="mt-5 font-semibold">{topic.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {topic.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-2">
          <div className="apeiro-card p-6 sm:p-8">
            <h2 className="text-xl font-semibold">Reach the founder directly</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              These public links are provided by the founder and are the best
              way to make contact while a dedicated support address is being
              finalized.
            </p>
            <div className="mt-6 grid gap-3">
              <a
                href={FOUNDER_LINKS[0].href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-semibold underline underline-offset-4 hover:text-accent"
              >
                <Code2 size={16} aria-hidden="true" />
                GitHub — moaber231
              </a>
              <a
                href={FOUNDER_LINKS[1].href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-semibold underline underline-offset-4 hover:text-accent"
              >
                <ExternalLink size={16} aria-hidden="true" />
                LinkedIn — Konstantinos Gkogkos
              </a>
              <a
                href={FOUNDER_LINKS[2].href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-semibold underline underline-offset-4 hover:text-accent"
              >
                Portfolio
              </a>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-secondary/30 p-6 sm:p-8">
            <h2 className="text-xl font-semibold">A note about privacy</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Please do not send passwords, API keys, webhook secrets, payment
              card details, or other sensitive information by email. If you have
              a security concern, use the contact route above and describe the
              issue without including a secret.
            </p>
            <Link href="/security" className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-foreground underline underline-offset-4 hover:text-accent">
              Read the security overview
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
