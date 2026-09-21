import { AppShell } from "@/components/layout/app-shell";

export default function DashboardLoading() {
  return (
    <AppShell>
      <div className="animate-pulse space-y-6">
        <div className="space-y-3">
          <div className="apeiro-skeleton h-4 w-28" />
          <div className="apeiro-skeleton h-9 w-72" />
          <div className="apeiro-skeleton h-4 w-96 max-w-full" />
        </div>

        <div className="apeiro-card h-48 bg-primary/5" />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="apeiro-card h-28 p-5">
              <div className="flex items-center justify-between">
                <div className="apeiro-skeleton h-9 w-9 rounded-xl" />
                <div className="apeiro-skeleton h-4 w-10" />
              </div>
              <div className="apeiro-skeleton mt-5 h-6 w-16" />
            </div>
          ))}
        </div>

        <div className="apeiro-card h-72">
          <div className="space-y-3 p-6">
            {[1, 2, 3].map((item) => (
              <div key={item} className="apeiro-skeleton h-12" />
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}