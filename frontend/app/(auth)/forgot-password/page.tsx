'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Lock, Mail, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import React, { useEffect, useState } from 'react';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const supabase = createClient();
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(
        email,
        { redirectTo: `${window.location.origin}/reset-password` }
      );

      if (resetError) {
        throw new Error(resetError.message);
      }

      setSent(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to send reset link'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!mounted) return null;

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--nous-bg-1)] px-6">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
            <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[var(--nous-sol)]/30 bg-[var(--nous-sol)]/10">
              <Mail
                className="h-6 w-6 text-[var(--nous-sol)]"
                strokeWidth={1.8}
              />
            </div>
            <h1
              className="mb-3 text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              Check your email
            </h1>
            <p
              className="mx-auto mb-8 max-w-xs text-[0.9375rem] leading-relaxed text-[var(--nous-fg-2)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              We sent a reset link to{' '}
              <span className="text-[var(--nous-fg-1)]">{email}</span>. Follow
              the link to choose a new password.
            </p>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-sm text-[var(--nous-fg-3)] transition-colors hover:text-[var(--nous-fg-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 rounded"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              <ArrowLeft className="h-4 w-4" strokeWidth={1.8} />
              Back to sign in
            </Link>
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
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
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
              Reset your password
            </h1>
            <p
              className="mt-2 text-[0.9375rem] leading-relaxed text-[var(--nous-fg-2)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Enter your email and we&apos;ll send a reset link.
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
                htmlFor="email"
                className="block text-sm font-medium text-[var(--nous-fg-2)]"
                style={{ fontFamily: 'var(--nous-font-ui)' }}
              >
                Email
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                  <Mail
                    className="h-4 w-4 text-[var(--nous-fg-3)]"
                    strokeWidth={1.8}
                  />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
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
                  <span>Sending…</span>
                </>
              ) : (
                <>
                  <span>Send reset link</span>
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
              <ArrowLeft className="h-4 w-4" strokeWidth={1.8} />
              Back to sign in
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
