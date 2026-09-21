"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Globe2, Loader2, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { createMonitor } from "@/lib/api/monitors";

export default function NewMonitorPage() {
  const router = useRouter();

  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [interval, setInterval] = useState("300");
  const [timeout, setTimeoutValue] = useState("10");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isValidUrl =
    url.startsWith("http://") || url.startsWith("https://");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!name.trim() || !isValidUrl) {
      return;
    }

    const accessToken = sessionStorage.getItem("apeiro_access");

    if (!accessToken) {
      router.push("/login");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const monitor = await createMonitor(accessToken, {
        name: name.trim(),
        url: url.trim(),
        check_interval: Number(interval),
        timeout: Number(timeout),
      });

      router.push(`/dashboard/monitors/${monitor.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create monitor.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="relative mx-auto max-w-3xl px-0 py-2 lg:py-4">
        <div
          aria-hidden="true"
          className="absolute -z-10 left-1/2 top-0 h-72 w-72 -translate-x-1/2 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none"
        />

        <div className="apeiro-stagger stagger-1">
          <DashboardHeader
            title="New Monitor"
            parentHref="/dashboard/monitors"
            parentLabel="Monitors"
          />
        </div>

        <div className="apeiro-stagger stagger-2 mt-6 mb-6">
          <p className="text-sm leading-6 text-slate-400">
            Tell Sitemyra which page you want to watch. Checks run
            automatically on your chosen interval.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="apeiro-glass apeiro-stagger stagger-3 overflow-hidden"
        >
          <div className="space-y-6 p-6">
            <div>
              <label
                htmlFor="name"
                className="mb-2 block text-sm font-medium text-slate-200"
              >
                Monitor name
              </label>

              <input
                id="name"
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="My website"
                autoComplete="off"
                className="apeiro-input"
              />

              <p className="mt-1.5 text-xs text-slate-400">
                A name that helps you identify this monitor.
              </p>
            </div>

            <div>
              <label
                htmlFor="url"
                className="mb-2 block text-sm font-medium text-slate-200"
              >
                URL
              </label>

              <div className="relative">
                <Globe2
                  size={17}
                  aria-hidden="true"
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
                />

                <input
                  id="url"
                  type="url"
                  required
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://example.com"
                  inputMode="url"
                  autoComplete="url"
                  aria-invalid={url ? !isValidUrl : undefined}
                  aria-describedby={url && !isValidUrl ? "url-error" : undefined}
                  className="apeiro-input !pl-9"
                />
              </div>

              {url && !isValidUrl && (
                <p id="url-error" className="mt-1.5 text-xs text-red-300">
                  Enter a valid HTTP or HTTPS URL.
                </p>
              )}
            </div>

            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="interval"
                  className="mb-2 block text-sm font-medium text-slate-200"
                >
                  Check interval
                </label>

                <select
                  id="interval"
                  value={interval}
                  onChange={(event) => setInterval(event.target.value)}
                  className="apeiro-input"
                >
                  <option value="300">Every 5 minutes</option>
                  <option value="900">Every 15 minutes</option>
                  <option value="1800">Every 30 minutes</option>
                  <option value="3600">Every hour</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="timeout"
                  className="mb-2 block text-sm font-medium text-slate-200"
                >
                  Request timeout
                </label>

                <select
                  id="timeout"
                  value={timeout}
                  onChange={(event) => setTimeoutValue(event.target.value)}
                  className="apeiro-input"
                >
                  <option value="5">5 seconds</option>
                  <option value="10">10 seconds</option>
                  <option value="30">30 seconds</option>
                  <option value="60">60 seconds</option>
                  <option value="120">120 seconds</option>
                </select>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3.5 py-3 text-sm text-red-200"
              >
                <span>{error}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col-reverse items-stretch justify-end gap-2 border-t border-slate-800/60 bg-slate-950/40 px-6 py-4 sm:flex-row sm:items-center">
            <Link
              href="/dashboard/monitors"
              className="apeiro-btn apeiro-btn-ghost"
            >
              Cancel
            </Link>

            <button
              type="submit"
              disabled={loading || !name.trim() || !isValidUrl}
              className="apeiro-btn apeiro-btn-primary min-w-[10rem]"
            >
              {loading ? (
                <Loader2
                  size={16}
                  aria-hidden="true"
                  className="animate-spin"
                />
              ) : (
                <Save size={16} aria-hidden="true" />
              )}

              {loading ? "Creating..." : "Create monitor"}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
