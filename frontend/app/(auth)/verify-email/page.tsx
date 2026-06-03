'use client';

import { useAuth } from '@/hooks/useAuth';
import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { Suspense, useEffect, useRef, useState } from 'react';

const VERIFIED_REDIRECT_PATH = '/dashboard';
const VERIFIED_REDIRECT_DELAY_MS = 2500;
const PENDING_AUTH_TIMEOUT_MS = 6000;

type ViewState = 'pending' | 'verified' | 'error';

function describeError(
  code: string | null,
  description: string | null
): string {
  if (description) return description;
  switch (code) {
    case 'access_denied':
      return 'The confirmation link was rejected. It may have expired or already been used.';
    case 'otp_expired':
    case 'expired_link':
      return 'This confirmation link has expired. Request a new one from the registration screen.';
    case 'exchange_failed':
      return 'We could not exchange the confirmation code for a session. The link may be invalid.';
    case 'missing_code':
      return 'No verification code was provided. Open the link from the confirmation email.';
    case 'otp_verification_failed':
      return 'We could not verify this confirmation link. It may have expired or already been used.';
    default:
      return 'We could not verify your account from this link.';
  }
}

function VerifyEmailContent(): React.JSX.Element | null {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();

  const errorCode = searchParams.get('error');
  const errorDescription = searchParams.get('error_description');
  const tokenHash = searchParams.get('token_hash');
  const tokenType = searchParams.get('type');

  const [mounted, setMounted] = useState(false);
  const [view, setView] = useState<ViewState>(errorCode ? 'error' : 'pending');
  const [otpErrorMessage, setOtpErrorMessage] = useState<string | null>(null);
  const isAuthenticatedRef = useRef(isAuthenticated);
  isAuthenticatedRef.current = isAuthenticated;

  useEffect(() => {
    setMounted(true);
  }, []);

  // Magic-link / token_hash flow: run verifyOtp client-side. Supabase only
  // sends these params when the email template is configured for the OTP
  // (non-PKCE) flow; the PKCE flow goes through /auth/callback instead.
  useEffect(() => {
    if (errorCode) return;
    if (!tokenHash || !tokenType) return;

    let cancelled = false;
    (async () => {
      try {
        const supabase = createClient();
        const { error } = await supabase.auth.verifyOtp({
          token_hash: tokenHash,
          type: tokenType as 'signup' | 'email',
        });
        if (cancelled) return;
        if (error) {
          setOtpErrorMessage(error.message);
          setView('error');
          return;
        }
        setView('verified');
      } catch (err) {
        if (cancelled) return;
        setOtpErrorMessage(
          err instanceof Error ? err.message : 'Verification failed'
        );
        setView('error');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [errorCode, tokenHash, tokenType]);

  // PKCE flow: /auth/callback already exchanged the code, so we just need
  // to wait for the auth state to propagate.
  useEffect(() => {
    if (errorCode) {
      setView('error');
      return;
    }

    // Token-hash flow drives its own state above.
    if (tokenHash && tokenType) return;

    if (isLoading) return;

    if (isAuthenticated) {
      setView('verified');
      return;
    }

    // Auth finished loading but no session — give the SIGNED_IN listener
    // a brief window in case it is still propagating, then show an error.
    const timer = setTimeout(() => {
      if (!isAuthenticatedRef.current) {
        setView('error');
      }
    }, PENDING_AUTH_TIMEOUT_MS);

    return () => clearTimeout(timer);
  }, [errorCode, tokenHash, tokenType, isAuthenticated, isLoading]);

  // Once verified, redirect to the dashboard.
  useEffect(() => {
    if (view !== 'verified') return;
    const timer = setTimeout(
      () => router.push(VERIFIED_REDIRECT_PATH),
      VERIFIED_REDIRECT_DELAY_MS
    );
    return () => clearTimeout(timer);
  }, [view, router]);

  if (!mounted) return null;

  if (view === 'error') {
    const message =
      otpErrorMessage ?? describeError(errorCode, errorDescription);
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          <div className="rounded-2xl border border-border bg-card p-10 text-center shadow-sm">
            <div className="flex items-center justify-center w-14 h-14 rounded-full bg-destructive/10 border border-destructive/30 mx-auto mb-6">
              <AlertTriangle
                className="w-7 h-7 text-destructive"
                aria-hidden="true"
              />
            </div>
            <h1 className="text-2xl font-semibold text-foreground mb-3">
              We couldn&apos;t confirm your email
            </h1>
            <p
              role="alert"
              className="text-sm text-muted-foreground mb-8 leading-relaxed"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              {message}
            </p>
            <div className="flex flex-col gap-4 items-center">
              <Link
                href="/register"
                className="inline-flex items-center justify-center w-full rounded-xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                Request a new confirmation link
              </Link>
              <Link
                href="/login"
                className="text-sm text-muted-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded"
              >
                Back to sign in
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  if (view === 'pending') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          <div className="rounded-2xl border border-border bg-card p-10 text-center shadow-sm">
            <div className="flex items-center justify-center w-14 h-14 rounded-full bg-primary/10 border border-primary/30 mx-auto mb-6">
              <Loader2
                className="w-7 h-7 text-primary motion-safe:animate-spin"
                aria-hidden="true"
              />
            </div>
            <h1 className="text-2xl font-semibold text-foreground mb-3">
              Confirming your email
            </h1>
            <p
              role="status"
              className="text-sm text-muted-foreground leading-relaxed"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Setting up your session. This only takes a moment.
            </p>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md"
      >
        <div className="rounded-2xl border border-border bg-card p-10 text-center shadow-sm">
          <div className="flex items-center justify-center w-14 h-14 rounded-full bg-primary/10 border border-primary/30 mx-auto mb-6">
            <CheckCircle2 className="w-7 h-7 text-primary" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-3">
            Your email is confirmed
          </h1>
          <p
            role="status"
            className="text-sm text-muted-foreground mb-6 leading-relaxed"
            style={{ fontFamily: 'var(--nous-font-body)' }}
          >
            Your account is active. Taking you to your workspace.
          </p>
          <div className="h-1 w-24 mx-auto rounded-full bg-muted overflow-hidden mb-8">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: '100%' }}
              transition={{ duration: VERIFIED_REDIRECT_DELAY_MS / 1000 }}
              className="h-full bg-primary"
            />
          </div>
          <Link
            href={VERIFIED_REDIRECT_PATH}
            className="inline-flex items-center justify-center w-full rounded-xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Go to workspace
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

export default function VerifyEmailPage(): React.JSX.Element {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
