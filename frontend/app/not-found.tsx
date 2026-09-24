import Link from "next/link";
import { ArrowLeft, ShieldQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="animate-apeiro-fade-up text-center">
        <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-secondary">
          <ShieldQuestion size={24} aria-hidden="true" />
        </div>

        <p className="text-sm font-medium text-muted-foreground">404</p>

        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          Page not found
        </h1>

        <p className="mt-2 text-sm text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist.
        </p>

        <Link
          href="/"
          className="apeiro-btn apeiro-btn-primary mt-6"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          Back to homepage
        </Link>
      </div>
    </main>
  );
}