'use client';

import { ThemeToggle } from '@/components/ui/theme-toggle';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { downloadStoredNousCliAuth } from '@/services/nousCliAuth';
import { getSafeAuthRedirect } from '@/utils/authRedirect';
import { motion } from 'framer-motion';
import { Lock, Mail } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { useEffect, useState } from 'react';

const ArrowRight = dynamic(
  () => import('lucide-react').then((mod) => mod.ArrowRight),
  { ssr: false }
);
const Database = dynamic(
  () => import('lucide-react').then((mod) => mod.Database),
  { ssr: false }
);
const Eye = dynamic(() => import('lucide-react').then((mod) => mod.Eye), {
  ssr: false,
});
const EyeOff = dynamic(() => import('lucide-react').then((mod) => mod.EyeOff), {
  ssr: false,
});

interface LoginFormData {
  email: string;
  password: string;
  downloadCliAuth: boolean;
}

const CAPABILITIES = [
  'Semantic search across your sources',
  'Multimodal document understanding',
  'Knowledge graph synthesis',
  'Private by default, yours to control',
];

function resolvePostLoginPath(rawNextPath: string | null): string {
  if (!rawNextPath || !rawNextPath.startsWith('/')) {
    return '/dashboard';
  }

  // SECURITY: a hand-rolled "starts with / but not //" check is not enough —
  // `/\evil.com` passes it, and WHATWG URL parsing (what the browser applies
  // when the router resolves the href) treats `/\` exactly like `//`, so the
  // push lands off-origin. Delegate to the single shared sanitizer that the
  // server-side auth callback already uses instead of writing a second one.
  const origin =
    typeof window === 'undefined' ? 'http://localhost' : window.location.origin;

  return getSafeAuthRedirect(rawNextPath, origin, '/dashboard');
}

function describeAuthCallbackError(code: string | null): string {
  // SECURITY (audit #23): never reflect the raw error_description from the
  // redirect URL — it's attacker-controlled and would render a fabricated
  // message verbatim. Map the known error CODE to a hardcoded message only.
  if (!code) return '';
  switch (code) {
    case 'auth_callback_failed':
      return 'Authentication callback failed. Please try signing in again.';
    case 'access_denied':
      return 'The confirmation link was rejected. It may have expired or already been used.';
    case 'otp_expired':
    case 'expired_link':
      return 'This confirmation link has expired. Request a new one from registration.';
    case 'exchange_failed':
      return 'We could not establish a session from the confirmation link.';
    case 'missing_code':
      return 'The confirmation link is missing its verification code.';
    default:
      return 'Authentication failed.';
  }
}

function LoginPageContent(): React.JSX.Element | null {
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = resolvePostLoginPath(searchParams.get('next'));
  const callbackError = describeAuthCallbackError(searchParams.get('error'));
  const [formData, setFormData] = useState<LoginFormData>({
    email: '',
    password: '',
    downloadCliAuth: false,
  });
  const [error, setError] = useState<string>(callbackError);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push(nextPath);
    }
  }, [isAuthenticated, isLoading, nextPath, router]);

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login(formData.email, formData.password);
      if (formData.downloadCliAuth) {
        try {
          downloadStoredNousCliAuth();
        } catch (downloadError) {
          console.error('Failed to export NOUS CLI auth:', downloadError);
        }
      }
      router.push(nextPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]:
        e.target.type === 'checkbox' ? e.target.checked : e.target.value,
    }));
  };

  const inputClass =
    'w-full rounded-(--nous-radius-md) border border-(--nous-border-1) bg-(--nous-bg-1) py-3 text-sm text-(--nous-fg-1) placeholder:text-(--nous-fg-3) outline-hidden transition-colors focus-visible:border-(--nous-sol) focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40';

  const Brand = (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-(--nous-radius-md) border border-(--nous-border-1) bg-(--nous-bg-2)">
        <span
          aria-hidden="true"
          className="text-base font-semibold text-(--nous-sol)"
        >
          N
        </span>
      </div>
      <span className="text-lg font-semibold tracking-[0.04em] text-(--nous-fg-1)">
        NOUS
      </span>
    </div>
  );

  // SSR-friendly skeleton to keep LCP stable while hydrating.
  if (!mounted) {
    return (
      <div className="flex min-h-screen bg-(--nous-bg-1) text-(--nous-fg-1)">
        <div className="hidden flex-col justify-center border-r border-(--nous-border-1) px-16 lg:flex lg:w-1/2 lg:px-24">
          <div className="mb-12">{Brand}</div>
          <h1 className="mb-6 max-w-md text-4xl font-semibold leading-tight tracking-tight text-(--nous-fg-1)">
            Turn your sources into answers you can trust.
          </h1>
          <p
            className="max-w-md text-base leading-relaxed text-(--nous-fg-2)"
            style={{ fontFamily: 'var(--nous-font-body)' }}
          >
            NOUS reads your documents the way a careful researcher would, and
            shows its work.
          </p>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 lg:px-8">
          <div className="w-full max-w-md">
            <div className="rounded-(--nous-radius-xl) border border-(--nous-border-1) bg-(--nous-bg-2) p-8">
              <h2 className="mb-6 text-xl font-semibold text-(--nous-fg-1)">
                Sign in
              </h2>
              <div className="space-y-5">
                <div className="h-12 rounded-(--nous-radius-md) bg-(--nous-bg-1)" />
                <div className="h-12 rounded-(--nous-radius-md) bg-(--nous-bg-1)" />
                <div className="h-12 rounded-(--nous-radius-md) bg-(--nous-sol)/20" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-screen bg-(--nous-bg-1) text-(--nous-fg-1)">
      <div className="absolute right-4 top-4 z-10 sm:right-6 sm:top-6">
        <ThemeToggle />
      </div>
      {/* Left panel — editorial */}
      <div className="hidden flex-col justify-center border-r border-(--nous-border-1) px-16 lg:flex lg:w-1/2 lg:px-24">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="mb-12">{Brand}</div>

          <h1 className="mb-6 max-w-lg text-4xl font-semibold leading-tight tracking-tight text-(--nous-fg-1)">
            Turn your sources into answers you can trust.
          </h1>
          <p
            className="mb-10 max-w-md text-base leading-relaxed text-(--nous-fg-2)"
            style={{ fontFamily: 'var(--nous-font-body)' }}
          >
            NOUS reads your documents the way a careful researcher would, and
            shows its work. Sign in to pick up where you left off.
          </p>

          <ul className="space-y-3">
            {CAPABILITIES.map((text, i) => (
              <li key={i} className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-(--nous-radius-sm) border border-(--nous-border-1) bg-(--nous-bg-2)"
                >
                  <Database className="h-3.5 w-3.5 text-(--nous-sol)" />
                </span>
                <span className="text-sm text-(--nous-fg-2)">{text}</span>
              </li>
            ))}
          </ul>
        </motion.div>
      </div>

      {/* Right panel — sign-in form */}
      <div className="flex flex-1 items-center justify-center px-6 lg:px-8">
        <div className="w-full max-w-md">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            {/* Mobile brand */}
            <div className="mb-8 flex justify-center lg:hidden">{Brand}</div>

            <div className="rounded-(--nous-radius-xl) border border-(--nous-border-1) bg-(--nous-bg-2) p-8 shadow-(--nous-shadow-xl)">
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-(--nous-fg-1)">
                  Sign in
                </h2>
                <p className="mt-1 text-sm text-(--nous-fg-3)">
                  Welcome back to NOUS.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div
                    role="alert"
                    className="rounded-(--nous-radius-md) border border-(--nous-mars)/40 bg-(--nous-mars)/10 p-3"
                  >
                    <p className="text-sm text-(--nous-mars)">{error}</p>
                  </div>
                )}

                {/* Email */}
                <div className="space-y-1.5">
                  <label
                    htmlFor="email"
                    className="block text-sm font-medium text-(--nous-fg-2)"
                  >
                    Email
                  </label>
                  <div className="relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <Mail
                        aria-hidden="true"
                        className="h-4 w-4 text-(--nous-fg-3)"
                      />
                    </div>
                    <input
                      id="email"
                      data-testid="email-input"
                      name="email"
                      type="email"
                      required
                      value={formData.email}
                      onChange={handleChange}
                      className={cn(inputClass, 'pl-11 pr-4')}
                      placeholder="you@example.com"
                      autoComplete="email"
                    />
                  </div>
                </div>

                {/* Password */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor="password"
                      className="block text-sm font-medium text-(--nous-fg-2)"
                    >
                      Password
                    </label>
                    <Link
                      href="/forgot-password"
                      className="rounded-sm text-sm text-(--nous-sol) underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                      <Lock
                        aria-hidden="true"
                        className="h-4 w-4 text-(--nous-fg-3)"
                      />
                    </div>
                    <input
                      id="password"
                      data-testid="password-input"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={formData.password}
                      onChange={handleChange}
                      className={cn(inputClass, 'pl-11 pr-12')}
                      placeholder="Your password"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 flex items-center rounded-sm pr-3.5 text-(--nous-fg-3) transition-colors hover:text-(--nous-sol) focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40"
                      aria-label={
                        showPassword ? 'Hide password' : 'Show password'
                      }
                    >
                      {showPassword ? (
                        <EyeOff aria-hidden="true" className="h-4 w-4" />
                      ) : (
                        <Eye aria-hidden="true" className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* CLI auth export */}
                <label
                  htmlFor="downloadCliAuth"
                  className="flex cursor-pointer items-start gap-3 rounded-(--nous-radius-md) border border-(--nous-border-1) bg-(--nous-bg-1) px-3.5 py-3"
                >
                  <input
                    id="downloadCliAuth"
                    name="downloadCliAuth"
                    type="checkbox"
                    checked={formData.downloadCliAuth}
                    onChange={handleChange}
                    className="mt-0.5 h-4 w-4 rounded border-(--nous-border-1) bg-(--nous-bg-1) accent-(--nous-sol) focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40"
                  />
                  <span className="text-sm leading-snug text-(--nous-fg-2)">
                    Download NOUS CLI credentials after signing in
                    <span className="mt-0.5 block text-xs text-(--nous-fg-3)">
                      Optional
                    </span>
                  </span>
                </label>

                {/* Submit */}
                <button
                  type="submit"
                  data-testid="login-button"
                  disabled={isSubmitting}
                  className="group flex w-full items-center justify-center gap-2 rounded-(--nous-radius-md) bg-(--nous-sol) py-3 text-sm font-semibold text-(--nous-erebus) transition-colors hover:bg-(--nous-helios) focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol) focus-visible:ring-offset-2 focus-visible:ring-offset-(--nous-bg-2) disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isSubmitting ? (
                    <span>Signing in…</span>
                  ) : (
                    <>
                      <span>Sign in</span>
                      <ArrowRight
                        aria-hidden="true"
                        className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                      />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-6 border-t border-(--nous-border-1) pt-5 text-center text-sm text-(--nous-fg-3)">
                New to NOUS?{' '}
                <Link
                  href="/register"
                  className="rounded-sm font-medium text-(--nous-sol) underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40"
                >
                  Create an account
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage(): React.JSX.Element {
  return (
    <React.Suspense fallback={null}>
      <LoginPageContent />
    </React.Suspense>
  );
}
