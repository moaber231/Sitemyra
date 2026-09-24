"use client";

import React from "react";
import { ArrowLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface DashboardHeaderProps {
  title: string;
  parentHref?: string;
  parentLabel?: string;
  children?: React.ReactNode;
}

export function DashboardHeader({
  title,
  parentHref,
  parentLabel,
  children,
}: DashboardHeaderProps) {
  const router = useRouter();

  return (
    <div className="dashboard-header border-b border-border/80">
      <div className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            aria-label="Go back"
            className="group inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/30 hover:bg-accent/5 hover:text-accent hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 active:scale-[0.97]"
          >
            <ArrowLeft
              size={17}
              aria-hidden="true"
              className="transition-transform duration-200 group-hover:-translate-x-0.5"
            />
          </button>

          <div className="min-w-0">
            {parentHref && parentLabel ? (
              <nav aria-label="Breadcrumb">
                <ol className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
                  <li className="hidden sm:list-item">Dashboard</li>
                  <li aria-hidden="true" className="hidden sm:list-item">
                    <ChevronRight size={13} aria-hidden="true" />
                  </li>
                  <li className="min-w-0">
                    <Link
                      href={parentHref}
                      className="inline-block max-w-[12rem] truncate rounded transition-colors duration-200 hover:text-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent sm:max-w-[16rem]"
                    >
                      {parentLabel}
                    </Link>
                  </li>
                  <li aria-hidden="true">
                    <ChevronRight size={13} aria-hidden="true" />
                  </li>
                  <li
                    aria-current="page"
                    className="max-w-[12rem] truncate font-medium text-foreground sm:max-w-[20rem]"
                  >
                    {title}
                  </li>
                </ol>
              </nav>
            ) : (
              <nav aria-label="Breadcrumb">
                <ol className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
                  <li>Dashboard</li>
                  <li aria-hidden="true">
                    <ChevronRight size={13} aria-hidden="true" />
                  </li>
                  <li aria-current="page" className="font-medium text-foreground">
                    {title}
                  </li>
                </ol>
              </nav>
            )}

            <h1 className="mt-1 truncate text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {title}
            </h1>
          </div>
        </div>

        {children && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {children}
          </div>
        )}
      </div>
    </div>
  );
}

export default DashboardHeader;
