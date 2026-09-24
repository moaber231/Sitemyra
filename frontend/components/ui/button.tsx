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
  "relative inline-flex items-center justify-center rounded-xl font-semibold transition-all duration-200 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "border border-accent/20 bg-gradient-to-br from-accent to-accent-secondary text-white shadow-[0_8px_24px_rgb(0_82_255_/_0.22)] hover:-translate-y-0.5 hover:shadow-[0_14px_34px_rgb(0_82_255_/_0.3)]",
  secondary:
    "border border-border bg-muted text-foreground shadow-sm hover:-translate-y-0.5 hover:border-accent/25 hover:bg-accent/5 hover:shadow-md",
  outline:
    "border border-border bg-transparent text-foreground hover:-translate-y-0.5 hover:border-accent/30 hover:bg-accent/5 hover:text-accent hover:shadow-sm",
  ghost:
    "border border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
  danger:
    "border border-danger/25 bg-danger-muted text-danger hover:-translate-y-0.5 hover:border-danger/40 hover:bg-danger/15",
  accent:
    "border border-accent/20 bg-accent text-accent-foreground shadow-[0_8px_24px_rgb(0_82_255_/_0.22)] hover:-translate-y-0.5 hover:shadow-[0_14px_34px_rgb(0_82_255_/_0.3)]",
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
