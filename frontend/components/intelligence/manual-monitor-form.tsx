"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Globe2, Loader2, Save } from "lucide-react";
import { toast } from "sonner";

import { createMonitor } from "@/lib/api/monitors";

const INTERVALS = [
  { value: "300", label: "Every 5 minutes" },
  { value: "900", label: "Every 15 minutes" },
  { value: "1800", label: "Every 30 minutes" },
  { value: "3600", label: "Every hour" },
];

const TIMEOUTS = [5, 10, 30, 60, 120];

/**
 * The original manual monitor form, kept intact.
 *
 * The URL intake flow is now the default, but nothing is lost: advanced
 * users (and the existing onboarding flow) still get name, interval and
 * timeout control here.
 */
export function ManualMonitorForm({ initialUrl = "" }: { initialUrl?: string }) {
  const router = useRouter();
  const [url, setUrl] = useState(initialUrl);
  const [name, setName] = useState("");
  const [interval, setInterval] = useState("300");
  const [timeout, setTimeoutValue] = useState("10");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isValidUrl = url.startsWith("http://") || url.startsWith("https://");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !isValidUrl) return;
    setLoading(true);
    setError("");

    const accessToken = sessionStorage.getItem("apeiro_access");
    if (!accessToken) {
      router.push("/login");
      return;
    }

    try {
      const monitor = await createMonitor(accessToken, {
        name: name.trim(),
        url: url.trim(),
        check_interval: Number(interval),
        timeout: Number(timeout),
      });
      toast.success("Monitor created.");
      router.push(`/dashboard/monitors/${monitor.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create monitor.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="apeiro-glass overflow-hidden">
      <div className="space-y-6 p-6">
        <div>
          <label htmlFor="manual-name" className="mb-2 block text-sm font-medium text-foreground">
            Monitor name
          </label>
          <input
            id="manual-name"
            name="name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="off"
            placeholder="My website"
            className="apeiro-input"
          />
          <p className="mt-1.5 text-xs text-muted-foreground">
            How this page will be named in your dashboard and alerts.
          </p>
        </div>

        <div>
          <label htmlFor="manual-url" className="mb-2 block text-sm font-medium text-foreground">
            Page URL
          </label>
          <div className="relative">
            <Globe2
              size={17}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              id="manual-url"
              name="url"
              type="url"
              inputMode="url"
              autoComplete="url"
              required
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com/pricing"
              aria-invalid={url ? !isValidUrl : undefined}
              aria-describedby={url && !isValidUrl ? "manual-url-error" : undefined}
              className="apeiro-input !pl-9"
            />
          </div>
          {url && !isValidUrl ? (
            <p id="manual-url-error" className="mt-1.5 text-xs text-danger">
              Enter a full http:// or https:// URL.
            </p>
          ) : null}
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <label htmlFor="manual-interval" className="mb-2 block text-sm font-medium text-foreground">
              Check frequency
            </label>
            <select
              id="manual-interval"
              name="check_interval"
              value={interval}
              onChange={(event) => setInterval(event.target.value)}
              className="apeiro-input"
            >
              {INTERVALS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="manual-timeout" className="mb-2 block text-sm font-medium text-foreground">
              Timeout (seconds)
            </label>
            <select
              id="manual-timeout"
              name="timeout"
              value={timeout}
              onChange={(event) => setTimeoutValue(event.target.value)}
              className="apeiro-input"
            >
              {TIMEOUTS.map((option) => (
                <option key={option} value={option}>
                  {option} seconds
                </option>
              ))}
            </select>
          </div>
        </div>

        {error ? (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger-muted px-3.5 py-3 text-sm text-danger"
          >
            <span>{error}</span>
          </div>
        ) : null}
      </div>

      <div className="flex flex-col-reverse items-stretch justify-end gap-2 border-t border-border bg-muted/30 px-6 py-4 sm:flex-row sm:items-center">
        <Link href="/dashboard/monitors" className="apeiro-btn apeiro-btn-ghost">
          Cancel
        </Link>
        <button
          type="submit"
          disabled={loading || !name.trim() || !isValidUrl}
          className="apeiro-btn apeiro-btn-primary min-w-[10rem]"
        >
          {loading ? (
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          ) : (
            <Save size={16} aria-hidden="true" />
          )}
          {loading ? "Creating…" : "Create monitor"}
        </button>
      </div>
    </form>
  );
}
