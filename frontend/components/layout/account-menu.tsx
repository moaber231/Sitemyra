"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, LogOut, User } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getMe } from "@/lib/api/auth";

function initialFromEmail(email: string) {
  return email.charAt(0).toUpperCase();
}

export function AccountMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: user } = useQuery({
    queryKey: ["me"],
    queryFn: () => {
      const token = sessionStorage.getItem("apeiro_access");

      if (!token) {
        return Promise.reject(new Error("Authentication required."));
      }

      return getMe(token);
    },
    staleTime: 5 * 60_000,
    retry: 0,
  });

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  function logout() {
    sessionStorage.removeItem("apeiro_access");
    sessionStorage.removeItem("apeiro_refresh");
    window.location.href = "/login";
  }

  const initial = user ? initialFromEmail(user.email) : "A";

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label="Account menu"
        aria-expanded={open}
        className="flex h-9 items-center gap-2 rounded-full border border-border bg-muted pl-1.5 pr-2 transition hover:border-ring/60"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
          {initial}
        </span>

        <ChevronDown
          size={14}
          className={`text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="animate-apeiro-pop absolute right-0 top-11 z-50 w-60 rounded-xl border border-border bg-card p-1.5 shadow-xl">
          <div className="border-b border-border px-3 py-2.5">
            <p className="truncate text-sm font-medium text-foreground">
              {user?.email ?? "Loading account…"}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {user
                ? `Member since ${new Date(
                    user.created_at,
                  ).toLocaleDateString()}`
                : "Signed in"}
            </p>
          </div>

          <Link
            href="/dashboard/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm transition hover:bg-muted"
          >
            <User size={16} />
            Account settings
          </Link>

          <div className="my-1 border-t border-border" />

          <button
            type="button"
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm text-danger transition hover:bg-danger-muted"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}