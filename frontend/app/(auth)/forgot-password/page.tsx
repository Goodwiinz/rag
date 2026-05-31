'use client';

import { createClient } from '@/lib/supabase/client';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { ArrowLeft, Mail } from 'lucide-react';
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
      <div className="min-h-screen flex items-center justify-center bg-background px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          <div className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
            <div
              className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary"
              aria-hidden="true"
            >
              <Mail className="h-6 w-6" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Check your inbox
            </h1>
            <p
              className="mt-3 text-[15px] leading-relaxed text-muted-foreground"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              If an account exists for{' '}
              <span className="font-medium text-foreground">{email}</span>, a
              password reset link is on its way. Follow it to choose a new
              password.
            </p>
            <Link
              href="/login"
              className="mt-8 inline-flex items-center gap-2 rounded-md text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to sign in
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md"
      >
        <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
          <div className="mb-8">
            <div
              className="mb-5 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary"
              aria-hidden="true"
            >
              <Mail className="h-5 w-5" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Reset your password
            </h1>
            <p
              className="mt-2 text-[15px] leading-relaxed text-muted-foreground"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Enter the email address linked to your account and we will send
              you a link to set a new password.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/5 px-3.5 py-2.5"
              >
                <p className="text-sm text-destructive">{error}</p>
              </motion.div>
            )}

            <div className="space-y-2">
              <label
                htmlFor="email"
                className="block text-sm font-medium text-foreground"
              >
                Email address
              </label>
              <div className="relative">
                <div
                  className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground"
                  aria-hidden="true"
                >
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  aria-describedby="email-hint"
                  className="w-full rounded-md border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/70 transition-colors focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </div>
              <p id="email-hint" className="text-xs text-muted-foreground">
                We will only use this to send your reset link.
              </p>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                'w-full rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground',
                'transition-colors hover:bg-primary/90',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                'disabled:cursor-not-allowed disabled:opacity-60'
              )}
            >
              {isSubmitting ? 'Sending...' : 'Send reset link'}
            </button>
          </form>

          <div className="mt-8 border-t border-border pt-6 text-center">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-md text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to sign in
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
