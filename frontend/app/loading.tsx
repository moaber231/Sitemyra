export default function Loading() {
  return (
    <div className="auth-shell flex min-h-screen items-center justify-center">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent/20 border-t-accent" />
        Loading Sitemyra...
      </div>
    </div>
  );
}