'use client';

import { useAuth } from '@/hooks/useAuth';
import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
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
      <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full mx-6"
        >
          <div className="rounded-2xl border border-red-500/30 bg-[var(--nous-bg-2)] p-10 text-center">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 mx-auto mb-6">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-[0.15em] mb-3">
              Verification Failed
            </h2>
            <p className="text-sm font-mono text-[var(--nous-fg-3)] mb-8 leading-relaxed">
              {message}
            </p>
            <div className="flex flex-col gap-3 items-center">
              <Link
                href="/register"
                className="text-[10px] font-mono text-[var(--nous-sol)] uppercase tracking-widest hover:underline"
              >
                Request a new confirmation link
              </Link>
              <Link
                href="/login"
                className="text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-widest hover:text-[var(--nous-sol)] transition-colors"
              >
                Return to Access Terminal
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  if (view === 'pending') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full mx-6"
        >
          <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/30 mx-auto mb-6">
              <RefreshCw className="w-8 h-8 text-[var(--nous-sol)] animate-spin" />
            </div>
            <h2 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-[0.15em] mb-3">
              Verifying Identity
            </h2>
            <p className="text-sm font-mono text-[var(--nous-fg-3)] mb-8 leading-relaxed">
              Establishing your session. This only takes a moment...
            </p>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/30 mx-auto mb-6">
            <CheckCircle className="w-8 h-8 text-[var(--nous-sol)]" />
          </div>
          <h2 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-[0.15em] mb-3">
            Identity Verified
          </h2>
          <p className="text-sm font-mono text-[var(--nous-fg-3)] mb-6 leading-relaxed">
            Your account has been activated. Redirecting to your workspace...
          </p>
          <div className="h-1 w-24 mx-auto rounded-full bg-[var(--nous-border-1)] overflow-hidden mb-6">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: '100%' }}
              transition={{ duration: VERIFIED_REDIRECT_DELAY_MS / 1000 }}
              className="h-full bg-[var(--nous-sol)]"
            />
          </div>
          <Link
            href={VERIFIED_REDIRECT_PATH}
            className="text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-widest hover:text-[var(--nous-sol)] transition-colors"
          >
            Continue to Workspace
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
