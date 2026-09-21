"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { register } from "@/lib/api/auth";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    try {
      const result = await register(email, password);
      sessionStorage.setItem("apeiro_access", result.access);
      sessionStorage.setItem("apeiro_refresh", result.refresh);
      window.location.href = "/dashboard";
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to create account.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto grid min-h-screen max-w-7xl lg:grid-cols-2">
        <div className="relative hidden overflow-hidden bg-[#0e1310] p-12 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="pointer-events-none absolute -left-24 top-1/3 h-80 w-80 rounded-full bg-accent opacity-10 blur-3xl" />

          <Link href="/" className="relative flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-accent">
              <ShieldCheck size={19} />
            </span>
            <span className="font-semibold">Sitemyra</span>
          </Link>

          <div className="relative max-w-md">
            <p className="text-sm font-medium text-accent">
              Start in minutes
            </p>

            <h2 className="mt-3 text-4xl font-semibold tracking-tight">
              Put your important pages on autopilot.
            </h2>

            <div className="mt-8 space-y-4">
              {[
                "Monitor important URLs",
                "Detect content changes",
                "Get email alerts",
              ].map((item) => (
                <div
                  key={item}
                  className="flex items-center gap-3 text-sm text-white/75"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-[#131a10]">
                    <Check size={14} />
                  </span>
                  {item}
                </div>
              ))}
            </div>
          </div>

          <p className="relative text-xs text-white/40">
            Your monitoring, without the busywork.
          </p>
        </div>

        <div className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
          <div className="w-full max-w-md animate-apeiro-fade-up">
            <Link
              href="/"
              className="mb-10 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition hover:text-foreground lg:hidden"
            >
              <ArrowLeft size={15} />
              Back to Sitemyra
            </Link>

            <div className="mb-8">
              <p className="text-sm font-semibold text-success">
                Get started
              </p>

              <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                Create your Sitemyra account.
              </h1>

              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Start monitoring the pages you care about.
              </p>
            </div>

            <div className="apeiro-card p-6 sm:p-8">
              <form onSubmit={handleSubmit} className="space-y-5">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium">
                    Email
                  </span>

                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    required
                    className="apeiro-input"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium">
                    Password
                  </span>

                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="At least 8 characters"
                    minLength={8}
                    required
                    className="apeiro-input"
                  />
                </label>

                <button
                  type="submit"
                  disabled={loading}
                  className="apeiro-btn apeiro-btn-primary w-full !py-3"
                >
                  {loading ? (
                    <>
                      <Loader2 size={17} className="animate-spin" />
                      Creating account...
                    </>
                  ) : (
                    <>
                      Create free account
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </form>
            </div>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link
                href="/login"
                className="font-semibold text-foreground hover:underline"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}