import {
  ArrowRight,
  BellRing,
  CheckCircle2,
  FileText,
  Mail,
  ScanSearch,
} from "lucide-react";

export function DemoMonitor() {
  return (
    <section
      className="apeiro-card overflow-hidden"
      aria-label="Illustrative Sitemyra monitoring example"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ef8c8c]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#e5c46c]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#8bc98e]" />
          <span className="ml-2 text-xs font-medium text-muted-foreground">
            Sitemyra monitor view
          </span>
        </div>
        <span className="apeiro-badge border border-border bg-muted text-muted-foreground">
          Illustrative example
        </span>
      </div>

      <div className="grid lg:grid-cols-[1.08fr_0.92fr]">
        <div className="border-b border-border p-5 sm:p-7 lg:border-b-0 lg:border-r">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Price change detected
            </p>
            <span className="apeiro-badge bg-warning-muted text-warning">
              <span className="h-1.5 w-1.5 rounded-full bg-warning" />
              Example event
            </span>
          </div>

          <div className="mt-5 flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
              <ScanSearch size={19} aria-hidden="true" />
            </span>
            <div>
              <h3 className="font-semibold">Example pricing page</h3>
              <p className="mt-1 break-all text-sm text-muted-foreground">
                example.com/pricing
              </p>
            </div>
          </div>

          <div className="mt-7 flex flex-wrap items-end gap-3">
            <span className="text-3xl font-semibold tabular-nums text-muted-foreground line-through">
              €49
            </span>
            <ArrowRight
              size={19}
              className="mb-1 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
            <span className="text-5xl font-semibold tabular-nums text-success">
              €59
            </span>
            <span className="mb-1 rounded-full bg-warning-muted px-2.5 py-1 text-xs font-semibold text-warning">
              +20.4%
            </span>
          </div>

          <div className="mt-6 rounded-xl border border-border bg-secondary/40 p-4 font-mono text-xs leading-6">
            <p>
              <span className="mr-2 select-none font-semibold text-rose-400">
                −
              </span>
              <span className="text-rose-300">
                &lt;span class=&quot;price&quot;&gt;€49&lt;/span&gt;
              </span>
            </p>
            <p>
              <span className="mr-2 select-none font-semibold text-emerald-400">
                +
              </span>
              <span className="text-emerald-300">
                &lt;span class=&quot;price&quot;&gt;€59&lt;/span&gt;
              </span>
            </p>
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            Demonstration data only. This is not a real customer, company, or
            live alert.
          </p>
        </div>

        <div className="space-y-4 bg-muted/30 p-5 sm:p-7">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            <BellRing size={15} aria-hidden="true" />
            What happens next
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/15 text-sky-300">
                <FileText size={16} aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-semibold">Change is recorded</p>
                <p className="text-xs text-muted-foreground">
                  Sitemyra keeps the result in your monitor history.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-300">
                <Mail size={16} aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-semibold">You receive an alert</p>
                <p className="text-xs text-muted-foreground">
                  Email, Slack, Discord, or a webhook you configure.
                </p>
              </div>
            </div>
            <p className="mt-3 rounded-lg bg-muted/60 px-3 py-2.5 text-sm leading-6">
              Price changed from <strong>€49</strong> to <strong>€59</strong>.
              Review the diff in your dashboard.
            </p>
          </div>

          <div className="flex items-center gap-2 pt-1 text-xs text-muted-foreground">
            <CheckCircle2 size={14} className="text-success" aria-hidden="true" />
            Competitor changed something → Sitemyra detected it → you know.
          </div>
        </div>
      </div>
    </section>
  );
}
