import Link from "next/link";
import { ArrowRight, ChevronDown, MessageCircleQuestion } from "lucide-react";

import { MarketingShell } from "@/components/marketing/marketing-shell";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "FAQ",
  description:
    "Answers about Sitemyra competitor monitoring, supported changes, alerts, plans, and account data.",
  path: "/faq",
});

const questions = [
  {
    question: "What is Sitemyra?",
    answer:
      "Sitemyra is an independent SaaS project for monitoring public competitor pages. It can check supported pages for content, DOM, visual, price, and response-status information, then show the result in your dashboard and notify configured channels.",
  },
  {
    question: "What can I monitor?",
    answer:
      "You can choose public pricing, product, landing, and content pages that you are authorized to access. The monitoring mode and frequency available to you depend on your plan.",
  },
  {
    question: "How does change detection work?",
    answer:
      "A scheduled check fetches the page. Depending on the mode, Sitemyra compares content, selected DOM content, a screenshot, or a selected price. A change is recorded when the configured comparison detects a difference.",
  },
  {
    question: "What happens when a change is detected?",
    answer:
      "The result appears in your monitor history. If the relevant notification preference and channel are enabled, Sitemyra can send an email or deliver an alert to a Slack, Discord, or generic webhook destination you configured.",
  },
  {
    question: "Can I monitor any website?",
    answer:
      "Sitemyra is intended for publicly accessible pages you are allowed to access. The application rejects unsafe destinations such as private or reserved networks, cloud metadata hosts, unsupported ports, and URLs with embedded credentials. It does not bypass authentication or access controls.",
  },
  {
    question: "Does the Free plan require a credit card?",
    answer:
      "The account creation flow creates a Free account without requesting payment details. Paid plan availability depends on the live billing configuration.",
  },
  {
    question: "How often does Sitemyra check a page?",
    answer:
      "The available check interval depends on the plan. The current plan limits are shown on the Pricing page. Scheduled checks are not a guarantee of instant detection during an outage or a provider delay.",
  },
  {
    question: "Where is my data stored and how long is it kept?",
    answer:
      "Sitemyra stores the account and monitoring data needed to provide the service. Check history and stored artifacts are limited by the plan history window and any configured artifact retention cap. Read the Privacy Policy for the current description and the remaining operator details that still need verification.",
  },
  {
    question: "Who operates Sitemyra?",
    answer:
      "Sitemyra is an independent SaaS project built in Greece by Konstantinos Gkogkos. The About page includes the founder's public GitHub, LinkedIn, and portfolio links.",
  },
  {
    question: "How can I contact the founder?",
    answer:
      "Use the Contact page. If a dedicated Sitemyra email has not been published yet, the page provides direct links to the founder's public profiles.",
  },
];

export default function FaqPage() {
  return (
    <MarketingShell>
      <section className="marketing-noise relative overflow-hidden border-b-4 px-5 pb-14 pt-16 sm:px-6 sm:pt-24 lg:px-8">
        <div className="marketing-orb" aria-hidden="true" />
        <div className="relative mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            FAQ
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-6xl">
            Straight answers about monitoring.
          </h1>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            The basics of what Sitemyra checks, what it stores, and how to get
            started.
          </p>
        </div>
      </section>

      <section className="marketing-grid border-y-4 px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="space-y-3">
            {questions.map((item) => (
              <details key={item.question} className="group apeiro-card overflow-hidden">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-5 text-left font-semibold marker:hidden [&::-webkit-details-marker]:hidden">
                  <span>{item.question}</span>
                  <ChevronDown size={18} className="shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
                <div className="border-t border-border px-5 py-5 text-sm leading-7 text-muted-foreground">
                  {item.answer}
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-5 rounded-2xl border border-border bg-secondary/30 p-7 text-center sm:p-9">
          <MessageCircleQuestion size={25} className="text-accent" aria-hidden="true" />
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Still have a question?</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Ask a product question or report feedback directly to the founder.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/contact" className="apeiro-btn apeiro-btn-primary">
              Contact Sitemyra
              <ArrowRight size={15} aria-hidden="true" />
            </Link>
            <Link href="/security" className="apeiro-btn apeiro-btn-outline">
              Read security details
            </Link>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
