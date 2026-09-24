import Link from "next/link";
import { ArrowLeft, ShieldQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <main className="auth-shell flex min-h-screen items-center justify-center px-6">
      <div className="animate-apeiro-fade-up text-center">
        <div className="modern-icon mx-auto mb-5 h-12 w-12 rounded-xl">
          <ShieldQuestion size={24} aria-hidden="true" />
        </div>

        <p className="text-sm font-medium text-muted-foreground">404</p>

        <h1 className="mt-1 font-display text-3xl font-normal tracking-tight text-foreground">
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