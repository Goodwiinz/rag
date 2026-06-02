'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Eye,
  EyeOff,
  Lock,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useRef, useState } from 'react';

const SESSION_TIMEOUT_MS = 5000;
const NOUS_EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const sessionDetected = useRef(false);

  useEffect(() => {
    setMounted(true);

    const supabase = createClient();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') {
        sessionDetected.current = true;
        setSessionReady(true);
      }
    });

    const timeout = setTimeout(() => {
      if (!sessionDetected.current) {
        setSessionExpired(true);
      }
    }, SESSION_TIMEOUT_MS);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError("Passwords don't match");
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      const supabase = createClient();
      const { error: updateError } = await supabase.auth.updateUser({
        password,
      });

      if (updateError) {
        throw new Error(updateError.message);
      }

      setSuccess(true);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!mounted) return null;

  if (sessionExpired) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--nous-bg-1)] px-6">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: NOUS_EASE }}
          className="w-full max-w-md"
        >
          <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/10">
              <AlertTriangle
                className="h-6 w-6 text-[var(--nous-mars)]"
                strokeWidth={1.8}
              />
            </div>
            <h1
              className="mb-3 text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              This link has expired
            </h1>
            <p
              className="mx-auto mb-7 max-w-xs text-[0.9375rem] leading-relaxed text-[var(--nous-fg-2)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              The reset link is expired or invalid. Request a new one to
              continue.
            </p>
            <Link
              href="/forgot-password"
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--nous-sol)] px-5 py-3 text-sm font-medium text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <span>Request a new link</span>
              <ArrowRight className="h-4 w-4" strokeWidth={1.8} />
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  if (!sessionReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--nous-bg-1)] px-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <RefreshCw className="mx-auto mb-4 h-6 w-6 animate-spin text-[var(--nous-sol)]" />
          <p
            className="text-sm text-[var(--nous-fg-3)]"
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            Verifying recovery link…
          </p>
        </motion.div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--nous-bg-1)] px-6">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: NOUS_EASE }}
          className="w-full max-w-md"
        >
          <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[var(--nous-sol)]/30 bg-[var(--nous-sol)]/10">
              <CheckCircle
                className="h-6 w-6 text-[var(--nous-sol)]"
                strokeWidth={1.8}
              />
            </div>
            <h1
              className="mb-3 text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              Password updated
            </h1>
            <p
              className="mb-5 text-[0.9375rem] leading-relaxed text-[var(--nous-fg-2)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Redirecting to sign in…
            </p>
            <div className="mx-auto h-1 w-24 overflow-hidden rounded-full bg-[var(--nous-border-1)]">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: '100%' }}
                transition={{ duration: 3, ease: 'linear' }}
                className="h-full bg-[var(--nous-sol)]"
              />
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--nous-bg-1)] px-6">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: NOUS_EASE }}
        className="w-full max-w-md"
      >
        <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-8">
          <div className="mb-7">
            <div className="mb-5 inline-flex h-11 w-11 items-center justify-center rounded-full border border-[var(--nous-border-1)] bg-[var(--nous-bg-3)]">
              <Lock
                className="h-5 w-5 text-[var(--nous-sol)]"
                strokeWidth={1.8}
              />
            </div>
            <h1
              className="text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              Set a new password
            </h1>
            <p
              className="mt-2 text-[0.9375rem] leading-relaxed text-[var(--nous-fg-2)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              At least 8 characters.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {error && (
              <motion.div
                role="alert"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/5 p-3"
              >
                <p
                  className="text-sm text-[var(--nous-mars)]"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                >
                  {error}
                </p>
              </motion.div>
            )}

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-sm font-medium text-[var(--nous-fg-2)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                New password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                  <Lock
                    className="h-4 w-4 text-[var(--nous-fg-3)]"
                    strokeWidth={1.8}
                  />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="w-full rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] py-3 pl-11 pr-12 text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)]/50 outline-none transition-colors focus-visible:border-[var(--nous-sol)]/50 focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/30"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--nous-fg-3)] transition-colors hover:text-[var(--nous-fg-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" strokeWidth={1.8} />
                  ) : (
                    <Eye className="h-4 w-4" strokeWidth={1.8} />
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-[var(--nous-fg-2)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Confirm password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                  <Lock
                    className="h-4 w-4 text-[var(--nous-fg-3)]"
                    strokeWidth={1.8}
                  />
                </div>
                <input
                  id="confirmPassword"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat the password"
                  className="w-full rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] py-3 pl-11 pr-4 text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)]/50 outline-none transition-colors focus-visible:border-[var(--nous-sol)]/50 focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/30"
                  style={{ fontFamily: 'var(--nous-font-ui)' }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="group flex w-full items-center justify-center gap-2 rounded-xl bg-[var(--nous-sol)] px-4 py-3 text-sm font-medium text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw
                    className="h-4 w-4 animate-spin"
                    strokeWidth={1.8}
                  />
                  <span>Updating…</span>
                </>
              ) : (
                <>
                  <span>Update password</span>
                  <ArrowRight
                    className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                    strokeWidth={1.8}
                  />
                </>
              )}
            </button>
          </form>

          <div className="mt-7 border-t border-[var(--nous-border-1)] pt-5 text-center">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-sm text-[var(--nous-fg-3)] transition-colors hover:text-[var(--nous-fg-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 rounded"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Back to sign in
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
