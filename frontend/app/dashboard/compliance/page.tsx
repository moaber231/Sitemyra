"use client";

import { useState } from "react";
import { FileCheck, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function download(type: "csv" | "pdf") {
  const token = sessionStorage.getItem("apeiro_access");
  if (!token) {
    window.location.href = "/login";
    return;
  }
  const res = await fetch(
    `${API_URL}/api/monitors/export/compliance/?type=${type}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!res.ok) throw new Error(`Export failed (${res.status}).`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `apeiro-compliance-report.${type}`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function CompliancePage() {
  const [busy, setBusy] = useState<string | null>(null);

  async function handle(type: "csv" | "pdf") {
    setBusy(type);
    try {
      await download(type);
      toast.success(`Compliance report (${type.toUpperCase()}) downloaded.`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl py-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <FileCheck size={22} /> Export Compliance Report
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          One-click download of uptime, SLA metrics (99.9% target), failure and
          change histories for your records — auditor-friendly CSV or PDF.
        </p>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {(["csv", "pdf"] as const).map((type) => (
            <button
              key={type}
              onClick={() => handle(type)}
              disabled={busy !== null}
              className="apeiro-card apeiro-interactive p-6 text-center"
            >
              {busy === type ? (
                <Loader2 size={22} className="mx-auto animate-spin" />
              ) : (
                <Download size={22} className="mx-auto" />
              )}
              <p className="mt-2 font-semibold uppercase">{type}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {type === "csv"
                  ? "Spreadsheet-ready rows per monitor"
                  : "Formatted auditor report"}
              </p>
            </button>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
