"use client";

import React from "react";
import { Loader2 } from "lucide-react";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "ghost"
  | "danger"
  | "accent";

export type ButtonSize = "sm" | "md" | "lg" | "icon";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const buttonBase =
  "relative inline-flex items-center justify-center font-medium transition-all duration-200 ease-out rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 text-white border border-indigo-400/20 shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:from-indigo-500 hover:to-violet-500 hover:shadow-[0_0_25px_rgba(99,102,241,0.5)] hover:-translate-y-px",
  secondary:
    "bg-slate-900/80 hover:bg-slate-800/80 text-slate-200 hover:text-white border border-slate-800 backdrop-blur-md active:bg-slate-800/90",
  outline:
    "border border-slate-800 hover:border-slate-700 bg-transparent text-slate-300 hover:text-white hover:bg-slate-800/50",
  ghost:
    "border border-transparent text-slate-400 hover:text-slate-100 hover:bg-slate-800/60",
  danger:
    "border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 hover:text-red-200 hover:border-red-500/40",
  accent:
    "bg-[var(--accent)] text-[var(--accent-foreground)] hover:shadow-[0_7px_22px_color-mix(in_srgb,var(--accent)_32%,transparent)] hover:-translate-y-px",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 px-3 text-[0.8125rem]",
  md: "h-10 gap-2 px-4 text-sm",
  lg: "h-11 gap-2 px-5 text-sm",
  icon: "h-10 w-10 gap-0",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className = "",
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={`${buttonBase} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`.trim()}
      {...rest}
    >
      {loading && (
        <Loader2 size={15} aria-hidden="true" className="animate-spin" />
      )}
      {children}
    </button>
  );
}

export default Button;
