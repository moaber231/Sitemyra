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
  /** "rules" or "ai:<provider>". Present on the event deep link. */
  generator?: string;
  /** True when the text came from Sitemyra's fixed rules rather than a model. */
  is_fallback?: boolean;
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

/* ------------------------------------------------------------------ *
 * Phase 6 — browser extension sessions
 * ------------------------------------------------------------------ */

export type ExtensionSession = {
  id: string;
  label: string;
  prefix: string;
  scopes: string;
  is_active: boolean;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export function getExtensionSessions(): Promise<{ sessions: ExtensionSession[]; allowed_scopes: string }> {
  return apiFetch<{ sessions: ExtensionSession[]; allowed_scopes: string }>(
    "/api/intelligence/extension-sessions/",
  );
}

export function createExtensionSession(label: string): Promise<
  ExtensionSession & { token: string; warning: string }
> {
  return apiFetch("/api/intelligence/extension-sessions/", {
    method: "POST",
    body: JSON.stringify({ label }),
  });
}

export function revokeExtensionSession(id: string): Promise<{ id: string; is_active: boolean }> {
  return apiFetch(`/api/intelligence/extension-sessions/${id}/`, { method: "DELETE" });
}

/* ------------------------------------------------------------------ *
 * Phase 2 — feed, pulse, competitors, discovery
 * ------------------------------------------------------------------ */

export type FeedEvent = {
  id: string;
  kind: string;
  icon: string;
  headline: string;
  summary: string;
  before: string;
  after: string;
  severity: Severity;
  source_url: string;
  detected_at: string;
  competitor_id: string | null;
  competitor_name: string | null;
  monitor_id: string | null;
  monitor_name: string | null;
  product_change_id: string | null;
  monitor_check_id: string | null;
  evidence: Record<string, unknown>;
  has_evidence: boolean;
};

export type FeedPage = {
  results: FeedEvent[];
  count: number;
  has_more: boolean;
  next_cursor: string | null;
  counts_by_kind: Record<string, number>;
  available_kinds: { value: string; label: string }[];
};

export type PulseState = {
  competitor_id: string;
  name: string;
  domain: string;
  homepage_url: string;
  relationship: string;
  relationship_reasons: string[];
  signals: string[];
  states: string[];
  state_label: string;
  window_days: number;
  events_in_window: number;
  events_by_kind: Record<string, number>;
  events_by_severity: Record<string, number>;
  dominant_kind: string;
  last_activity_at: string | null;
  monitor_count: number;
  tracks_product: boolean;
  first_seen_at: string | null;
};

export type PulseResponse = {
  window_days: number;
  competitors: PulseState[];
  totals: { competitors: number; with_activity: number };
};

export type CompetitorCandidate = {
  id: string;
  url: string;
  domain: string;
  relationship: string;
  reasons: string[];
  reason_list: string[];
  confidence: Confidence;
  approved: boolean;
  approved_at: string | null;
};

export type IntelligenceOverview = {
  competitors: number;
  active_competitors: number;
  events_7d: number;
  events_24h: number;
};

export type EventDetail = FeedEvent & {
  explanation: Explanation;
  product_watch_id: string | null;
  context: {
    id: string;
    headline: string;
    kind: string;
    severity: Severity;
    detected_at: string;
  }[];
  evidence_url: string;
  timeline_url: string | null;
  export: { csv: string; json: string };
};

export type MarketSignal = {
  id: string;
  kind: string;
  headline: string;
  statement: string;
  interpretation: string;
  window_days: number;
  evidence: {
    signal_event_id: string;
    competitor_id: string | null;
    competitor: string | null;
    headline: string;
    before: string;
    after: string;
    source_url: string;
    detected_at: string;
    severity: Severity;
  }[];
  evidence_count: number;
  confidence: Confidence;
  status: string;
  created_at: string;
};

export type NarrationPreference = {
  ai_narration_enabled: boolean;
  provider_configured: boolean;
  provider: string | null;
  explanation: string;
};

export function getFeed(params: {
  kind?: string;
  severity?: string;
  competitor?: string;
  monitor?: string;
  cursor?: string;
  limit?: number;
  window_days?: number;
} = {}): Promise<FeedPage> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "" && value !== null) query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<FeedPage>(`/api/intelligence/feed/${suffix}`);
}

export function getPulse(windowDays?: number): Promise<PulseResponse> {
  const suffix = windowDays ? `?window_days=${windowDays}` : "";
  return apiFetch<PulseResponse>(`/api/intelligence/pulse/${suffix}`);
}

export function getIntelligenceOverview(): Promise<IntelligenceOverview> {
  return apiFetch<IntelligenceOverview>("/api/intelligence/overview/");
}

export function getCompetitor(id: string): Promise<
  PulseState & {
    candidates: CompetitorCandidate[];
    monitors: { id: string; name: string; url: string; active: boolean }[];
  }
> {
  return apiFetch(`/api/intelligence/competitors/${id}/`);
}

export function discoverCompetitors(
  url: string,
  workspace?: string | null,
): Promise<{
  competitor: { id: string; name: string; domain: string; homepage_url: string };
  candidate_count: number;
  candidates: CompetitorCandidate[];
  detail: string;
}> {
  return apiFetch("/api/intelligence/competitors/discover/", {
    method: "POST",
    body: JSON.stringify({ url, workspace: workspace ?? undefined }),
  });
}

export function approveCandidate(input: {
  candidate_id: string;
  recipe?: string;
  workspace?: string | null;
}): Promise<{
  competitor: { id: string; name: string; domain: string; relationship: string };
  monitors: unknown[];
  created: number;
  limit_reached: boolean;
  detail?: string;
}> {
  return apiFetch("/api/intelligence/competitors/approve/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getEventDetail(id: string): Promise<EventDetail> {
  return apiFetch<EventDetail>(`/api/intelligence/events/${id}/`);
}

export function getSignals(status?: string): Promise<{
  count: number;
  minimum_competitors: number;
  signals: MarketSignal[];
}> {
  const suffix = status ? `?status=${status}` : "";
  return apiFetch(`/api/intelligence/signals/${suffix}`);
}

export function reviewSignal(
  id: string,
  status: "reviewed" | "dismissed",
): Promise<{ id: string; status: string }> {
  return apiFetch(`/api/intelligence/signals/${id}/review/`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

export function getNarrationPreference(): Promise<NarrationPreference> {
  return apiFetch<NarrationPreference>("/api/intelligence/narration-preference/");
}

export function updateNarrationPreference(enabled: boolean): Promise<NarrationPreference> {
  return apiFetch<NarrationPreference>("/api/intelligence/narration-preference/", {
    method: "PATCH",
    body: JSON.stringify({ ai_narration_enabled: enabled }),
  });
}

/* ------------------------------------------------------------------ *
 * Phase 4 — reports and battlecards
 * ------------------------------------------------------------------ */

export type ReportSummary = {
  id: string;
  title: string;
  slug: string;
  kind: string;
  status: string;
  formats: string[];
  period_start: string;
  period_end: string;
  rows: number;
  competitors: number;
  sources: number;
  truncated: boolean;
  branding: Record<string, unknown>;
  generated_at: string | null;
  created_at: string;
  executive_summary: string;
  downloads: Record<string, string>;
};

export type Battlecard = {
  id: string;
  is_stale: boolean;
  generated_at: string | null;
  stale_note: string;
  refreshed: boolean;
  competitor: {
    id: string;
    name: string;
    domain: string;
    website: string;
    relationship: string;
    relationship_reasons: string[];
    first_seen_at: string | null;
  };
  state: string;
  states: string[];
  products: Record<string, unknown>[];
  pricing: {
    name: string;
    price: string;
    list_price: string;
    discount_percent: number | null;
    currency: string;
    source_url: string;
    captured_at: string;
  }[];
  features: Record<string, unknown>[];
  recent_changes: {
    id: string;
    detected_at: string;
    headline: string;
    kind: string;
    severity: Severity;
    source_url: string;
  }[];
  positioning: string;
  sources: string[];
  note: string;
};

export const EXPORT_FORMATS = ["csv", "xlsx", "json", "markdown", "html", "xml", "pdf"] as const;

export function getReports(): Promise<{ reports: ReportSummary[] }> {
  return apiFetch<{ reports: ReportSummary[] }>("/api/intelligence/reports/");
}

export function createReport(input: {
  title: string;
  period_days?: number;
  competitor_ids?: string[];
  formats?: string[];
  workspace?: string | null;
  organization?: string | null;
}): Promise<ReportSummary> {
  return apiFetch<ReportSummary>("/api/intelligence/reports/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getBattlecard(competitorId: string, refresh = false): Promise<Battlecard> {
  const suffix = refresh ? "?refresh=1" : "";
  return apiFetch<Battlecard>(`/api/intelligence/competitors/${competitorId}/battlecard/${suffix}`);
}

/* ------------------------------------------------------------------ *
 * Phase 5 — agency mode
 * ------------------------------------------------------------------ */

export type Organization = {
  id: string;
  name: string;
  slug: string;
  role: string;
  branding: Record<string, unknown>;
  plan: string;
  mrr_cents: number;
  is_active: boolean;
  seats: number;
  clients: number;
  limits: {
    max_seats: number;
    max_client_workspaces: number;
    max_monitors: number;
    min_interval_seconds: number;
    white_label: boolean;
    history_days: number;
  };
  available_plans: string[];
  created_at: string;
};

export type ClientWorkspace = {
  id: string;
  name: string;
  slug: string;
  organization_id: string | null;
  owner_id: string;
  members: number;
  monitors: number;
  monitors_total: number;
  competitors: number;
  created_at: string;
};

export function getOrganizations(): Promise<{ organizations: Organization[] }> {
  return apiFetch<{ organizations: Organization[] }>("/api/intelligence/organizations/");
}

export function createOrganization(name: string): Promise<Organization> {
  return apiFetch<Organization>("/api/intelligence/organizations/", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function getOrganizationWorkspaces(id: string): Promise<{ workspaces: ClientWorkspace[] }> {
  return apiFetch<{ workspaces: ClientWorkspace[] }>(
    `/api/intelligence/organizations/${id}/workspaces/`,
  );
}

export function createClientWorkspace(id: string, name: string): Promise<ClientWorkspace> {
  return apiFetch<ClientWorkspace>(`/api/intelligence/organizations/${id}/workspaces/`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function getOrganizationBranding(id: string): Promise<{
  branding: Record<string, unknown>;
  white_label_enabled: boolean;
  note: string;
}> {
  return apiFetch(`/api/intelligence/organizations/${id}/branding/`);
}

export function updateOrganizationBranding(
  id: string,
  branding: Record<string, unknown>,
): Promise<{ branding: Record<string, unknown>; updated_at: string }> {
  return apiFetch(`/api/intelligence/organizations/${id}/branding/`, {
    method: "PATCH",
    body: JSON.stringify(branding),
  });
}
