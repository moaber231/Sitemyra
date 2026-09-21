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
    <div className="border-b border-slate-800/60">
      <div className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            aria-label="Go back"
            className="group inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-900/80 border border-slate-800 text-slate-400 transition-all duration-200 ease-out hover:text-white hover:border-slate-700 hover:bg-slate-800/60 hover:shadow-[0_4px_16px_rgba(0,0,0,0.4)] focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 active:scale-[0.97]"
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
                <ol className="flex min-w-0 items-center gap-1.5 text-[0.8125rem] text-slate-500">
                  <li className="hidden sm:list-item">
                    <span className="transition-colors">Dashboard</span>
                  </li>
                  <li
                    aria-hidden="true"
                    className="hidden sm:list-item"
                  >
                    <ChevronRight
                      size={13}
                      className="text-slate-600"
                    />
                  </li>
                  <li className="min-w-0">
                    <Link
                      href={parentHref}
                      className="inline-block max-w-[12rem] truncate rounded transition-colors duration-200 hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 sm:max-w-[16rem]"
                    >
                      {parentLabel}
                    </Link>
                  </li>
                  <li aria-hidden="true">
                    <ChevronRight
                      size={13}
                      className="shrink-0 text-slate-600"
                    />
                  </li>
                  <li
                    aria-current="page"
                    className="max-w-[12rem] truncate font-medium text-slate-300 sm:max-w-[20rem]"
                  >
                    {title}
                  </li>
                </ol>
              </nav>
            ) : (
              <nav aria-label="Breadcrumb">
                <ol className="hidden items-center gap-1.5 text-[0.8125rem] text-slate-500 sm:flex">
                  <li>
                    <span>Dashboard</span>
                  </li>
                  <li aria-hidden="true">
                    <ChevronRight
                      size={13}
                      className="text-slate-600"
                    />
                  </li>
                  <li
                    aria-current="page"
                    className="font-medium text-slate-300"
                  >
                    {title}
                  </li>
                </ol>
              </nav>
            )}

            <h1 className="mt-0.5 truncate text-xl font-semibold tracking-tight text-slate-100 sm:text-2xl">
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
