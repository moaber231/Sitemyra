"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, Building2, Loader2, Palette, Plus } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { SectionLabel } from "@/components/intelligence/primitives";
import {
  createClientWorkspace,
  createOrganization,
  getOrganizationWorkspaces,
  getOrganizations,
  updateOrganizationBranding,
  type Organization,
} from "@/lib/api/intelligence";

/**
 * Agency mode (Feature 12).
 *
 * An agency owns client workspaces. Each client gets its own competitors,
 * monitors, alerts, reports and users — and branded reports carry the
 * agency's name instead of Sitemyra's.
 */
export default function OrganizationPage() {
  const [name, setName] = useState("");
  const [clientName, setClientName] = useState("");
  const [agencyName, setAgencyName] = useState("");
  const [color, setColor] = useState("#0052ff");
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["intelligence-organizations"],
    queryFn: getOrganizations,
    retry: false,
  });

  const organizations = data?.organizations ?? [];
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = organizations.find((org) => org.id === activeId) ?? organizations[0] ?? null;

  const clients = useQuery({
    queryKey: ["intelligence-clients", active?.id],
    queryFn: () => getOrganizationWorkspaces(active!.id),
    enabled: Boolean(active?.id),
    retry: false,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["intelligence-organizations"] });
    void queryClient.invalidateQueries({ queryKey: ["intelligence-clients"] });
  };

  const createOrg = useMutation({
    mutationFn: () => createOrganization(name.trim()),
    onSuccess: () => {
      toast.success("Agency created.");
      setName("");
      invalidate();
    },
    onError: (caught) => toast.error(caught instanceof Error ? caught.message : "Could not create the agency."),
  });

  const createClient = useMutation({
    mutationFn: () => createClientWorkspace(active!.id, clientName.trim()),
    onSuccess: () => {
      toast.success("Client workspace created.");
      setClientName("");
      invalidate();
    },
    onError: (caught) =>
      toast.error(caught instanceof Error ? caught.message : "Could not create the client."),
  });

  const saveBranding = useMutation({
    mutationFn: () =>
      updateOrganizationBranding(active!.id, { agency_name: agencyName, primary_color: color }),
    onSuccess: () => {
      toast.success("Branding updated.");
      invalidate();
    },
    onError: (caught) =>
      toast.error(caught instanceof Error ? caught.message : "Could not update branding."),
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Agency" />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Run competitive intelligence for many clients from one account: separate
            watchlists, separate alerts, branded reports.
          </p>
        </div>

        {isLoading ? (
          <div className="apeiro-card h-24 animate-pulse bg-muted/40" aria-busy="true" />
        ) : isError ? (
          <div className="apeiro-card p-8 text-center" role="alert">
            <p className="text-sm text-danger">
              {(error as Error)?.message ?? "Sitemyra could not load your agencies."}
            </p>
          </div>
        ) : organizations.length === 0 ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              createOrg.mutate();
            }}
            className="apeiro-card p-6"
          >
            <h2 className="text-sm font-semibold text-foreground">Create an agency</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              One account, many client workspaces. You become its owner.
            </p>
            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="North Studio"
                aria-label="Agency name"
                className="apeiro-input flex-1"
              />
              <button
                type="submit"
                disabled={createOrg.isPending || !name.trim()}
                className="apeiro-btn apeiro-btn-primary shrink-0"
              >
                {createOrg.isPending ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}
                Create
              </button>
            </div>
          </form>
        ) : (
          <>
            {organizations.length > 1 ? (
              <div role="group" aria-label="Choose an agency" className="flex flex-wrap gap-2">
                {organizations.map((org) => (
                  <button
                    key={org.id}
                    type="button"
                    onClick={() => setActiveId(org.id)}
                    aria-pressed={active?.id === org.id}
                    className={`apeiro-btn !min-h-0 !py-1.5 text-xs ${
                      active?.id === org.id ? "apeiro-btn-primary" : "apeiro-btn-ghost"
                    }`}
                  >
                    {org.name}
                  </button>
                ))}
              </div>
            ) : null}

            {active ? <AgencyPanel org={active} /> : null}

            <section className="apeiro-card p-6">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Briefcase size={15} className="text-accent" aria-hidden="true" />
                Client workspaces
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {active?.limits.max_client_workspaces} included on the {active?.plan} plan ·{" "}
                {active?.clients} created
              </p>

              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <input
                  value={clientName}
                  onChange={(event) => setClientName(event.target.value)}
                  placeholder="Client A"
                  aria-label="Client name"
                  className="apeiro-input flex-1"
                />
                <button
                  type="button"
                  onClick={() => createClient.mutate()}
                  disabled={createClient.isPending || !clientName.trim() || !active}
                  className="apeiro-btn apeiro-btn-primary shrink-0"
                >
                  {createClient.isPending ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Plus size={15} aria-hidden="true" />}
                  Add client
                </button>
              </div>

              <ul className="mt-4 divide-y divide-border rounded-2xl border border-border">
                {(clients.data?.workspaces ?? []).map((client) => (
                  <li key={client.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-foreground">{client.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {client.monitors} active monitor{client.monitors === 1 ? "" : "s"} ·{" "}
                        {client.competitors} competitor{client.competitors === 1 ? "" : "s"} ·{" "}
                        {client.members} member{client.members === 1 ? "" : "s"}
                      </span>
                    </span>
                    <a href={`/dashboard/monitors?workspace=${client.id}`} className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs">
                      Open watchlist
                    </a>
                  </li>
                ))}
                {(clients.data?.workspaces ?? []).length === 0 ? (
                  <li className="px-4 py-6 text-center text-sm text-muted-foreground">
                    No client workspaces yet.
                  </li>
                ) : null}
              </ul>
            </section>

            <section className="apeiro-card p-6">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Palette size={15} className="text-accent" aria-hidden="true" />
                Report branding
              </h2>
              {!active?.limits.white_label ? (
                <p className="mt-2 text-sm text-muted-foreground">
                  White-label reports are part of the Pro and Business plans.
                </p>
              ) : (
                <>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Your name and colour on every report you share. Stored as plain text — Sitemyra
                    never renders it as HTML and never fetches a logo URL.
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div>
                      <label htmlFor="brand-name" className="mb-2 block text-sm font-medium text-foreground">
                        Agency name
                      </label>
                      <input
                        id="brand-name"
                        value={agencyName}
                        onChange={(event) => setAgencyName(event.target.value)}
                        placeholder={active.name}
                        className="apeiro-input"
                      />
                    </div>
                    <div>
                      <label htmlFor="brand-color" className="mb-2 block text-sm font-medium text-foreground">
                        Primary colour
                      </label>
                      <input
                        id="brand-color"
                        value={color}
                        onChange={(event) => setColor(event.target.value)}
                        className="apeiro-input font-mono"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => saveBranding.mutate()}
                    disabled={saveBranding.isPending}
                    className="apeiro-btn apeiro-btn-primary mt-4"
                  >
                    {saveBranding.isPending ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : null}
                    Save branding
                  </button>
                </>
              )}
            </section>
          </>
        )}
      </div>
    </AppShell>
  );
}

function AgencyPanel({ org }: { org: Organization }) {
  return (
    <section className="apeiro-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight text-foreground">
            <Building2 size={17} className="text-accent" aria-hidden="true" />
            {org.name}
          </h2>
          <p className="mt-0.5 text-xs capitalize text-muted-foreground">
            {org.role} · {org.plan} plan
          </p>
        </div>
        <span className="apeiro-badge bg-secondary text-secondary-foreground capitalize">
          {org.is_active ? "Active" : "Deactivated"}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Seats" value={`${org.seats}/${org.limits.max_seats}`} />
        <Stat label="Clients" value={`${org.clients}/${org.limits.max_client_workspaces}`} />
        <Stat label="URLs" value={`${org.limits.max_monitors}`} />
        <Stat label="History" value={`${org.limits.history_days}d`} />
      </dl>
      <p className="mt-4">
        <SectionLabel>Note</SectionLabel>{" "}
        <span className="text-xs text-muted-foreground">
          Plan limits apply across the whole agency. Client monitors are paused, never deleted,
          if the agency downgrades.
        </span>
      </p>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/30 px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular-nums text-base font-semibold text-foreground">{value}</dd>
    </div>
  );
}
