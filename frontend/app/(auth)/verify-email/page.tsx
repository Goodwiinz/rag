'use client';

import { createClient } from '@/lib/supabase/client';
import { motion } from 'framer-motion';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useState } from 'react';

type VerifyStatus = 'verifying' | 'success' | 'error';

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<VerifyStatus>('verifying');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const tokenHash = searchParams.get('token_hash');
  const type = searchParams.get('type');

  useEffect(() => {
    if (!tokenHash || !type) {
      setStatus('success');
      return;
    }

    const verify = async () => {
      try {
        const supabase = createClient();
        const { error } = await supabase.auth.verifyOtp({
          token_hash: tokenHash,
          type: type as 'signup' | 'email',
        });
        if (error) throw error;
        setStatus('success');
      } catch (err) {
        setStatus('error');
        setErrorMessage(
          err instanceof Error ? err.message : 'Verification failed'
        );
      }
    };

    verify();
  }, [tokenHash, type]);

  useEffect(() => {
    if (status !== 'success') return;
    const timer = setTimeout(() => router.push('/login'), 4000);
    return () => clearTimeout(timer);
  }, [status, router]);

  const handleResend = useCallback(async () => {
    setErrorMessage('Please return to the registration page to resend.');
  }, []);

  if (status === 'verifying') {
    return (
      <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
        <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6">
          <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin" />
        </div>
        <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
          Verifying Identity
        </h2>
        <p className="text-sm font-mono text-[var(--terminal-text-muted)] leading-relaxed">
          Please wait while we confirm your email...
        </p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
        <div className="flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 mx-auto mb-6">
          <AlertCircle className="w-8 h-8 text-red-400" />
        </div>
        <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
          Verification Failed
        </h2>
        <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-6 leading-relaxed">
          {errorMessage || 'The verification link may have expired or already been used.'}
        </p>
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={handleResend}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] font-mono text-xs font-bold uppercase tracking-[0.15em] text-[var(--terminal-text-muted)] hover:border-[var(--phosphor-green)]/50 hover:text-[var(--phosphor-green)] transition-all"
          >
            Resend Verification
          </button>
          <Link
            href="/register"
            className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
          >
            Return to Registration
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6">
        <CheckCircle className="w-8 h-8 text-[var(--phosphor-green)]" />
      </div>
      <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
        Identity Verified
      </h2>
      <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-6 leading-relaxed">
        Your account has been activated. Redirecting to login...
      </p>
      <div className="h-1 w-24 mx-auto rounded-full bg-[var(--terminal-border)] overflow-hidden mb-6">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: '100%' }}
          transition={{ duration: 4 }}
          className="h-full bg-[var(--phosphor-green)]"
        />
      </div>
      <Link
        href="/login"
        className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
      >
        Go to Access Terminal
      </Link>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full mx-6"
      >
        <Suspense
          fallback={
            <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
              <Loader2 className="w-8 h-8 text-[var(--phosphor-green)] animate-spin mx-auto" />
            </div>
          }
        >
          <VerifyEmailContent />
        </Suspense>
      </motion.div>
    </div>
  );
}
