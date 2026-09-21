"use client";

import { useEffect, useState } from "react";
import {
  Camera,
  CheckCircle2,
  DollarSign,
  Globe2,
  Loader2,
  ScanSearch,
  TriangleAlert,
} from "lucide-react";

import {
  getAdvancedConfig,
  updateAdvancedConfig,
  testAdvancedMonitor,
  type AdvancedConfig,
  type AdvancedMode,
} from "@/lib/api/advanced";

interface AdvancedConfigProps {
  monitorId: string;
}

interface ModeMeta {
  value: AdvancedMode;
  label: string;
  description: string;
  icon: typeof Globe2;
}

const MODES: ModeMeta[] = [
  {
    value: "http",
    label: "HTTP",
    description: "Fastest, cheapest",
    icon: Globe2,
  },
  {
    value: "dom",
    label: "DOM",
    description: "Meaningful content changes",
    icon: ScanSearch,
  },
  {
    value: "screenshot",
    label: "Screenshot",
    description: "Visual change detection",
    icon: Camera,
  },
  {
    value: "price",
    label: "Price",
    description: "Track a product price",
    icon: DollarSign,
  },
];

export function AdvancedConfigPanel({
  monitorId,
}: AdvancedConfigProps) {
  const [config, setConfig] = useState<AdvancedConfig>({
    mode: "http",
    selector: "",
    price_selector: "",
    price_currency: "",
    screenshot_threshold: 0.5,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [notice, setNotice] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    const token = sessionStorage.getItem("apeiro_access");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    getAdvancedConfig(token, monitorId)
      .then((data) => {
        setConfig(data);
        setNotice(null);
      })
      .catch((error) => {
        setNotice({
          kind: "error",
          text:
            error instanceof Error
              ? error.message
              : "Unable to load advanced settings.",
        });
      })
      .finally(() => {
        setLoading(false);
      });
  }, [monitorId]);

  async function save() {
    const token = sessionStorage.getItem("apeiro_access");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    setSaving(true);
    setNotice(null);

    try {
      const updated = await updateAdvancedConfig(
        token,
        monitorId,
        config,
      );

      setConfig(updated);
      setNotice({ kind: "success", text: "Advanced settings saved." });
    } catch (error) {
      setNotice({
        kind: "error",
        text:
          error instanceof Error
            ? error.message
            : "Unable to save settings.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function test() {
    const token = sessionStorage.getItem("apeiro_access");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    setTesting(true);
    setNotice(null);

    try {
      const result = await testAdvancedMonitor(token, monitorId);

      setNotice({
        kind: "success",
        text: `Advanced check queued (${result.task_id.slice(0, 8)}…).`,
      });
    } catch (error) {
      setNotice({
        kind: "error",
        text:
          error instanceof Error
            ? error.message
            : "Unable to queue advanced check.",
      });
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <section className="apeiro-card p-6">
        <div className="h-4 w-40 rounded bg-muted" />
        <div className="mt-2 h-6 w-80 max-w-full rounded bg-muted" />

        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div
              key={item}
              className="apeiro-skeleton aspect-[5/3]"
            />
          ))}
        </div>
      </section>
    );
  }

  const needsSelector =
    config.mode === "dom" || config.mode === "screenshot";

  return (
    <section className="apeiro-card overflow-hidden">
      <div className="border-b border-border p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Advanced monitoring
        </p>

        <h2 className="mt-2 text-lg font-semibold">
          Choose how Sitemyra watches this page
        </h2>

        <p className="mt-1 text-sm text-muted-foreground">
          Use lightweight HTTP monitoring by default, or enable DOM,
          screenshot, or price tracking.
        </p>
      </div>

      <div className="space-y-6 bg-background/40 p-6">
        <div>
          <span className="mb-2.5 block text-sm font-medium">
            Monitoring mode
          </span>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {MODES.map((mode) => {
              const Icon = mode.icon;
              const selected = config.mode === mode.value;

              return (
                <button
                  key={mode.value}
                  type="button"
                  onClick={() =>
                    setConfig({ ...config, mode: mode.value })
                  }
                  aria-pressed={selected}
                  className={`apeiro-interactive flex flex-col gap-2 rounded-xl border p-3.5 text-left ${
                    selected
                      ? "border-ring bg-card shadow-[0_0_0_2px_color-mix(in_srgb,var(--ring)_30%,transparent)]"
                      : "border-border bg-card hover:border-ring/60"
                  }`}
                >
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                      selected
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <Icon size={15} />
                  </span>

                  <span>
                    <span className="block text-sm font-semibold">
                      {mode.label}
                    </span>

                    <span className="mt-0.5 block text-xs leading-4 text-muted-foreground">
                      {mode.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {needsSelector && (
          <label className="block">
            <span className="mb-2 block text-sm font-medium">
              CSS selector
            </span>

            <input
              value={config.selector}
              onChange={(event) =>
                setConfig({
                  ...config,
                  selector: event.target.value,
                })
              }
              placeholder="main, .product, #content"
              className="apeiro-input"
            />

            <span className="mt-1.5 block text-xs text-muted-foreground">
              Limit monitoring to the part of the page that matters.
            </span>
          </label>
        )}

        {config.mode === "price" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-medium">
                Price CSS selector
              </span>

              <input
                value={config.price_selector}
                onChange={(event) =>
                  setConfig({
                    ...config,
                    price_selector: event.target.value,
                  })
                }
                placeholder=".price, [data-price]"
                className="apeiro-input"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-medium">
                Currency
              </span>

              <input
                value={config.price_currency}
                onChange={(event) =>
                  setConfig({
                    ...config,
                    price_currency: event.target.value.toUpperCase(),
                  })
                }
                placeholder="EUR"
                maxLength={3}
                className="apeiro-input"
              />
            </label>
          </div>
        )}

        {config.mode === "screenshot" && (
          <label className="block">
            <span className="mb-2 block text-sm font-medium">
              Change threshold — {config.screenshot_threshold}%
            </span>

            <input
              type="range"
              min="0.01"
              max="100"
              step="0.01"
              value={config.screenshot_threshold}
              onChange={(event) =>
                setConfig({
                  ...config,
                  screenshot_threshold: Number(event.target.value),
                })
              }
              className="w-full accent-[var(--primary)]"
            />

            <span className="mt-1.5 block text-xs text-muted-foreground">
              Percentage of changed pixels required to create a visual diff.
            </span>
          </label>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="apeiro-btn apeiro-btn-primary"
          >
            {saving ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <CheckCircle2 size={15} />
            )}
            {saving ? "Saving..." : "Save settings"}
          </button>

          {config.mode !== "http" && (
            <button
              type="button"
              onClick={test}
              disabled={testing}
              className="apeiro-btn apeiro-btn-outline"
            >
              {testing ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <ScanSearch size={15} />
              )}
              {testing ? "Queuing..." : "Run test"}
            </button>
          )}
        </div>

        {notice && (
          <div
            className={`flex items-start gap-2.5 rounded-lg border p-3.5 text-sm ${
              notice.kind === "success"
                ? "border-success/30 bg-success-muted text-success"
                : "border-danger/30 bg-danger-muted text-danger"
            }`}
          >
            {notice.kind === "success" ? (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
            ) : (
              <TriangleAlert size={16} className="mt-0.5 shrink-0" />
            )}
            <span>{notice.text}</span>
          </div>
        )}
      </div>
    </section>
  );
}

export default AdvancedConfigPanel;