"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ListChecks,
  Settings,
  Plus,
  ShieldCheck,
  X,
  Users,
  CreditCard,
  KeyRound,
  BellRing,
  FileCheck,
  Rocket,
} from "lucide-react";

const items = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/monitors", label: "Monitors", icon: ListChecks },
  { href: "/dashboard/onboarding", label: "Onboarding", icon: Rocket },
  { href: "/dashboard/workspaces", label: "Workspaces", icon: Users },
  { href: "/dashboard/billing", label: "Billing", icon: CreditCard },
  { href: "/dashboard/channels", label: "Alert Channels", icon: BellRing },
  { href: "/dashboard/api-keys", label: "API Keys", icon: KeyRound },
  { href: "/dashboard/compliance", label: "Compliance", icon: FileCheck },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex-1 space-y-1 p-3">
      {items.map((item) => {
        const active =
          pathname === item.href ||
          (item.href !== "/dashboard" && pathname.startsWith(item.href));

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
              active
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            <item.icon
              size={17}
              className="shrink-0 transition-transform duration-200 group-hover:scale-105"
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <div className="flex h-16 items-center justify-between border-b border-border px-5">
      <Link href="/dashboard" className="group flex items-center gap-2.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-accent transition-transform duration-200 group-hover:rotate-3">
          <ShieldCheck size={17} />
        </span>
        <span className="font-semibold tracking-tight">Sitemyra</span>
      </Link>
    </div>
  );
}

function AddMonitorButton({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="border-t border-border p-3">
      <Link
        href="/dashboard/monitors/new"
        onClick={onNavigate}
        className="apeiro-btn apeiro-btn-primary w-full"
      >
        <Plus size={16} />
        Add monitor
      </Link>
    </div>
  );
}

export default function Sidebar({
  mobileOpen,
  onClose,
}: {
  mobileOpen: boolean;
  onClose: () => void;
}) {
  return (
    <>
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card lg:flex">
        <Brand />
        <Navigation />
        <AddMonitorButton />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/45 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          <aside className="animate-apeiro-fade-up absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col border-r border-border bg-card shadow-2xl">
            <div className="flex h-16 items-center justify-between border-b border-border pl-5 pr-3">
              <Link
                href="/dashboard"
                onClick={onClose}
                className="flex items-center gap-2.5"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-accent">
                  <ShieldCheck size={17} />
                </span>
                <span className="font-semibold tracking-tight">Sitemyra</span>
              </Link>

              <button
                type="button"
                onClick={onClose}
                aria-label="Close navigation"
                className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                <X size={18} />
              </button>
            </div>

            <Navigation onNavigate={onClose} />
            <AddMonitorButton onNavigate={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}