import Link from "next/link";
import type { ReactNode } from "react";

import { MarketingShell } from "@/components/marketing/marketing-shell";

const legalNavigation = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
  { label: "Cookie Policy", href: "/cookies" },
  { label: "Security", href: "/security" },
];

export function LegalPage({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <MarketingShell>
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-6 sm:py-20 lg:px-8">
        <header className="max-w-3xl">
          <div className="section-label">
            <span aria-hidden="true" />
            {eyebrow}
          </div>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            {title}
          </h1>
          <p className="mt-5 text-base leading-7 text-muted-foreground">
            {description}
          </p>
        </header>

        <div className="marketing-grid mt-12 grid gap-10 rounded-3xl border border-border bg-card/70 p-5 shadow-sm sm:p-8 lg:grid-cols-[13rem_minmax(0,46rem)] lg:gap-16">
          <aside className="lg:sticky lg:top-28 lg:self-start">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-foreground">
              Policies
            </p>
            <nav className="mt-4 grid gap-2" aria-label="Policy navigation">
              {legalNavigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-sm text-muted-foreground transition hover:text-foreground"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </aside>

          <article className="min-w-0 space-y-10 rounded-2xl bg-background/70 p-5 sm:p-7">{children}</article>
        </div>
      </div>
    </MarketingShell>
  );
}

export function LegalSection({
  title,
  children,
  headingLevel = "h2",
}: {
  title: string;
  children: ReactNode;
  headingLevel?: "h2" | "h3";
}) {
  return (
    <section>
      {headingLevel === "h3" ? (
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      ) : (
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      )}
      <div className="mt-3 space-y-4 text-sm leading-7 text-muted-foreground [&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-4 [&_a:hover]:text-accent [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_strong]:text-foreground">
        {children}
      </div>
    </section>
  );
}

export function ReviewNote({ children }: { children: ReactNode }) {
  return (
    <aside className="rounded-xl border border-accent/20 bg-accent/5 p-4 text-sm leading-6 text-foreground shadow-sm">
      <strong className="block text-sm">Operator review note</strong>
      <span className="mt-1 block text-muted-foreground">{children}</span>
    </aside>
  );
}
