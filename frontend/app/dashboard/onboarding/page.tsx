"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Globe, Cpu, BellRing, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { createMonitor } from "@/lib/api/monitors";
import { createChannel } from "@/lib/api/ops";
import { getOnboarding, updateOnboarding } from "@/lib/api/developer";

const ENGINES = [
  { id: "http", label: "HTTP", hint: "Fast content-hash checks" },
  { id: "visual", label: "Visual", hint: "Screenshot diffing" },
  {
    id: "price",
    label: "Price",
    hint: "Track prices & drift — best for pricing pages",
  },
];

function token() {
  return sessionStorage.getItem("apeiro_access") ?? "";
}

export default function OnboardingPage() {
  const [step, setStep] = useState(1);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [engine, setEngine] = useState("http");
  const [webhook, setWebhook] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token()) {
      window.location.href = "/login";
      return;
    }
    getOnboarding()
      .then((o) => {
        setStep(o.completed ? 4 : Math.min(Math.max(o.step, 1), 3));
        if (o.completed) setDone(true);
        if (o.engine) setEngine(o.engine);
      })
      .catch(() => undefined);
  }, []);

  async function stepOne() {
    if (!url.trim() || !name.trim()) {
      toast.error("Give your monitor a name and URL.");
      return;
    }
    setBusy(true);
    try {
      const monitor = await createMonitor(token(), {
        name: name.trim(),
        url: url.trim(),
        check_interval: 300,
        timeout: 15,
      });
      await updateOnboarding({
        step: 2,
        first_monitor_id: monitor.id,
      });
      setStep(2);
      toast.success("First URL added.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not add URL.");
    } finally {
      setBusy(false);
    }
  }

  async function stepTwo() {
    setBusy(true);
    try {
      await updateOnboarding({ step: 3, engine });
      setStep(3);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save engine.");
    } finally {
      setBusy(false);
    }
  }

  async function stepThree(skip = false) {
    setBusy(true);
    try {
      if (!skip && webhook.trim()) {
        await createChannel({
          channel_type: webhook.includes("discord") ? "discord" : "slack",
          name: "Onboarding webhook",
          config: webhook.trim(),
        });
      }
      await updateOnboarding({
        step: 4,
        completed: true,
        webhook_configured: !skip && Boolean(webhook.trim()),
      });
      setDone(true);
      setStep(4);
      toast.success("Onboarding complete. Happy monitoring!");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not finish.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl py-8">
        <p className="text-sm font-semibold text-success">
          Zero-to-touch onboarding
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          Catch your first price change in 3 steps
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Point Apeiro at a competitor pricing page, pick price tracking,
          and get a Slack or email alert the instant it moves.
        </p>
        <Steps current={done ? 4 : step} />

        {!done && step === 1 && (
          <div className="apeiro-card mt-6 space-y-4 p-6">
            <h2 className="flex items-center gap-2 font-semibold">
              <Globe size={17} /> Step 1 — Add your first URL
            </h2>
            <label className="block">
              <span className="mb-2 block text-sm font-medium">Name</span>
              <input
                className="apeiro-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Competitor pricing"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-medium">URL</span>
              <input
                className="apeiro-input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://competitor.com/pricing"
              />
              <span className="mt-1.5 block text-xs text-muted-foreground">
                Works best on pricing and product pages you want to watch.
              </span>
            </label>
            <button
              onClick={stepOne}
              disabled={busy}
              className="apeiro-btn apeiro-btn-primary w-full"
            >
              {busy ? <Loader2 size={16} className="animate-spin" /> : null}
              Continue
            </button>
          </div>
        )}

        {!done && step === 2 && (
          <div className="apeiro-card mt-6 space-y-4 p-6">
            <h2 className="flex items-center gap-2 font-semibold">
              <Cpu size={17} /> Step 2 — Choose monitoring engine
            </h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {ENGINES.map((e) => (
                <button
                  key={e.id}
                  onClick={() => setEngine(e.id)}
                  className={`rounded-xl border p-4 text-left transition ${
                    engine === e.id
                      ? "border-accent bg-accent/10"
                      : "border-border hover:bg-muted"
                  }`}
                >
                  <p className="font-semibold">{e.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{e.hint}</p>
                </button>
              ))}
            </div>
            <button
              onClick={stepTwo}
              disabled={busy}
              className="apeiro-btn apeiro-btn-primary w-full"
            >
              Continue
            </button>
          </div>
        )}

        {!done && step === 3 && (
          <div className="apeiro-card mt-6 space-y-4 p-6">
            <h2 className="flex items-center gap-2 font-semibold">
              <BellRing size={17} /> Step 3 — Set alert webhook
            </h2>
            <label className="block">
              <span className="mb-2 block text-sm font-medium">
                Slack / Discord webhook URL
              </span>
              <input
                className="apeiro-input"
                value={webhook}
                onChange={(e) => setWebhook(e.target.value)}
                placeholder="https://hooks.slack.com/..."
              />
              <span className="mt-1.5 block text-xs text-muted-foreground">
                Works with Slack, Discord, or any generic webhook. Email
                alerts are on by default — manage them in Settings.
              </span>
            </label>
            <div className="flex gap-3">
              <button
                onClick={() => stepThree(false)}
                disabled={busy}
                className="apeiro-btn apeiro-btn-primary flex-1"
              >
                Save & finish
              </button>
              <button
                onClick={() => stepThree(true)}
                disabled={busy}
                className="apeiro-btn apeiro-btn-ghost flex-1"
              >
                Skip for now
              </button>
            </div>
          </div>
        )}

        {done && (
          <div className="apeiro-card mt-6 p-8 text-center">
            <CheckCircle2 size={32} className="mx-auto text-success" />
            <h2 className="mt-3 font-semibold">You are all set!</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Your first monitor is running. You&apos;ll get a Slack or
              email alert the moment the price or content moves — plus a
              weekly digest every Monday.
            </p>
            <a
              href="/dashboard"
              className="apeiro-btn apeiro-btn-primary mt-5"
            >
              Go to dashboard
            </a>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function Steps({ current }: { current: number }) {
  const labels = ["Add URL", "Engine", "Webhook"];
  return (
    <div className="mt-5 flex gap-2">
      {labels.map((label, i) => {
        const n = i + 1;
        const active = current === n;
        const past = current > n;
        return (
          <div
            key={label}
            className={`flex-1 rounded-xl border px-3 py-2 text-xs font-medium ${
              past
                ? "border-success/40 bg-success-muted text-success"
                : active
                  ? "border-accent bg-accent/10"
                  : "border-border text-muted-foreground"
            }`}
          >
            Step {n} — {label}
          </div>
        );
      })}
    </div>
  );
}
