import Link from "next/link";

import { LegalPage, LegalSection, ReviewNote } from "@/components/marketing/legal-page";
import { marketingMetadata } from "@/lib/marketing-seo";

export const metadata = marketingMetadata({
  title: "Terms of Service",
  description:
    "Terms for using the Sitemyra competitor monitoring service, including accounts, monitoring, subscriptions, and acceptable use.",
  path: "/terms",
});

export default function TermsPage() {
  return (
    <LegalPage
      eyebrow="Legal"
      title="Terms of Service"
      description="These terms describe the responsibilities and limits that apply when you use the current Sitemyra application. They are a product summary and need review against the operator's final business and legal setup."
    >
      <ReviewNote>
        Before Sitemyra accepts paid subscriptions, the founder should have a
        qualified Greek accountant or legal professional confirm the legal
        operator, business/tax setup, invoice requirements, consumer terms,
        governing law, and refund process. This page intentionally does not guess
        those details.
      </ReviewNote>

      <LegalSection title="1. Agreement and operator">
        <p>
          By creating an account or using Sitemyra, you agree to these terms and
          to the policies linked on this site. Sitemyra is an independent SaaS
          project built in Greece by Konstantinos Gkogkos. The legal operator
          name, registration number, business address, VAT status, and invoicing
          details are not yet verified in this repository and must be added
          before the service takes paid subscriptions.
        </p>
        <p>
          If you do not agree with these terms, do not create an account or use
          the service.
        </p>
      </LegalSection>

      <LegalSection title="2. Account responsibilities">
        <p>
          You are responsible for providing accurate account information,
          keeping your password and sign-in credentials secure, and signing out
          of shared devices. You are responsible for activity performed through
          your account and for revoking access you no longer need.
        </p>
        <p>
          You must be old enough to enter into an agreement in your location and
          must not use Sitemyra unlawfully. Tell the founder promptly if you
          believe your account or an API key has been compromised.
        </p>
      </LegalSection>

      <LegalSection title="3. Acceptable use and monitoring pages">
        <p>
          Sitemyra is intended for monitoring publicly accessible pages that you
          own or are authorized to access. You must not use the service to bypass
          authentication, access controls, paywalls, robots restrictions, or
          other technical measures; to overload, probe, or disrupt a website; to
          collect personal data in violation of applicable law; to monitor
          private infrastructure; or to interfere with Sitemyra or its providers.
        </p>
        <p>
          The service blocks certain private, reserved, loopback, link-local,
          multicast, and cloud-metadata destinations, as well as unsupported
          ports and credential-bearing URLs. You remain responsible for the URLs
          you submit and for complying with the target site's terms and laws.
        </p>
      </LegalSection>

      <LegalSection title="4. Plans, subscriptions, and cancellation">
        <div id="subscriptions" className="scroll-mt-28">
          <LegalSection title="Plans and billing" headingLevel="h3">
            <p>
              New accounts start on the Free plan. Paid plan prices, limits, and
              availability are shown on the Pricing page and can change as the
              product evolves. If paid billing is enabled, checkout and
              subscription management are provided by the configured payment
              provider. Sitemyra may disable paid checkout when billing is not
              configured.
            </p>
            <p>
              You are responsible for providing a valid payment method through
              the payment provider and for any taxes or charges that apply to
              your use. Sitemyra does not store full payment-card details in its
              application database.
            </p>
          </LegalSection>
        </div>
        <LegalSection title="Cancellation and refunds" headingLevel="h3">
          <p>
            When a paid subscription is available, cancellation is handled
            through the customer portal or the cancellation controls provided by
            the payment provider. Access and limits after cancellation are
            handled by the current downgrade behavior in the application.
          </p>
          <p>
            A final refund policy has not yet been verified and is not promised
            on this page. Refund eligibility, timing, taxes, and any cancellation
            fee must be confirmed by the operator and will apply as required by
            law. Contact the founder before relying on a refund or cancelling a
            subscription if you need clarification.
          </p>
        </LegalSection>
      </LegalSection>

      <LegalSection title="5. Your content and monitored information">
        <p>
          You keep ownership of the names, URLs, selectors, and other content you
          submit. You grant Sitemyra the limited permission needed to store that
          information, fetch the pages you request, create the monitoring
          results you request, and send the notifications you configure.
        </p>
        <p>
          Sitemyra may retain check results, screenshots, DOM or HTML artifacts,
          price points, and diffs according to the plan and retention settings.
          You are responsible for making sure that your use of the service and
          the pages you monitor comply with applicable law and third-party
          rights.
        </p>
      </LegalSection>

      <LegalSection title="6. Intellectual property">
        <p>
          The Sitemyra application, software, design, documentation, and brand
          are owned by their respective rights holders. These terms do not
          transfer ownership of the service to you. You may use the service only
          for its intended purpose and may not copy, resell, reverse engineer,
          or misuse the application except where applicable law expressly allows
          it.
        </p>
      </LegalSection>

      <LegalSection title="7. Third-party pages and services">
        <p>
          Sitemyra does not control the websites you monitor, the providers you
          connect, or the payment, email, sign-in, and storage services that may
          be enabled. Their availability, terms, privacy practices, and content
          are their own. A change detected by Sitemyra is an observation from a
          scheduled check, not a guarantee that a page is correct, current, or
          safe.
        </p>
      </LegalSection>

      <LegalSection title="8. Availability and service changes">
        <p>
          Sitemyra is provided on an ongoing best-effort basis. Checks can be
          delayed by target-site errors, rate limits, network failures, browser
          failures, maintenance, or infrastructure incidents. Sitemyra may
          change, suspend, or discontinue features and may modify plan limits as
          the product develops. We do not promise a specific uptime percentage.
        </p>
      </LegalSection>

      <LegalSection title="9. Disclaimers and limitation of liability">
        <p>
          To the fullest extent permitted by applicable law, Sitemyra is provided
          "as is" and "as available" without warranties of merchantability,
          fitness for a particular purpose, accuracy, or uninterrupted
          availability. Monitoring output is informational and should not be
          the sole basis for business, legal, financial, or security decisions.
        </p>
        <p>
          To the fullest extent permitted by applicable law, the operator will
          not be liable for indirect, incidental, special, consequential, or
          punitive damages, or for lost profits, revenue, data, or business
          opportunity, arising from the service or these terms. Any liability
          cap, exclusions, or required consumer rights must be reviewed and
          completed by the operator with qualified professional advice.
        </p>
      </LegalSection>

      <LegalSection title="10. Suspension and termination">
        <p>
          You may stop using Sitemyra and request account deletion through the
          contact route. The operator may suspend or terminate access for a
          material breach, unlawful activity, abuse, non-payment, or a security
          risk. Where appropriate, the operator will try to provide notice and an
          opportunity to address a fixable issue.
        </p>
        <p>
          Sections concerning payment, intellectual property, liability, and
          dispute resolution may continue after termination where applicable.
        </p>
      </LegalSection>

      <LegalSection title="11. Governing law and disputes">
        <p>
          The governing law, courts, dispute process, and any mandatory consumer
          rights have not yet been verified for the operator. They must be added
          before the final commercial launch. Nothing in this page excludes
          rights that cannot lawfully be excluded.
        </p>
      </LegalSection>

      <LegalSection title="12. Contact and changes">
        <p>
          Use the <Link href="/contact">contact page</Link> for questions about
          these terms. The operator may update these terms as the product and
          business setup change. The effective date and any material change
          notice should be added after professional review.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
