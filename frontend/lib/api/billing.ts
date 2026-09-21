import { apiFetch } from "./client";

export type Plan = {
  id: string;
  name: string;
  mrr_cents: number;
  max_monitors: number;
  min_interval_seconds: number;
  max_alert_channels: number;
  history_days: number;
};

export type Subscription = {
  plan: string;
  status: string;
  mrr_cents: number;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  limits: {
    max_monitors: number;
    min_interval_seconds: number;
    max_alert_channels: number;
    history_days: number;
  };
  stripe_customer_id: string;
};

export function getPlans() {
  return apiFetch<{ current_plan: string; plans: Plan[] }>(
    "/api/billing/plans/",
  );
}

export function getSubscription() {
  return apiFetch<Subscription>("/api/billing/subscription/");
}

export function createCheckout(plan: "pro" | "business") {
  return apiFetch<{ checkout_url: string; stub: boolean; plan?: string }>(
    "/api/billing/checkout/",
    { method: "POST", body: JSON.stringify({ plan }) },
  );
}

export function createPortalSession() {
  return apiFetch<{ portal_url: string; stub: boolean }>(
    "/api/billing/portal/",
    { method: "POST" },
  );
}
