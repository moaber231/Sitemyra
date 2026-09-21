"use client";

import { useEffect, useState } from "react";
import { CreditCard, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import {
  createCheckout,
  createPortalSession,
  getPlans,
  getSubscription,
  type Plan,
  type Subscription,
} from "@/lib/api/billing";

export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [billingConfigured, setBillingConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionStorage.getItem("apeiro_access")) {
      window.location.href = "/login";
      return;
    }
    Promise.all([getPlans(), getSubscription()])
      .then(([p, s]) => {
        setPlans(p.plans);
        setSub(s);
        setBillingConfigured(
          (p as { billing_configured?: boolean }).billing_configured !== false &&
            (s as { billing_configured?: boolean }).billing_configured !==
              false,
        );
        const params = new URLSearchParams(window.location.search);
        const result = params.get("checkout");
        if (result === "success") {
          toast.success("Checkout complete. Your plan is now active.");
          window.history.replaceState({}, "", window.location.pathname);
        } else if (result === "cancelled") {
          toast.error("Checkout was cancelled. No charge was made.");
          window.history.replaceState({}, "", window.location.pathname);
        }
      })
      .catch((e) =>
        toast.error(e instanceof Error ? e.message : "Billing unavailable."),
      )
      .finally(() => setLoading(false));
  }, []);

  async function checkout(plan: "pro" | "business") {
    setBusy(plan);
    try {
      const res = await createCheckout(plan);
      if ((res as { stub?: boolean }).stub) {
        // Should only happen with the explicit dev stub; never in prod.
        toast.error(
          "Billing is not configured. Checkout is unavailable.",
        );
        return;
      }
      window.location.href = res.checkout_url;
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Checkout unavailable.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function portal() {
    try {
      const res = await createPortalSession();
      if ((res as { stub?: boolean }).stub) {
        toast.error("Billing is not configured. Portal is unavailable.");
        return;
      }
      window.location.href = res.portal_url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Portal unavailable.");
    }
  }

  if (loading)
    return (
      <AppShell>
        <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" /> Loading billing…
        </div>
      </AppShell>
    );

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl py-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <CreditCard size={22} /> Billing & Usage
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Current plan: <strong>{sub?.plan}</strong> ({sub?.status}) ·
          Limits: {sub?.limits.max_monitors} URLs, min interval{" "}
          {sub?.limits.min_interval_seconds}s, {sub?.limits.max_alert_channels}{" "}
          alert channel(s). Failed payments enter dunning (past_due) with a
          grace period; canceled subscriptions downgrade gracefully to Free.
        </p>
        {!billingConfigured && (
          <p className="mt-3 rounded-lg border border-border bg-muted p-3 text-sm text-muted-foreground">
            Billing is not configured on this server. Upgrades and the
            customer portal are disabled until the administrator sets Stripe
            keys.
          </p>
        )}

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {plans.map((p) => {
            const current = sub?.plan === p.id;
            return (
              <div
                key={p.id}
                className={`apeiro-card p-5 ${current ? "border-accent" : ""}`}
              >
                <h2 className="font-semibold">
                  {p.name}{" "}
                  {current && (
                    <span className="ml-1 rounded-full bg-success-muted px-2 py-0.5 text-xs text-success">
                      current
                    </span>
                  )}
                </h2>
                <p className="mt-1 text-2xl font-semibold">
                  ${(p.mrr_cents / 100).toFixed(0)}
                  <span className="text-sm font-normal text-muted-foreground">
                    /mo
                  </span>
                </p>
                <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                  <li>{p.max_monitors} active URLs</li>
                  <li>Min interval {p.min_interval_seconds}s</li>
                  <li>{p.max_alert_channels} alert channels</li>
                  <li>{p.history_days}d history</li>
                </ul>
                {p.id !== "free" && !current && (
                  <button
                    onClick={() => checkout(p.id as "pro" | "business")}
                    disabled={busy !== null || !billingConfigured}
                    title={
                      billingConfigured
                        ? undefined
                        : "Billing is not configured"
                    }
                    className="apeiro-btn apeiro-btn-primary mt-4 w-full"
                  >
                    {busy === p.id ? (
                      <Loader2 size={15} className="animate-spin" />
                    ) : null}
                    Upgrade to {p.name}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <button
          onClick={portal}
          disabled={!billingConfigured}
          title={billingConfigured ? undefined : "Billing is not configured"}
          className="apeiro-btn apeiro-btn-ghost mt-6"
        >
          Open Stripe Customer Portal
        </button>
      </div>
    </AppShell>
  );
}
