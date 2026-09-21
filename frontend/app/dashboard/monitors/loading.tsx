export default function MonitorsLoading() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading monitors">
      <div className="border-b border-slate-800/60 py-4">
        <div className="flex items-center gap-3">
          <div className="apeiro-skeleton h-9 w-9 rounded-xl bg-slate-800/50" />
          <div className="space-y-2">
            <div className="apeiro-skeleton h-3 w-40 bg-slate-800/50" />
            <div className="apeiro-skeleton h-6 w-56 bg-slate-800/50" />
          </div>
        </div>
      </div>

      <div className="apeiro-skeleton h-4 w-96 max-w-full bg-slate-800/50" />

      <div className="space-y-3">
        {[1, 2, 3].map((item) => (
          <div key={item} className="apeiro-glass p-5">
            <div className="flex items-center gap-3">
              <div className="apeiro-skeleton h-9 w-9 shrink-0 rounded-xl bg-slate-800/50" />
              <div className="apeiro-skeleton h-4 w-48 max-w-full bg-slate-800/50" />
            </div>
            <div className="apeiro-skeleton mt-3 h-3 w-72 max-w-full bg-slate-800/50" />
          </div>
        ))}
      </div>
    </div>
  );
}
