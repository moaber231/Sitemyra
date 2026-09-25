import Link from "next/link";
import type { ReactNode } from "react";
import { ExternalLink, Mail, ShieldCheck } from "lucide-react";

import { FOUNDER_LINKS, getPublicContactEmail, SITE_NAME } from "@/lib/site";

const footerGroups = [
  {
    title: "Product",
    links: [
      { label: "Features", href: "/#features" },
      { label: "Website construction", href: "/services" },
      { label: "How it works", href: "/how-it-works" },
      { label: "Pricing", href: "/pricing" },
      { label: "FAQ", href: "/faq" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Contact", href: "/contact" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Security", href: "/security" },
      { label: "How monitoring works", href: "/how-it-works#examples" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy Policy", href: "/privacy" },
      { label: "Terms of Service", href: "/terms" },
      { label: "Cookie Policy", href: "/cookies" },
    ],
  },
];

function FounderLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground"
    >
      {children}
    </a>
  );
}

export function SiteFooter() {
  const contactEmail = getPublicContactEmail();

  return (
    <footer className="marketing-inverted border-t border-white/10">
      <div className="mx-auto max-w-6xl px-5 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-[1.35fr_2fr]">
          <div>
            <Link href="/" className="inline-flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                <ShieldCheck size={18} aria-hidden="true" />
              </span>
              <span className="font-display text-xl text-white">Sitemyra</span>
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-6 text-muted-foreground">
              Know when your competitors change. An independent SaaS project
              built in Greece for people who need to keep an eye on the web.
            </p>
            {contactEmail ? (
              <a
                href={`mailto:${contactEmail}`}
                className="mt-4 inline-flex items-center gap-2 text-sm text-foreground underline decoration-border underline-offset-4 transition hover:text-accent"
              >
                <Mail size={15} aria-hidden="true" />
                {contactEmail}
              </a>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-x-6 gap-y-9 sm:grid-cols-4">
            {footerGroups.map((group) => (
              <div key={group.title}>
                <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-foreground">
                  {group.title}
                </h2>
                <ul className="mt-4 space-y-3">
                  {group.links.map((link) => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="text-sm text-muted-foreground transition hover:text-foreground"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-10 border-t border-border pt-6">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-muted-foreground">
              © {new Date().getFullYear()} {SITE_NAME}. Built independently in
              Greece.
            </p>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-foreground">
                Founder
              </p>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                <FounderLink href={FOUNDER_LINKS[0].href}>
                  <ExternalLink size={14} aria-hidden="true" />
                  GitHub
                </FounderLink>
                <FounderLink href={FOUNDER_LINKS[1].href}>
                  <ExternalLink size={14} aria-hidden="true" />
                  LinkedIn
                </FounderLink>
                <FounderLink href={FOUNDER_LINKS[2].href}>
                  Portfolio
                </FounderLink>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
