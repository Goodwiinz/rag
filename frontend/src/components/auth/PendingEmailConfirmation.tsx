'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { Mail, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

interface PendingEmailConfirmationProps {
  email: string;
  onReset: () => void;
}

export default function PendingEmailConfirmation({
  email,
  onReset,
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
    if (resendCooldown > 0) return;
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
    <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
          {/* Animated mail icon */}
          <motion.div
            animate={{ scale: [1, 1.05, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/30 mx-auto mb-6"
          >
            <Mail className="w-8 h-8 text-[var(--nous-sol)]" />
          </motion.div>

          <h2 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-[0.15em] mb-3">
            Verify Your Identity
          </h2>

          <p className="text-sm font-mono text-[var(--nous-fg-3)] mb-8 leading-relaxed">
            We sent a verification link to{' '}
            <span className="text-[var(--nous-sol)]">{email}</span>. Check
            your inbox and click the link to activate your account.
          </p>

          {/* Resend button */}
          <button
            onClick={handleResend}
            disabled={resendCooldown > 0 || resendStatus === 'sending'}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)] font-mono text-xs font-bold uppercase tracking-[0.15em] text-[var(--nous-fg-3)] hover:border-[var(--nous-sol)]/50 hover:text-[var(--nous-sol)] disabled:opacity-40 disabled:cursor-not-allowed transition-all mb-4"
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

          {/* Resend status feedback */}
          {resendStatus === 'sent' && resendCooldown > 0 && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[10px] font-mono text-[var(--nous-sol)] mb-4"
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
              className="text-[10px] font-mono text-[var(--nous-fg-3)] mb-6"
            >
              Not seeing it? Check your spam or junk folder.
            </motion.p>
          )}

          {/* Wrong email / back links */}
          <div className="flex flex-col items-center gap-3 pt-4 border-t border-[var(--nous-border-1)]">
            <button
              onClick={onReset}
              className="text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-widest hover:text-[var(--nous-sol)] transition-colors"
            >
              Wrong email? Try again
            </button>
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
