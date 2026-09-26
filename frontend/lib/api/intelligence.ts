import { apiFetch } from "@/lib/api/client";

/* ------------------------------------------------------------------ *
 * Types
 * ------------------------------------------------------------------ */

export type PageKind =
  | "product"
  | "pricing"
  | "features"
  | "variants"
  | "reviews"
  | "faq"
  | "docs"
  | "changelog"
  | "blog"
  | "careers"
  | "promotions"
  | "homepage"
  | "legal"
  | "support"
  | "other";

export type Confidence = "high" | "medium" | "low";

export type DiscoveredTarget = {
  id: string;
  url: string;
  kind: PageKind;
  kind_label: string;
  label: string;
  why: string;
  confidence: Confidence;
  relevance: number;
  is_product: boolean;
  is_primary: boolean;
};

export type UrlAnalysis = {
  id: string;
  url: string;
  status: string;
  page_kind: PageKind;
  page_kind_label: string;
  classification_confidence: Confidence;
  classification_rationale: string;
  product_detected: boolean;
  facts: Record<string, { value: unknown; method: string; raw: string }>;
  summary: Record<string, unknown>;
  status_code: number | null;
  response_time_ms: number | null;
  fetched_at: string;
  expires_at: string;
  targets: DiscoveredTarget[];
  target_count: number;
  found_count: number;
  cached?: boolean;
};

export type ProductSnapshot = {
  id: string;
  product_watch: string;
  monitor_check: string | null;
  captured_at: string;
  name: string;
  brand: string;
  sku: string;
  price: string | null;
  list_price: string | null;
  discount_percent: number | null;
  currency: string;
  availability: string;
  availability_label: string;
  condition: string;
  rating: string | null;
  review_count: number | null;
  description: string;
  badges: string[];
  variants: { label?: string; price?: string; currency?: string }[];
  images: string[];
  bundles: string[];
  specs: Record<string, string>;
  shipping: Record<string, string>;
  source_url: string;
  extraction: Record<string, string>;
  evidence: Record<string, string>;
  changed_fields: string[];
};

export type Severity = "informational" | "minor" | "important" | "critical";

export type ProductChange = {
  id: string;
  product_watch: string;
  previous_snapshot: string | null;
  current_snapshot: string | null;
  monitor_check: string | null;
  field: string;
  label: string;
  before: string;
  after: string;
  severity: Severity;
  severity_label: string;
  category: string;
  category_label: string;
  basis: string;
  rule: string;
  evidence: Record<string, unknown>;
  source_url: string;
  created_at: string;
  summary_line: string;
};

export type ProductWatch = {
  id: string;
  monitor: string;
  monitor_name: string;
  monitor_url: string;
  name: string;
  brand: string;
  currency: string;
  product_detected: boolean;
  detection_note: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  created_at: string;
  latest_snapshot: ProductSnapshot | null;
  change_count: number;
  latest_severity: Severity | "";
};

export type ChangeEvidence = {
  field: string;
  label: string;
  before: string;
  after: string;
  severity: Severity;
  category: string;
  rule: string;
  basis: string;
  source_url?: string;
  detected_at?: string;
};

export type Explanation = {
  what_changed: string;
  why_it_may_matter: string;
  what_to_check: string;
  confidence: Confidence;
  basis: string[];
  evidence: ChangeEvidence[];
};

export type ProductWatchDetail = {
  product_watch: ProductWatch;
  current_snapshot: ProductSnapshot | null;
  changes: ProductChange[];
  explanation: Explanation;
  source_url: string;
};

export type MonitorProduct = {
  monitor_id: string;
  product_watch: ProductWatch;
  current_snapshot: ProductSnapshot | null;
  changes: ProductChange[];
  explanation: Explanation;
};

export type Recipe = {
  slug: string;
  name: string;
  description: string;
  check_interval: number;
  product_watch: boolean;
  target_kinds: PageKind[];
};

export type ActivationResult = {
  monitors: { id: string; name: string; url: string; check_interval: number }[];
  product_watches: ProductWatch[];
  created: number;
  skipped: { url: string; label: string; reason: string; monitor_id?: string }[];
  limit_reached: boolean;
  plan: string;
  plan_limit: number | null;
  check_interval: number | null;
  recipe: string;
  published_first_checks: number;
  selected_targets?: DiscoveredTarget[];
  detail?: string;
};

export type QuickMonitorResult = {
  analysis_id: string;
  monitor_id?: string;
  monitors: { id: string; name: string; url: string }[];
  product_watches: ProductWatch[];
  created: number;
  skipped: ActivationResult["skipped"];
  plan: string;
  plan_limit: number | null;
  product_detected: boolean;
  page_kind: PageKind;
  detail?: string;
};

export type PublicAnalysis = {
  url: string;
  page_kind: PageKind;
  page_kind_label: string;
  classification_confidence: Confidence;
  classification_rationale: string;
  product_detected: boolean;
  facts: Record<string, unknown>;
  found_count: number;
  targets: { kind: PageKind; label: string; url: string; relevance: number }[];
  sign_in_url: string;
};

/* ------------------------------------------------------------------ *
 * Client
 * ------------------------------------------------------------------ */

export function analyzeUrl(url: string): Promise<UrlAnalysis> {
  return apiFetch<UrlAnalysis>("/api/intelligence/analyze/", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function analyzeUrlPublic(url: string): Promise<PublicAnalysis> {
  return apiFetch<PublicAnalysis>("/api/intelligence/public/analyze/", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function activateAnalysis(input: {
  analysis_id?: string;
  url?: string;
  target_ids?: string[];
  recipe?: string;
  workspace?: string | null;
  check_interval?: number | null;
}): Promise<ActivationResult> {
  return apiFetch<ActivationResult>("/api/intelligence/activate/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function quickMonitor(input: {
  url?: string;
  analysis_id?: string;
  recipe?: string;
}): Promise<QuickMonitorResult> {
  return apiFetch<QuickMonitorResult>("/api/intelligence/quick-monitor/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getRecipes(): Promise<{ recipes: Recipe[]; plan: string }> {
  return apiFetch<{ recipes: Recipe[]; plan: string }>("/api/intelligence/recipes/");
}

export function getProductWatches(): Promise<{ product_watches: ProductWatch[] }> {
  return apiFetch<{ product_watches: ProductWatch[] }>("/api/intelligence/product-watches/");
}

export function getProductWatch(id: string): Promise<ProductWatchDetail> {
  return apiFetch<ProductWatchDetail>(`/api/intelligence/product-watches/${id}/`);
}

export function getProductTimeline(
  id: string,
  params: { severity?: string; category?: string; limit?: number } = {},
): Promise<{ product_watch_id: string; count: number; changes: ProductChange[]; explanation: Explanation }> {
  const query = new URLSearchParams();
  if (params.severity) query.set("severity", params.severity);
  if (params.category) query.set("category", params.category);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<{
    product_watch_id: string;
    count: number;
    changes: ProductChange[];
    explanation: Explanation;
  }>(`/api/intelligence/product-watches/${id}/timeline/${suffix}`);
}

export function getMonitorProduct(monitorId: string): Promise<MonitorProduct> {
  return apiFetch<MonitorProduct>(`/api/intelligence/monitors/${monitorId}/product/`);
}
