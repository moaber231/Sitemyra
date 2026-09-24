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
    <header className="sticky top-0 z-40 border-b-2 bg-white">
      <div className="mx-auto flex min-h-[4.5rem] max-w-6xl items-center justify-between gap-4 px-5 sm:px-6 lg:px-8">
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-2.5"
          aria-label="Sitemyra home"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-transform duration-200 group-hover:rotate-3">
            <ShieldCheck size={19} aria-hidden="true" />
          </span>
          <span className="marketing-display text-xl">Sitemyra</span>
        </Link>

        <nav
          className="hidden items-center gap-1 lg:flex"
          aria-label="Primary navigation"
        >
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="border-b border-transparent px-2 py-2 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-muted-foreground transition-colors duration-100 hover:border-black hover:text-black"
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
          <div className="absolute right-0 top-12 z-50 w-64 max-w-[calc(100vw-2.5rem)] border-2 border-black bg-white p-2">
            <nav aria-label="Mobile navigation" className="grid gap-1">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="border-b border-border px-3 py-3 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-muted-foreground transition-colors duration-100 hover:bg-black hover:text-white"
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
