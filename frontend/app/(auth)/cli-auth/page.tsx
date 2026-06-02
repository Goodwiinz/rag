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
    <main className="flex min-h-screen items-center justify-center bg-[var(--nous-bg-1)] px-6 py-12 text-[var(--nous-fg-1)]">
      <section className="w-full max-w-xl rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-8">
        <div className="mb-7 flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-[var(--nous-sol)]/30 bg-[var(--nous-bg-3)]">
            <Shield
              className="h-5 w-5 text-[var(--nous-sol)]"
              strokeWidth={1.8}
            />
          </div>
          <div>
            <p
              className="text-xs font-medium text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              NOUS CLI
            </p>
            <h1
              className="text-2xl font-semibold tracking-tight text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-heading)' }}
            >
              Authorize CLI access
            </h1>
          </div>
        </div>

        <p
          className="mb-6 max-w-lg text-[0.9375rem] leading-relaxed text-[var(--nous-fg-2)]"
          style={{ fontFamily: 'var(--nous-font-body)' }}
        >
          Approve this request to let the NOUS command line connect to your
          current account and organization.
        </p>

        <dl className="mb-8 space-y-4 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/60 p-5">
          <div>
            <dt
              className="text-xs font-medium text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Session ID
            </dt>
            <dd
              className="mt-1.5 break-all text-sm text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              {sessionId || 'missing-session-id'}
            </dd>
          </div>
          <div>
            <dt
              className="text-xs font-medium text-[var(--nous-fg-3)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              Verification code
            </dt>
            <dd
              className="mt-1.5 text-lg tracking-[0.25em] text-[var(--nous-fg-accent)]"
              style={{ fontFamily: 'var(--nous-font-mono)' }}
            >
              {verificationCode || 'missing'}
            </dd>
          </div>
        </dl>

        {isConnected ? (
          <div className="mb-6 rounded-xl border border-[var(--nous-sol)]/30 bg-[var(--nous-sol)]/10 p-5">
            <p
              className="text-sm font-medium text-[var(--nous-fg-1)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              CLI connected. You can return to your terminal.
            </p>
            <p
              className="mt-2 text-sm leading-relaxed text-[var(--nous-fg-2)]"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              The pending NOUS terminal session will finish sign-in
              automatically.
            </p>
          </div>
        ) : null}

        {error ? (
          <div
            role="alert"
            className="mb-6 rounded-xl border border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/5 p-4"
          >
            <p
              className="text-sm text-[var(--nous-mars)]"
              style={{ fontFamily: 'var(--nous-font-ui)' }}
            >
              {error}
            </p>
          </div>
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={handleApprove}
            disabled={
              !sessionId || !verificationCode || isSubmitting || isConnected
            }
            className={cn(
              'inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl',
              'bg-[var(--nous-sol)] px-5 text-sm font-medium text-[var(--nous-erebus)]',
              'transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            <CheckCircle2 className="h-4 w-4" strokeWidth={1.8} />
            {isSubmitting ? 'Approving…' : 'Approve'}
          </button>
          <Link
            href="/login"
            className={cn(
              'inline-flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl border border-[var(--nous-border-1)]',
              'bg-transparent px-5 text-sm font-medium text-[var(--nous-fg-2)]',
              'transition-colors hover:border-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40'
            )}
            style={{ fontFamily: 'var(--nous-font-ui)' }}
          >
            <ArrowLeft className="h-4 w-4" strokeWidth={1.8} />
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
