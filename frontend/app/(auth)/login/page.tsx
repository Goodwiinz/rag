'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { downloadStoredNousCliAuth } from '@/services/nousCliAuth';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Database,
  Eye,
  EyeOff,
  Lock,
  Mail,
  RefreshCw,
  Shield,
  Sparkles,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { useEffect, useState } from 'react';

interface LoginFormData {
  email: string;
  password: string;
  downloadCliAuth: boolean;
}

const FEATURES = [
  { icon: Sparkles, text: 'Semantic search across everything you read' },
  { icon: Database, text: 'Multimodal documents, papers, and data' },
  { icon: Zap, text: 'Knowledge graph synthesis' },
  { icon: Shield, text: 'Cited, traceable answers' },
] as const;

function resolvePostLoginPath(rawNextPath: string | null): string {
  if (!rawNextPath || !rawNextPath.startsWith('/')) {
    return '/dashboard';
  }

  if (rawNextPath.startsWith('//')) {
    return '/dashboard';
  }

  return rawNextPath;
}

function describeAuthCallbackError(
  code: string | null,
  description: string | null
): string {
  if (!code) return '';
  if (description) return description;
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
  const callbackError = describeAuthCallbackError(
    searchParams.get('error'),
    searchParams.get('error_description')
  );
  const [formData, setFormData] = useState<LoginFormData>({
    email: '',
    password: '',
    downloadCliAuth: false,
  });
  const [error, setError] = useState<string>(callbackError);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

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
    'w-full pl-11 pr-4 py-3 rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)] transition-colors hover:border-[var(--nous-border-2)] focus-visible:outline-none focus-visible:border-[var(--nous-sol)] focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/30';

  return (
    <div className="min-h-screen flex bg-[var(--nous-bg-1)] text-[var(--nous-fg-1)] selection:bg-[var(--nous-sol)]/20">
      {/* Brand panel */}
      <aside className="hidden lg:flex lg:w-1/2 flex-col justify-center px-16 lg:px-24 border-r border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
        <div className="max-w-md">
          <p className="nous-overline mb-5">Multimodal Intelligence</p>
          <p className="nous-wordmark text-5xl mb-6">NOUS</p>
          <p className="nous-body text-lg mb-10 max-w-[60ch]">
            Turn scattered documents, papers, and data into a connected body of
            knowledge you can question, cite, and build on.
          </p>

          <ul className="space-y-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3">
                <span className="flex items-center justify-center w-8 h-8 rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-3)] text-[var(--nous-fg-accent-safe)]">
                  <Icon className="w-4 h-4" aria-hidden="true" />
                </span>
                <span className="nous-ui text-[var(--nous-fg-2)]">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex items-center justify-center px-6 py-12 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          {/* Mobile wordmark */}
          <div className="lg:hidden mb-10 text-center">
            <p className="nous-wordmark text-3xl">NOUS</p>
          </div>

          <header className="mb-8">
            <h1 className="nous-h2 mb-1">Sign in</h1>
            <p className="nous-caption">
              Welcome back. Enter your credentials to continue.
            </p>
          </header>

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {error && (
              <div
                role="alert"
                className="rounded-[var(--nous-radius-md)] border border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/10 px-3.5 py-3"
              >
                <p className="nous-ui text-sm font-semibold text-[var(--nous-mars)]">
                  We couldn&apos;t sign you in
                </p>
                <p className="nous-caption mt-0.5 text-[var(--nous-fg-2)]">
                  {error}
                </p>
              </div>
            )}

            {/* Email */}
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="nous-ui block text-sm font-medium"
              >
                Email
              </label>
              <div className="relative">
                <Mail
                  className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                  aria-hidden="true"
                />
                <input
                  id="email"
                  data-testid="email-input"
                  name="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  className={inputClass}
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
                  className="nous-ui block text-sm font-medium"
                >
                  Password
                </label>
                <Link
                  href="/forgot-password"
                  className="nous-caption rounded-sm text-[var(--nous-fg-accent-safe)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock
                  className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                  aria-hidden="true"
                />
                <input
                  id="password"
                  data-testid="password-input"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={formData.password}
                  onChange={handleChange}
                  className={cn(inputClass, 'pr-12')}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-colors focus-visible:outline-none focus-visible:text-[var(--nous-sol)]"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" aria-hidden="true" />
                  ) : (
                    <Eye className="w-4 h-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {/* CLI auth option */}
            <label
              htmlFor="downloadCliAuth"
              className="flex items-center gap-3 rounded-[var(--nous-radius-md)] border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] px-3.5 py-3 cursor-pointer"
            >
              <input
                id="downloadCliAuth"
                name="downloadCliAuth"
                type="checkbox"
                checked={formData.downloadCliAuth}
                onChange={handleChange}
                className="h-4 w-4 rounded border-[var(--nous-border-2)] text-[var(--nous-sol)] focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
              />
              <span className="nous-ui text-sm text-[var(--nous-fg-2)]">
                Download NOUS CLI auth after sign in
              </span>
            </label>

            {/* Submit */}
            <button
              type="submit"
              data-testid="login-button"
              disabled={isSubmitting}
              className={cn(
                'w-full flex items-center justify-center gap-2 py-3 px-4 rounded-[var(--nous-radius-md)]',
                'nous-ui text-sm font-semibold',
                'bg-[var(--nous-sol)] text-[var(--nous-erebus)]',
                'transition-colors hover:bg-[var(--nous-helios)] active:scale-[0.99]',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-bg-1)]',
                'disabled:opacity-60 disabled:cursor-not-allowed'
              )}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw
                    className="w-4 h-4 animate-spin"
                    aria-hidden="true"
                  />
                  <span>Signing in</span>
                </>
              ) : (
                <>
                  <span>Sign in</span>
                  <ArrowRight className="w-4 h-4" aria-hidden="true" />
                </>
              )}
            </button>
          </form>

          <p className="nous-caption mt-8 text-center">
            New to NOUS?{' '}
            <Link
              href="/register"
              className="rounded-sm font-medium text-[var(--nous-fg-accent-safe)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
            >
              Create an account
            </Link>
          </p>
        </motion.div>
      </main>
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
