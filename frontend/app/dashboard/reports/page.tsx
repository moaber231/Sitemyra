"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Loader2, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { DashboardHeader } from "@/components/navigation/DashboardHeader";
import { Note, relativeTime } from "@/components/intelligence/primitives";
import { createReport, getReports, type ReportSummary } from "@/lib/api/intelligence";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

/**
 * Reports (Feature 11).
 *
 * A report is a dated snapshot: executive summary, competitors, changes by
 * category, a timeline, and the source links. The composed payload is stored
 * with the report, so a download always reproduces exactly what was shared.
 */
export default function ReportsPage() {
  const [title, setTitle] = useState("");
  const [periodDays, setPeriodDays] = useState(30);
  const [formats, setFormats] = useState<string[]>(["html", "pdf"]);
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["intelligence-reports"],
    queryFn: getReports,
    retry: false,
  });

  const create = useMutation({
    mutationFn: () =>
      createReport({
        title: title.trim() || "Competitive intelligence report",
        period_days: periodDays,
        formats,
      }),
    onSuccess: (report) => {
      toast.success(`“${report.title}” is ready.`);
      setTitle("");
      void queryClient.invalidateQueries({ queryKey: ["intelligence-reports"] });
    },
    onError: (caught) =>
      toast.error(caught instanceof Error ? caught.message : "Could not build the report."),
  });

  const reports = data?.reports ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <div className="apeiro-stagger stagger-1">
          <DashboardHeader title="Reports" />
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Turn your intelligence into something you can send. Every row carries its source
            URL and detection time, so the recipient can check any claim.
          </p>
        </div>

        <section className="apeiro-stagger stagger-2 apeiro-card mt-6 p-6">
          <h2 className="text-sm font-semibold text-foreground">Build a report</h2>
          <div className="mt-4 space-y-4">
            <div>
              <label htmlFor="report-title" className="mb-2 block text-sm font-medium text-foreground">
                Title
              </label>
              <input
                id="report-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Q3 competitive intelligence — Acme"
                className="apeiro-input"
              />
            </div>
            <div>
              <label htmlFor="report-period" className="mb-2 block text-sm font-medium text-foreground">
                Period
              </label>
              <select
                id="report-period"
                value={periodDays}
                onChange={(event) => setPeriodDays(Number(event.target.value))}
                className="apeiro-input"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={180}>Last 180 days</option>
              </select>
            </div>
            <fieldset>
              <legend className="mb-2 text-sm font-medium text-foreground">Formats</legend>
              <div className="flex flex-wrap gap-2">
                {["html", "pdf", "csv", "xlsx", "json", "markdown", "xml"].map((fmt) => {
                  const active = formats.includes(fmt);
                  return (
                    <button
                      key={fmt}
                      type="button"
                      onClick={() =>
                        setFormats((current) =>
                          current.includes(fmt)
                            ? current.filter((item) => item !== fmt)
                            : [...current, fmt],
                        )
                      }
                      aria-pressed={active}
                      className={`apeiro-btn !min-h-0 !py-1.5 text-xs ${
                        active ? "apeiro-btn-primary" : "apeiro-btn-ghost"
                      }`}
                    >
                      {fmt.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </fieldset>
            <button
              type="button"
              onClick={() => create.mutate()}
              disabled={create.isPending || formats.length === 0}
              className="apeiro-btn apeiro-btn-primary"
            >
              {create.isPending ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <FileText size={15} aria-hidden="true" />}
              {create.isPending ? "Building…" : "Build report"}
            </button>
          </div>
        </section>

        <div className="apeiro-stagger stagger-3 mt-6">
          {isLoading ? (
            <div className="apeiro-card h-32 animate-pulse bg-muted/40" aria-busy="true" />
          ) : isError ? (
            <div className="apeiro-card p-8 text-center" role="alert">
              <p className="text-sm text-danger">
                {(error as Error)?.message ?? "Sitemyra could not load your reports."}
              </p>
            </div>
          ) : reports.length === 0 ? (
            <Note>No reports yet. Build one above when you are ready to share your findings.</Note>
          ) : (
            <ul className="space-y-3">
              {reports.map((report) => (
                <ReportRow key={report.id} report={report} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function ReportRow({ report }: { report: ReportSummary }) {
  return (
    <li className="apeiro-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold tracking-tight text-foreground">
            {report.title}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {report.rows} change{report.rows === 1 ? "" : "s"} · {report.competitors} competitor
            {report.competitors === 1 ? "" : "s"} · {report.sources} source
            {report.sources === 1 ? "" : "s"} · {relativeTime(report.created_at)}
          </p>
        </div>
        <span className="apeiro-badge bg-secondary text-secondary-foreground capitalize">
          {report.status}
        </span>
      </div>

      {report.executive_summary ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{report.executive_summary}</p>
      ) : null}

      {report.truncated ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-warning">
          <TriangleAlert size={12} aria-hidden="true" />
          This report shows the most recent changes only.
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {Object.entries(report.downloads).map(([fmt, path]) => (
          <a
            key={fmt}
            href={`${API}${path}`}
            className="apeiro-btn apeiro-btn-outline !min-h-0 !py-1.5 text-xs"
          >
            <Download size={12} aria-hidden="true" />
            {fmt.toUpperCase()}
          </a>
        ))}
      </div>
    </li>
  );
}
