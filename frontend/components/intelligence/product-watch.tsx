"use client";

import { useQuery } from "@tanstack/react-query";

import { getMonitorProduct, type MonitorProduct } from "@/lib/api/intelligence";

import { Note, SectionLabel } from "./primitives";
import {
  ChangeExplanation,
  ChangeTimeline,
  CurrentProduct,
  ProductTabError,
  ProductTabSkeleton,
} from "./product-watch-panel";

/**
 * The monitor's Product tab.
 *
 * It only renders for a monitor that actually has a product watch, and it
 * is explicit about confidence: Sitemyra shows what it read, from where,
 * and how sure it is.
 */
export function ProductWatchPanel({ monitorId }: { monitorId: string }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["monitor-product", monitorId],
    queryFn: () => getMonitorProduct(monitorId),
    enabled: Boolean(monitorId),
    retry: false,
  });

  if (isLoading) return <ProductTabSkeleton />;

  if (isError) {
    const message =
      (error as Error | undefined)?.message ??
      "Sitemyra could not load product intelligence for this monitor.";
    return <ProductTabError message={message} />;
  }

  if (!data) return <Note>No product intelligence is available for this monitor.</Note>;

  return <ProductWatchContent data={data} />;
}

function ProductWatchContent({ data }: { data: MonitorProduct }) {
  const watch = data.product_watch;

  return (
    <div className="space-y-6">
      <section>
        <SectionLabel>Tracked product</SectionLabel>
        <h2 className="mt-1.5 text-xl font-semibold tracking-tight text-foreground">{watch.name}</h2>
        <p className="mt-1 truncate text-sm text-muted-foreground">{watch.monitor_url}</p>
      </section>

      <CurrentProduct
        snapshot={data.current_snapshot}
        currency={watch.currency}
        productDetected={watch.product_detected}
        detectionNote={watch.detection_note}
      />

      <ChangeExplanation explanation={data.explanation} productName={watch.name} />

      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <SectionLabel>Change timeline</SectionLabel>
          <p className="text-xs text-muted-foreground">
            {data.changes.length} recorded change{data.changes.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="mt-3">
          <ChangeTimeline changes={data.changes} />
        </div>
      </section>

      <Note>
        Sitemyra records these changes from the page&apos;s own published data on every check.
        It does not access private systems, and it never estimates a value the page does not
        publish.
      </Note>
    </div>
  );
}
