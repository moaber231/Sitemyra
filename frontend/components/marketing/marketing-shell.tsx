import type { ReactNode } from "react";

import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

export function MarketingShell({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only absolute left-4 top-4 z-50 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-accent-foreground focus:not-sr-only"
      >
        Skip to main content
      </a>
      <SiteHeader />
      <main id="main-content" className={className}>
        {children}
      </main>
      <SiteFooter />
    </div>
  );
}
