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
      className="modern-gradient-border overflow-hidden rounded-2xl"
      aria-label="Illustrative Sitemyra monitoring example"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 bg-card/80 px-4 py-3 backdrop-blur sm:px-5">
        <div className="flex items-center gap-3">
          <span className="modern-pulse-dot h-2.5 w-2.5 rounded-full bg-accent" aria-hidden="true" />
          <span className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-foreground">
            Sitemyra / monitor view
          </span>
        </div>
        <span className="rounded-full border border-accent/20 bg-accent/5 px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-accent">
          Illustrative example
        </span>
      </div>

      <div className="grid lg:grid-cols-[1.08fr_0.92fr]">
        <div className="border-b border-border/70 p-5 sm:p-8 lg:border-b-0 lg:border-r">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="marketing-label text-xs font-medium uppercase text-accent">
              Price change detected
            </p>
            <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">
              Example event
            </span>
          </div>

          <div className="mt-8 flex items-start gap-4">
            <span className="modern-icon h-11 w-11 shrink-0 rounded-xl">
              <ScanSearch size={20} strokeWidth={1.7} aria-hidden="true" />
            </span>
            <div>
              <h3 className="font-display text-2xl text-foreground">Example pricing page</h3>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                example.com/pricing
              </p>
            </div>
          </div>

          <div className="mt-10 flex flex-wrap items-end gap-4">
            <span className="text-3xl tabular-nums text-muted-foreground line-through">
              €49
            </span>
            <ArrowRight
              size={20}
              strokeWidth={1.7}
              className="mb-1 shrink-0 text-accent"
              aria-hidden="true"
            />
            <span className="text-6xl tabular-nums text-foreground">€59</span>
            <span className="mb-1 rounded-full border border-accent/20 bg-accent/5 px-2.5 py-1 font-mono text-xs text-accent">
              +20.4%
            </span>
          </div>

          <div className="mt-8 rounded-xl border border-border bg-muted/60 p-4 font-mono text-xs leading-7 text-muted-foreground">
            <p>
              <span className="mr-2 select-none font-semibold text-accent">−</span>
              <span>&lt;span class=&quot;price&quot;&gt;€49&lt;/span&gt;</span>
            </p>
            <p>
              <span className="mr-2 select-none font-semibold text-accent">+</span>
              <span>&lt;span class=&quot;price&quot;&gt;€59&lt;/span&gt;</span>
            </p>
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            Demonstration data only. This is not a real customer, company, or
            live alert.
          </p>
        </div>

        <div className="space-y-5 bg-muted/45 p-5 sm:p-8">
          <div className="flex items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-foreground">
            <BellRing size={16} strokeWidth={1.7} className="text-accent" aria-hidden="true" />
            What happens next
          </div>

          <div className="rounded-xl border border-border bg-card p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-accent/25 hover:shadow-md">
            <div className="flex items-center gap-3">
              <span className="modern-icon h-9 w-9 rounded-lg">
                <FileText size={17} strokeWidth={1.7} aria-hidden="true" />
              </span>
              <div>
                <p className="font-semibold text-foreground">Change is recorded</p>
                <p className="text-sm text-muted-foreground">
                  Sitemyra keeps the result in your monitor history.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-accent/25 hover:shadow-md">
            <div className="flex items-center gap-3">
              <span className="modern-icon h-9 w-9 rounded-lg">
                <Mail size={17} strokeWidth={1.7} aria-hidden="true" />
              </span>
              <div>
                <p className="font-semibold text-foreground">You receive an alert</p>
                <p className="text-sm text-muted-foreground">
                  Email, Slack, Discord, or a webhook you configure.
                </p>
              </div>
            </div>
            <p className="mt-4 rounded-lg border-l-2 border-accent bg-accent/5 px-3 py-2.5 text-sm leading-6 text-foreground">
              Price changed from <strong>€49</strong> to <strong>€59</strong>.
              Review the diff in your dashboard.
            </p>
          </div>

          <div className="flex items-center gap-2 pt-1 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-muted-foreground">
            <CheckCircle2 size={15} strokeWidth={1.7} className="text-success" aria-hidden="true" />
            Competitor changed something → Sitemyra detected it → you know.
          </div>
        </div>
      </div>
    </section>
  );
}
