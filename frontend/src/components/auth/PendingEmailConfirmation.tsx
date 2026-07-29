'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { Mail, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

interface PendingEmailConfirmationProps {
  email: string;
  onReset: () => void;
  /**
   * Signup came back with GoTrue's enumeration-protection shape, so we cannot
   * honestly promise a verification mail. Shows neutral guidance instead —
   * this must never assert that the account exists.
   */
  possiblyExisting?: boolean;
}

export default function PendingEmailConfirmation({
  email,
  onReset,
  possiblyExisting = false,
}: PendingEmailConfirmationProps) {
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendStatus, setResendStatus] = useState<
    'idle' | 'sending' | 'sent' | 'error'
  >('idle');
  const [showSpamHint, setShowSpamHint] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowSpamHint(true), 30_000);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const interval = setInterval(
      () => setResendCooldown((prev) => prev - 1),
      1000
    );
    return () => clearInterval(interval);
  }, [resendCooldown]);

  const handleResend = useCallback(async () => {
    // Defence in depth: `resend({ email: '' })` is always rejected by GoTrue,
    // so never fire it without an address (the button is disabled too).
    if (resendCooldown > 0 || !email) return;
    setResendStatus('sending');
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.resend({
        type: 'signup',
        email,
      });
      if (error) throw error;
      setResendStatus('sent');
      setResendCooldown(60);
    } catch {
      setResendStatus('error');
    }
  }, [email, resendCooldown]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-(--nous-bg-1)">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <div className="rounded-2xl border border-(--nous-border-1) bg-(--nous-bg-2) p-10 text-center">
          {/* Animated mail icon */}
          <motion.div
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="flex items-center justify-center w-16 h-16 rounded-full bg-(--nous-sol)/10 border border-(--nous-sol)/30 mx-auto mb-6"
          >
            <Mail className="w-8 h-8 text-(--nous-sol)" />
          </motion.div>

          <h2 className="text-xl font-mono font-bold text-(--nous-fg-1) uppercase tracking-[0.15em] mb-3">
            Verify Your Identity
          </h2>

          {possiblyExisting ? (
            <p className="text-sm font-mono text-(--nous-fg-3) mb-8 leading-relaxed">
              Check your inbox for{' '}
              <span className="text-(--nous-sol)">{email}</span>. If this
              address is new to NOUS, we sent a verification link. Already have
              an account? You can sign in or reset your password instead.
            </p>
          ) : (
            <p className="text-sm font-mono text-(--nous-fg-3) mb-8 leading-relaxed">
              We sent a verification link to{' '}
              <span className="text-(--nous-sol)">{email}</span>. Check your
              inbox and click the link to activate your account.
            </p>
          )}

          {possiblyExisting && (
            <div className="flex flex-col items-center gap-3 mb-4">
              <Link
                href="/login"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-(--nous-border-1) bg-(--nous-bg-1) font-mono text-xs font-bold uppercase tracking-[0.15em] text-(--nous-fg-3) hover:border-(--nous-sol)/50 hover:text-(--nous-sol) transition-all"
              >
                Sign in
              </Link>
              <Link
                href="/forgot-password"
                className="text-[10px] font-mono text-(--nous-fg-3) uppercase tracking-widest hover:text-(--nous-sol) transition-colors"
              >
                Reset your password
              </Link>
            </div>
          )}

          {/* Resend button */}
          {!possiblyExisting && (
            <button
              onClick={handleResend}
              disabled={
                !email || resendCooldown > 0 || resendStatus === 'sending'
              }
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-(--nous-border-1) bg-(--nous-bg-1) font-mono text-xs font-bold uppercase tracking-[0.15em] text-(--nous-fg-3) hover:border-(--nous-sol)/50 hover:text-(--nous-sol) disabled:opacity-40 disabled:cursor-not-allowed transition-all mb-4"
            >
              {resendStatus === 'sending' ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Sending...
                </>
              ) : resendCooldown > 0 ? (
                <>Resend in {resendCooldown}s</>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Resend Verification
                </>
              )}
            </button>
          )}

          {!email && !possiblyExisting && (
            <p className="text-[10px] font-mono text-(--nous-fg-3) mb-4">
              We no longer have the address on this device, so we cannot resend
              the link. Use &ldquo;Wrong email? Try again&rdquo; below to
              restart.
            </p>
          )}

          {/* Resend status feedback */}
          {resendStatus === 'sent' && resendCooldown > 0 && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-(--nous-sol) mb-4"
            >
              Verification email sent!
            </motion.p>
          )}
          {resendStatus === 'error' && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-red-400 mb-4"
            >
              Failed to resend. Please try again.
            </motion.p>
          )}

          {/* Spam hint */}
          {showSpamHint && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-(--nous-fg-3) mb-6"
            >
              Not seeing it? Check your spam or junk folder.
            </motion.p>
          )}

          {/* Wrong email / back links */}
          <div className="flex flex-col items-center gap-3 pt-4 border-t border-(--nous-border-1)">
            <button
              onClick={onReset}
              className="text-[10px] font-mono text-(--nous-fg-3) uppercase tracking-widest hover:text-(--nous-sol) transition-colors"
            >
              Wrong email? Try again
            </button>
            <Link
              href="/login"
              className="text-[10px] font-mono text-(--nous-fg-3) uppercase tracking-widest hover:text-(--nous-sol) transition-colors"
            >
              Return to Access Terminal
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
