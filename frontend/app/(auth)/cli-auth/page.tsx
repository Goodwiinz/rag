'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { api } from '@/services/api-client';
import { ArrowLeft, CheckCircle2, Shield } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { useEffect, useState } from 'react';

function CliAuthPageContent(): React.JSX.Element {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id') ?? '';
  const verificationCode = searchParams.get('code') ?? '';
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const next = `/cli-auth?session_id=${encodeURIComponent(sessionId)}&code=${encodeURIComponent(
        verificationCode
      )}`;
      router.push(`/login?next=${encodeURIComponent(next)}`);
    }
  }, [isAuthenticated, isLoading, router, sessionId, verificationCode]);

  const handleApprove = async (): Promise<void> => {
    if (!sessionId || !verificationCode || isSubmitting) {
      return;
    }

    setError('');
    setIsSubmitting(true);

    try {
      await api.post('/cli-auth/approve', {
        session_id: sessionId,
        verification_code: verificationCode,
      });
      setIsConnected(true);
    } catch (approveError) {
      setError(
        approveError instanceof Error
          ? approveError.message
          : 'Failed to approve NOUS CLI login.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-[var(--nous-bg-1)] text-[var(--nous-fg-1)] flex items-center justify-center px-6 py-12">
      <section className="w-full max-w-xl rounded-3xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]/95 p-8 shadow-2xl shadow-black/30">
        <div className="mb-8 flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--nous-sol)]/30 bg-[var(--nous-bg-3)]">
            <Shield className="h-6 w-6 text-[var(--nous-sol)]" />
          </div>
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.35em] text-[var(--nous-fg-3)]">
              NOUS CLI
            </p>
            <h1 className="text-2xl font-mono font-bold uppercase tracking-[0.18em]">
              Authorize Terminal Access
            </h1>
          </div>
        </div>

        <div className="mb-8 space-y-4 rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/70 p-5 font-mono">
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-[var(--nous-fg-3)]">
              Session ID
            </p>
            <p className="mt-2 break-all text-sm">{sessionId || 'missing-session-id'}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.3em] text-[var(--nous-fg-3)]">
              Verification Code
            </p>
            <p className="mt-2 text-lg tracking-[0.35em] text-[var(--nous-sol)]">
              {verificationCode || 'MISSING'}
            </p>
          </div>
        </div>

        <p className="mb-8 max-w-lg text-sm leading-7 text-[var(--nous-fg-3)]">
          Approve this request to let the NOUS command line connect to your current account and
          organization.
        </p>

        {isConnected ? (
          <div className="rounded-2xl border border-[var(--nous-sol)]/30 bg-[var(--nous-sol)]/10 p-5 font-mono">
            <p className="text-sm font-bold uppercase tracking-[0.22em] text-[var(--nous-sol)]">
              CLI connected, return to terminal.
            </p>
            <p className="mt-3 text-sm leading-7 text-[var(--nous-fg-3)]">
              The pending NOUS terminal session can finish sign-in automatically now.
            </p>
          </div>
        ) : null}

        {error ? (
          <div className="mb-6 rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <div className="flex flex-col gap-4 sm:flex-row">
          <button
            type="button"
            onClick={handleApprove}
            disabled={!sessionId || !verificationCode || isSubmitting || isConnected}
            className={cn(
              'inline-flex min-h-12 flex-1 items-center justify-center gap-3 rounded-2xl border border-[var(--nous-sol)]/30',
              'bg-[var(--nous-sol)]/90 px-5 font-mono text-sm font-bold uppercase tracking-[0.22em] text-[var(--nous-bg-1)]',
              'transition hover:bg-[var(--nous-sol)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]',
              'disabled:cursor-not-allowed disabled:opacity-60'
            )}
          >
            <CheckCircle2 className="h-4 w-4" />
            {isSubmitting ? 'Approving...' : 'Approve CLI Login'}
          </button>
          <Link
            href="/login"
            className={cn(
              'inline-flex min-h-12 flex-1 items-center justify-center gap-3 rounded-2xl border border-[var(--nous-border-1)]',
              'bg-transparent px-5 font-mono text-sm font-bold uppercase tracking-[0.22em] text-[var(--nous-fg-3)]',
              'transition hover:border-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)]'
            )}
          >
            <ArrowLeft className="h-4 w-4" />
            Cancel
          </Link>
        </div>
      </section>
    </main>
  );
}

export default function CliAuthPage(): React.JSX.Element {
  return (
    <React.Suspense fallback={null}>
      <CliAuthPageContent />
    </React.Suspense>
  );
}
