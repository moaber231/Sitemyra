import Link from "next/link";
import { ArrowRight, CheckCircle2, LockKeyhole, ShieldCheck } from "lucide-react";

import { LegalPage, LegalSection, ReviewNote } from "@/components/marketing/legal-page";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "Security",
  description:
    "A transparent overview of the security practices implemented in the Sitemyra application and deployment.",
  path: "/security",
});

const practices = [
  "Production settings enforce HTTPS redirects, secure cookies, HSTS, and clickjacking protection.",
  "Application secrets are supplied through environment configuration and are excluded from source control.",
  "Passwords are handled through Django password hashing; JWT access tokens are short-lived and kept in browser session storage.",
  "Webhook destinations are encrypted at rest, and developer API keys are stored as hashes rather than raw secrets.",
  "Monitored URLs are checked for unsafe destinations, private or reserved networks, metadata hosts, unsupported ports, and credential-bearing URLs.",
  "Production services run as separate Docker workloads with health checks and restart policies.",
];

export default function SecurityPage() {
  return (
    <LegalPage
      eyebrow="Security"
      title="Security, without the theatre."
      description="This page describes controls that are present in the current Sitemyra codebase. It is not a certification and does not claim an audit, penetration test, or compliance certification."
    >
      <div className="rounded-xl border border-accent/25 bg-accent/5 p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck size={20} className="mt-0.5 shrink-0 text-accent" aria-hidden="true" />
          <div>
            <h2 className="font-semibold">Our current position</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Sitemyra is an early-stage product operated as an independent
              project. We publish the controls we can verify and avoid making
              claims about certifications or formal audits that have not been
              completed.
            </p>
          </div>
        </div>
      </div>

      <LegalSection title="Implemented practices">
        <ul className="space-y-3">
          {practices.map((practice) => (
            <li key={practice} className="flex items-start gap-2">
              <CheckCircle2 size={16} className="mt-1 shrink-0 text-success" aria-hidden="true" />
              <span>{practice}</span>
            </li>
          ))}
        </ul>
      </LegalSection>

      <LegalSection title="Data handling in the application">
        <p>
          The application stores account information, the URLs and settings you
          choose for monitors, check results, notification preferences, and
          delivery records. Webhook secrets are encrypted before storage. The
          application does not claim to make monitored pages private or to
          bypass access controls.
        </p>
        <p>
          Monitoring requests are intended for publicly accessible pages. The
          URL validation layer blocks private and reserved network destinations,
          cloud metadata hosts, unsupported ports, and URLs containing embedded
          credentials. Browser-based checks also validate page requests and
          redirects.
        </p>
      </LegalSection>

      <LegalSection title="Deployment boundaries">
        <p>
          The production Compose setup separates the web application, API,
          Celery workers, scheduler, PostgreSQL, and Redis into distinct
          services. It uses health checks, restart policies, and environment-based
          secrets. TLS termination is expected to happen at the hosting or edge
          layer; that edge configuration is outside this repository.
        </p>
        <ReviewNote>
          The repository does not contain an Nginx configuration or evidence of
          a formal certificate-renewal process. Those details should be
          documented by the operator after the hosting setup is verified.
        </ReviewNote>
      </LegalSection>

      <LegalSection title="What this page does not claim">
        <p>
          Sitemyra does not claim SOC 2, ISO 27001, GDPR certification, a formal
          penetration test, zero vulnerabilities, military-grade security, or
          enterprise compliance. No software can promise uninterrupted
          availability or absolute security.
        </p>
      </LegalSection>

      <LegalSection title="Reporting a concern">
        <p>
          If you find a security issue, use the <Link href="/contact">contact page</Link> and
          describe the issue without sending passwords, API keys, webhook
          secrets, or payment details. Please allow a reasonable amount of time
          for the founder to investigate before public disclosure.
        </p>
      </LegalSection>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-secondary/30 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <LockKeyhole size={19} className="text-accent" aria-hidden="true" />
          <span className="text-sm text-muted-foreground">Want the full data picture?</span>
        </div>
        <Link href="/privacy" className="inline-flex items-center gap-2 text-sm font-semibold text-foreground underline underline-offset-4 hover:text-accent">
          Read the Privacy Policy
          <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </LegalPage>
  );
}
