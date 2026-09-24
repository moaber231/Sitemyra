"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { login } from "@/lib/api/auth";
import {
  oauthStart,
  oauthStatus,
  type OAuthProvider,
} from "@/lib/api/developer";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [providers, setProviders] = useState<
    Record<OAuthProvider, { enabled: boolean }>
  >({
    google: { enabled: false },
    github: { enabled: false },
  });
  const [ssoLoading, setSsoLoading] = useState<OAuthProvider | null>(null);

  useEffect(() => {
    oauthStatus()
      .then((result) => setProviders(result.providers))
      .catch(() => {});
    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("oauth_error");
    if (oauthError) {
      toast.error(decodeURIComponent(oauthError));
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);

    try {
      const result = await login(email, password);
      sessionStorage.setItem("apeiro_access", result.access);
      sessionStorage.setItem("apeiro_refresh", result.refresh);
      window.location.href = "/dashboard";
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to sign in.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleOAuth(provider: OAuthProvider) {
    // Real OAuth: redirect to the provider's consent screen. Secrets stay
    // server-side; the browser only carries the short-lived code + state.
    setSsoLoading(provider);
    try {
      const result = await oauthStart(provider);
      sessionStorage.setItem("apeiro_oauth_provider", result.provider);
      window.location.href = result.authorization_url;
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "SSO sign-in failed.",
      );
      setSsoLoading(null);
    }
  }

  const ssoAvailable = providers.google.enabled || providers.github.enabled;

  return (
    <AuthLayout
      eyebrow="Welcome back"
      title="Your web watchlist is waiting."
      description="Sign in to see what changed, what is healthy, and what needs your attention."
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-semibold text-foreground hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      {ssoAvailable && (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3">
            {providers.google.enabled && (
              <button
                type="button"
                onClick={() => handleOAuth("google")}
                disabled={ssoLoading !== null}
                title="Continue with Google"
                className="apeiro-btn apeiro-btn-ghost w-full"
              >
                {ssoLoading === "google" ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                Google SSO
              </button>
            )}
            {providers.github.enabled && (
              <button
                type="button"
                onClick={() => handleOAuth("github")}
                disabled={ssoLoading !== null}
                title="Continue with GitHub"
                className="apeiro-btn apeiro-btn-ghost w-full"
              >
                {ssoLoading === "github" ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : null}
                GitHub SSO
              </button>
            )}
          </div>
          <div className="mb-5 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            or continue with email
            <span className="h-px flex-1 bg-border" />
          </div>
        </>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="you@example.com"
          required
        />

        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="••••••••"
          required
        />

        <button
          type="submit"
          disabled={loading}
          className="apeiro-btn apeiro-btn-primary w-full !py-3"
        >
          {loading ? (
            <>
              <Loader2 size={17} className="animate-spin" />
              Signing in...
            </>
          ) : (
            <>
              Sign in
              <ArrowRight size={16} />
            </>
          )}
        </button>
      </form>
    </AuthLayout>
  );
}

function AuthLayout({
  eyebrow,
  title,
  description,
  children,
  footer,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <main className="auth-shell min-h-screen">
      <div className="mx-auto grid min-h-screen max-w-6xl lg:grid-cols-2">
        <div className="auth-panel relative hidden flex-col justify-between overflow-hidden rounded-r-[2rem] p-8 lg:flex lg:p-12">
          <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-accent opacity-20 blur-3xl" />

          <Link href="/" className="relative flex items-center gap-2.5">
            <span className="modern-icon h-9 w-9 rounded-xl">
              <ShieldCheck size={19} />
            </span>
            <span className="font-semibold">Sitemyra</span>
          </Link>

          <div className="relative max-w-md">
            <div className="mb-5 h-1 w-12 rounded-full bg-accent" />

            <h2 className="font-display text-4xl font-normal tracking-tight text-white">
              Know what changed.
              <br />
              Without constantly checking.
            </h2>

            <p className="mt-5 text-sm leading-7 text-muted-foreground">
              Sitemyra quietly watches your important pages and lets you focus
              on the work that matters.
            </p>
          </div>

          <p className="relative text-xs text-muted-foreground">
            Simple monitoring. Useful alerts. Less checking.
          </p>
        </div>

        <div className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
          <div className="w-full max-w-md animate-apeiro-fade-up">
            <Link
              href="/"
              className="mb-10 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition hover:text-foreground lg:hidden"
            >
              <ArrowLeft size={15} />
              Back to Sitemyra
            </Link>

            <div className="mb-8">
              <p className="text-sm font-semibold text-success">
                {eyebrow}
              </p>

              <h1 className="mt-2 font-display text-3xl font-normal tracking-tight text-foreground">
                {title}
              </h1>

              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            </div>

            <div className="apeiro-card p-6 shadow-lg sm:p-8">{children}</div>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              {footer}
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

function Field({
  label,
  type,
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium">{label}</span>

      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        className="apeiro-input"
      />
    </label>
  );
}