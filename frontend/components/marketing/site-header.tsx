import Link from "next/link";
import { ArrowRight, Menu, ShieldCheck } from "lucide-react";

const navigation = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/faq", label: "FAQ" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-background/90 backdrop-blur-xl">
      <div className="mx-auto flex min-h-[4.5rem] max-w-7xl items-center justify-between gap-4 px-5 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-2.5"
          aria-label="Sitemyra home"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-accent shadow-sm transition-transform duration-200 group-hover:rotate-3">
            <ShieldCheck size={19} aria-hidden="true" />
          </span>
          <span className="text-lg font-semibold tracking-tight">Sitemyra</span>
        </Link>

        <nav
          className="hidden items-center gap-1 lg:flex"
          aria-label="Primary navigation"
        >
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-lg px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 sm:flex">
          <Link href="/login" className="apeiro-btn apeiro-btn-ghost">
            Sign in
          </Link>
          <Link href="/register" className="apeiro-btn apeiro-btn-primary">
            Start monitoring
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>

        <details className="group relative lg:hidden">
          <summary className="flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-lg border border-border bg-card text-muted-foreground transition hover:bg-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
            <Menu size={19} aria-hidden="true" />
            <span className="sr-only">Open navigation</span>
          </summary>
          <div className="absolute right-0 top-12 z-50 w-64 max-w-[calc(100vw-2.5rem)] rounded-xl border border-border bg-card p-2 shadow-2xl">
            <nav aria-label="Mobile navigation" className="grid gap-1">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
                >
                  {item.label}
                </Link>
              ))}
              <div className="my-1 border-t border-border" />
              <Link
                href="/login"
                className="rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="apeiro-btn apeiro-btn-primary mt-1 w-full"
              >
                Start monitoring
                <ArrowRight size={15} aria-hidden="true" />
              </Link>
            </nav>
          </div>
        </details>
      </div>
    </header>
  );
}
