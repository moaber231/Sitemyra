"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

interface BackButtonProps {
  href: string;
  label?: string;
  className?: string;
}

export function BackButton({
  href,
  label = "Back",
  className,
}: BackButtonProps) {
  return (
    <Link
      href={href}
      aria-label={label}
      className={`group inline-flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-400 transition-colors duration-200 hover:bg-slate-800/80 hover:text-slate-100 ${
        className ?? ""
      }`}
    >
      <ArrowLeft
        size={16}
        aria-hidden="true"
        className="shrink-0 transition-transform duration-200 group-hover:-translate-x-0.5"
      />
      {label}
    </Link>
  );
}

export default BackButton;