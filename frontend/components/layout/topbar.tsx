"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, Plus, ShieldCheck } from "lucide-react";
import { AccountMenu } from "./account-menu";

export default function Topbar({
  onMenuClick,
}: {
  onMenuClick: () => void;
}) {
  const pathname = usePathname();

  const title =
    pathname === "/dashboard"
      ? "Overview"
      : pathname === "/dashboard/monitors"
        ? "Monitors"
        : pathname.startsWith("/dashboard/monitors/new")
          ? "New monitor"
          : pathname.startsWith("/dashboard/monitors/")
            ? "Monitor"
            : pathname.startsWith("/dashboard/settings")
              ? "Settings"
              : "Dashboard";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-card/90 px-4 backdrop-blur-md sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="rounded-lg p-2 text-muted-foreground transition hover:bg-muted hover:text-foreground lg:hidden"
        >
          <Menu size={19} />
        </button>

        <div className="flex shrink-0 items-center gap-2 lg:hidden">
          <ShieldCheck size={18} className="text-accent-foreground" />
          <span className="font-semibold">Sitemyra</span>
        </div>

        <h1 className="hidden truncate text-sm font-semibold sm:block">
          {title}
        </h1>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <Link
          href="/dashboard/monitors/new"
          className="apeiro-btn apeiro-btn-primary hidden sm:inline-flex"
        >
          <Plus size={15} />
          Add monitor
        </Link>

        <Link
          href="/dashboard/monitors/new"
          aria-label="Add monitor"
          className="apeiro-btn apeiro-btn-primary sm:hidden"
        >
          <Plus size={16} />
        </Link>

        <AccountMenu />
      </div>
    </header>
  );
}