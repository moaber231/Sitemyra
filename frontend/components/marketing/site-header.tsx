"use client";

import Link from "next/link";
import { Menu, ShieldCheck, X } from "lucide-react";

const navigation = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/faq", label: "FAQ" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex min-h-[4.75rem] max-w-6xl items-center justify-between gap-4 px-5 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-2.5"
          aria-label="Sitemyra home"
        >
          <span className="modern-icon h-9 w-9 rounded-xl transition-transform duration-300 group-hover:rotate-6 group-hover:scale-105">
            <ShieldCheck size={19} strokeWidth={1.8} aria-hidden="true" />
          </span>
          <span className="font-display text-xl tracking-tight text-foreground">
            Sitemyra
          </span>
        </Link>

        <nav
          aria-label="Primary navigation"
          className="hidden items-center gap-1 lg:flex"
        >
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors duration-200 hover:bg-accent/5 hover:text-accent"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 sm:flex">
          <Link
            href="/login"
            className="apeiro-btn apeiro-btn-ghost !min-h-10 !px-3 !py-2 text-sm"
          >
            Sign in
          </Link>
          <Link href="/register" className="apeiro-btn apeiro-btn-primary !min-h-10 !px-4 !py-2">
            Get started
            <span aria-hidden="true">→</span>
          </Link>
        </div>

        <details className="group relative sm:hidden">
          <summary className="flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-xl border border-border bg-card text-foreground shadow-sm transition hover:border-accent/30 hover:text-accent [&::-webkit-details-marker]:hidden">
            <Menu size={19} className="group-open:hidden" aria-hidden="true" />
            <X size={19} className="hidden group-open:block" aria-hidden="true" />
            <span className="sr-only">Toggle navigation</span>
          </summary>
          <div className="absolute right-0 top-14 z-50 w-72 max-w-[calc(100vw-2.5rem)] rounded-2xl border border-border bg-card p-2 shadow-xl">
            <nav aria-label="Mobile navigation" className="grid gap-1">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-xl px-3 py-3 text-sm font-medium text-muted-foreground transition hover:bg-accent/5 hover:text-accent"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="my-2 border-t border-border" />
            <div className="grid grid-cols-2 gap-2">
              <Link
                href="/login"
                className="apeiro-btn apeiro-btn-outline !min-h-10 !px-2 !py-2 text-xs"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="apeiro-btn apeiro-btn-primary !min-h-10 !px-2 !py-2 text-xs"
              >
                Get started
              </Link>
            </div>
          </div>
        </details>
      </div>
    </header>
  );
}
