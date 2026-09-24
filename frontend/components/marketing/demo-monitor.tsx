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
      className="apeiro-card marketing-grid overflow-hidden border-2"
      aria-label="Illustrative Sitemyra monitoring example"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 bg-black px-4 py-3 text-white sm:px-5">
        <div className="flex items-center gap-3">
          <span className="h-3 w-3 border border-white" aria-hidden="true" />
          <span className="font-mono text-[0.68rem] uppercase tracking-[0.16em]">
            Sitemyra / monitor view
          </span>
        </div>
        <span className="border border-white px-2 py-1 font-mono text-[0.62rem] uppercase tracking-[0.14em]">
          Illustrative example
        </span>
      </div>

      <div className="grid lg:grid-cols-[1.08fr_0.92fr]">
        <div className="border-b-2 p-5 sm:p-8 lg:border-b-0 lg:border-r-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="marketing-label text-xs font-medium uppercase">
              Price change detected
            </p>
            <span className="border border-border px-2 py-1 font-mono text-[0.62rem] uppercase tracking-[0.14em]">
              Example event
            </span>
          </div>

          <div className="mt-8 flex items-start gap-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center border border-border bg-secondary">
              <ScanSearch size={20} strokeWidth={1.5} aria-hidden="true" />
            </span>
            <div>
              <h3 className="font-display text-2xl">Example pricing page</h3>
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
              strokeWidth={1.5}
              className="mb-1 shrink-0"
              aria-hidden="true"
            />
            <span className="text-6xl tabular-nums">€59</span>
            <span className="mb-1 border border-border px-2 py-1 font-mono text-xs">
              +20.4%
            </span>
          </div>

          <div className="mt-8 border border-border bg-secondary p-4 font-mono text-xs leading-7">
            <p>
              <span className="mr-2 select-none font-semibold">−</span>
              <span>&lt;span class=&quot;price&quot;&gt;€49&lt;/span&gt;</span>
            </p>
            <p>
              <span className="mr-2 select-none font-semibold">+</span>
              <span>&lt;span class=&quot;price&quot;&gt;€59&lt;/span&gt;</span>
            </p>
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            Demonstration data only. This is not a real customer, company, or
            live alert.
          </p>
        </div>

        <div className="space-y-5 bg-secondary p-5 sm:p-8">
          <div className="flex items-center gap-2 font-mono text-[0.68rem] uppercase tracking-[0.16em]">
            <BellRing size={16} strokeWidth={1.5} aria-hidden="true" />
            What happens next
          </div>

          <div className="border border-border bg-white p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center border border-border">
                <FileText size={17} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <div>
                <p className="font-semibold">Change is recorded</p>
                <p className="text-sm text-muted-foreground">
                  Sitemyra keeps the result in your monitor history.
                </p>
              </div>
            </div>
          </div>

          <div className="border border-border bg-white p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center border border-border">
                <Mail size={17} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <div>
                <p className="font-semibold">You receive an alert</p>
                <p className="text-sm text-muted-foreground">
                  Email, Slack, Discord, or a webhook you configure.
                </p>
              </div>
            </div>
            <p className="mt-4 border-l-2 border-border pl-3 text-sm leading-6">
              Price changed from <strong>€49</strong> to <strong>€59</strong>.
              Review the diff in your dashboard.
            </p>
          </div>

          <div className="flex items-center gap-2 pt-1 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-muted-foreground">
            <CheckCircle2 size={15} strokeWidth={1.5} aria-hidden="true" />
            Competitor changed something → Sitemyra detected it → you know.
          </div>
        </div>
      </div>
    </section>
  );
}
