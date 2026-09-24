"use client";

import { useMemo } from "react";
import {
  Camera,
  DollarSign,
  FileDiff,
  FileSpreadsheet,
  Repeat,
  type LucideIcon,
} from "lucide-react";

export type DiffLineKind = "add" | "remove" | "context";

export interface DiffLine {
  kind: DiffLineKind;
  text: string;
}

export interface DiffViewerProps {
  title: string;
  diffType: "dom" | "screenshot" | "price";
  summary?: string;
  before?: string;
  after?: string;
  diffPercentage?: number | null;
  createdAt?: string;
  meta?: Record<string, string>;
}

const TYPE_META: Record<
  DiffViewerProps["diffType"],
  { label: string; icon: LucideIcon; className: string }
> = {
  dom: {
    label: "DOM & CSS diff",
    icon: FileDiff,
    className: "bg-warning-muted text-warning",
  },
  screenshot: {
    label: "Visual diff",
    icon: Camera,
    className: "bg-secondary text-secondary-foreground",
  },
  price: {
    label: "Price diff",
    icon: DollarSign,
    className: "bg-success-muted text-success",
  },
};

function lcsTable(a: string[], b: string[]) {
  const m = a.length;
  const n = b.length;
  const table: number[][] = Array.from({ length: m + 1 }, () =>
    new Array<number>(n + 1).fill(0),
  );

  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      table[i][j] =
        a[i] === b[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }

  return table;
}

export function diffLines(a: string[], b: string[]): DiffLine[] {
  if (a.length === 0 && b.length === 0) return [];

  if (a.length === 0) {
    return b.map((text) => ({ kind: "add", text }));
  }

  if (b.length === 0) {
    return a.map((text) => ({ kind: "remove", text }));
  }

  const table = lcsTable(a, b);
  const lines: DiffLine[] = [];
  let i = 0;
  let j = 0;

  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      lines.push({ kind: "context", text: a[i] });
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      lines.push({ kind: "remove", text: a[i] });
      i += 1;
    } else {
      lines.push({ kind: "add", text: b[j] });
      j += 1;
    }
  }

  while (i < a.length) {
    lines.push({ kind: "remove", text: a[i] });
    i += 1;
  }

  while (j < b.length) {
    lines.push({ kind: "add", text: b[j] });
    j += 1;
  }

  return lines;
}

export function diffText(a: string, b: string): DiffLine[] {
  return diffLines(a.split("\n"), b.split("\n"));
}

export function priceDiffFromSummary(
  summary: string,
): { before: string; after: string } | null {
  const match = summary.match(
    /from\s+([\d.,]+)\s+to\s+([\d.,]+)\s+([A-Za-z]{3})/i,
  );

  if (!match) return null;

  const [, before, after, currency] = match;

  return {
    before: `${before} ${currency.toUpperCase()}`,
    after: `${after} ${currency.toUpperCase()}`,
  };
}

function lineClass(kind: DiffLineKind) {
  if (kind === "add") {
    return "border-l-2 border-emerald-400 bg-emerald-500/[0.09] text-emerald-300";
  }

  if (kind === "remove") {
    return "border-l-2 border-rose-400 bg-rose-500/[0.09] text-rose-300";
  }

  return "border-l-2 border-transparent text-slate-400";
}

function prefixFor(kind: DiffLineKind) {
  if (kind === "add") return "+";
  if (kind === "remove") return "-";
  return " ";
}

export function DiffViewer({
  title,
  diffType,
  summary,
  before,
  after,
  diffPercentage,
  createdAt,
  meta,
}: DiffViewerProps) {
  const typeMeta = TYPE_META[diffType];
  const TypeIcon = typeMeta.icon;

  const { lines, additions, deletions } = useMemo(() => {
    if (before != null && after != null) {
      return diffText(before, after).reduce(
        (acc, line) => {
          if (line.kind === "add") acc.additions += 1;
          if (line.kind === "remove") acc.deletions += 1;
          acc.lines.push(line);
          return acc;
        },
        { lines: [] as DiffLine[], additions: 0, deletions: 0 },
      );
    }

    if (diffType === "price" && summary) {
      const parsed = priceDiffFromSummary(summary);

      if (parsed) {
        const generated = diffLines(
          [parsed.before],
          [parsed.after],
        );

        return {
          lines: generated,
          additions: generated.filter((line) => line.kind === "add").length,
          deletions: generated.filter((line) => line.kind === "remove")
            .length,
        };
      }
    }

    return {
      lines: [
        { kind: "context", text: summary || "Change detected." },
      ] as DiffLine[],
      additions: 0,
      deletions: 0,
    };
  }, [before, after, diffType, summary]);

  const hasChanges = additions > 0 || deletions > 0;

  return (
    <section className="apeiro-card overflow-hidden">
      <div className="border-b border-border p-6">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${typeMeta.className}`}
          >
            <TypeIcon size={16} />
          </span>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-base font-semibold">{title}</h2>
              <span className={`apeiro-badge text-xs ${typeMeta.className}`}>
                <TypeIcon size={12} />
                {typeMeta.label}
              </span>
            </div>

            {createdAt && (
              <p className="mt-0.5 text-xs text-slate-400">{createdAt}</p>
            )}
          </div>
        </div>

        {summary && (
          <p className="mt-3 rounded-lg border border-border bg-muted/60 px-3.5 py-2.5 text-sm leading-6 text-slate-300">
            {summary}
          </p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
            <span className="font-semibold">+{additions}</span>
            additions
          </span>

          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-300">
            <span className="font-semibold">-{deletions}</span>
            deletions
          </span>

          {diffPercentage != null && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-slate-400">
              <Repeat size={11} />
              {diffPercentage.toFixed(2)}% changed
            </span>
          )}

          {meta &&
            Object.entries(meta).map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-slate-400"
              >
                <FileSpreadsheet size={11} />
                {key}: <span className="text-slate-300">{value}</span>
              </span>
            ))}
        </div>
      </div>

      <div className="code-surface overflow-x-auto">
        {hasChanges ? (
          <div className="min-w-[42rem] py-2 font-mono text-[0.8125rem] leading-6">
            <div className="flex items-center gap-2 bg-slate-800/40 px-4 py-1.5 text-xs font-medium text-slate-500">
              <FileDiff size={13} />
              <span className="truncate">{title}</span>
            </div>

            {lines.map((line, index) => (
              <div
                key={`${line.kind}-${index}`}
                className={`flex px-4 ${lineClass(line.kind)}`}
              >
                <span
                  className={`mr-3 w-6 shrink-0 select-none text-right font-semibold ${
                    line.kind === "add"
                      ? "text-emerald-400"
                      : line.kind === "remove"
                        ? "text-rose-400"
                        : "text-slate-600"
                  }`}
                  aria-hidden="true"
                >
                  {prefixFor(line.kind)}
                </span>
                <span className="whitespace-pre-wrap break-words">
                  {line.text || " "}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-5 py-8 text-center">
            <FileDiff size={20} className="mx-auto text-slate-600" />

            <p className="mt-3 text-sm font-medium text-slate-300">
              No structured diff lines available for this event.
            </p>

            <p className="mt-1 text-xs text-slate-500">
              Raw content snapshots are hashed and not persisted to keep
              storage lean.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

export default DiffViewer;