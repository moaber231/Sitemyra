import Link from "next/link";

import { LegalPage, LegalSection, ReviewNote } from "@/components/marketing/legal-page";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "Cookie Policy",
  description:
    "A transparent explanation of the cookies and browser storage currently used by Sitemyra.",
  path: "/cookies",
});

export default function CookiesPage() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Cookie Policy"
      description="Sitemyra currently focuses on essential account functionality. This page explains the browser storage visible in the application and does not claim an analytics or advertising program that is not present in the repository."
    >
      <LegalSection title="1. Cookies currently used">
        <p>
          The current Sitemyra frontend does not set advertising cookies, and no
          analytics provider is integrated in the application code. The core
          product uses the account email, server-side records, and short-lived
          authentication tokens rather than advertising identifiers.
        </p>
        <p>
          Depending on the hosting or edge layer, essential infrastructure
          cookies may be used for security, load balancing, or session
          protection. Those cookies are controlled by the relevant provider and
          are not described as Sitemyra analytics cookies.
        </p>
      </LegalSection>

      <LegalSection title="2. Browser session storage">
        <p>
          When you sign in, the frontend stores access and refresh tokens in the
          browser&apos;s <code>sessionStorage</code> so they are available to API
          requests during the current browser session. Session storage is not
          the same as a persistent cookie and is cleared when the browser session
          ends, subject to the browser&apos;s behavior. The frontend does not
          write these tokens to <code>localStorage</code>.
        </p>
        <p>
          The sign-in flow may also store a short-lived OAuth provider value
          while completing a Google or GitHub authorization-code flow.
        </p>
      </LegalSection>

      <LegalSection title="3. Managing browser storage">
        <p>
          You can clear site data or session storage through your browser
          settings. Doing so signs you out and may remove in-progress sign-in
          state. Sitemyra does not currently offer an advertising consent
          banner because no advertising or analytics tracker is integrated in
          the repository.
        </p>
      </LegalSection>

      <LegalSection title="4. Changes to this policy">
        <p>
          If a cookie, analytics provider, or other tracking technology is added,
          this page should be updated with its purpose, provider, duration, and
          any applicable consent mechanism. Users can contact the founder with
          questions through the <Link href="/contact">contact page</Link>.
        </p>
        <ReviewNote>
          The final operator should verify whether the hosting, payment, email,
          or sign-in providers set their own cookies or similar browser
          technologies and document those provider-specific practices where
          required.
        </ReviewNote>
      </LegalSection>
    </LegalPage>
  );
}
