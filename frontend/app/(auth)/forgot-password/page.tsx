'use client';

import { supabase } from '@/lib/supabase';
import { cn } from '@/lib/utils';
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
      <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full mx-6"
        >
          <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-10 text-center">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/30 mx-auto mb-6">
              <Mail className="w-8 h-8 text-[var(--phosphor-green)]" />
            </div>
            <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.15em] mb-3">
              Reset Link Sent
            </h2>
            <p className="text-sm font-mono text-[var(--terminal-text-muted)] mb-8 leading-relaxed">
              We sent a password reset link to{' '}
              <span className="text-[var(--phosphor-green)]">{email}</span>.
              Check your inbox and follow the instructions.
            </p>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
            >
              <ArrowLeft className="w-3 h-3" />
              Return to Access Terminal
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--terminal-bg)] relative overflow-hidden">
      <div className="absolute inset-0 opacity-[0.02] pointer-events-none">
        <div
          className="h-full w-full"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
          }}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md mx-6"
      >
        <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-8 shadow-2xl shadow-black/50">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] mb-4">
              <Lock className="w-5 h-5 text-[var(--phosphor-green)]" />
            </div>
            <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.2em]">
              Key Recovery
            </h2>
            <p className="text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider mt-2">
              Enter your identity protocol to receive a reset link
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-red-500/30 bg-red-500/5 p-3"
              >
                <p className="text-[10px] font-mono text-red-400 font-bold uppercase tracking-tighter">
                  Recovery Error: {error}
                </p>
              </motion.div>
            )}

            <div className="space-y-2">
              <label
                htmlFor="email"
                className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1"
              >
                Identity Protocol
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <Mail className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                  placeholder="UID@DOMAIN.COM"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                'group w-full flex items-center justify-center gap-3 py-3.5 px-4 rounded-xl font-mono text-xs font-bold uppercase tracking-[0.2em]',
                'bg-[var(--phosphor-green)] text-[var(--terminal-bg)]',
                'hover:shadow-[0_0_25px_var(--phosphor-green-glow)] hover:scale-[1.02] active:scale-[0.98]',
                'disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300'
              )}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Transmitting...</span>
                </>
              ) : (
                <>
                  <span>Send Reset Link</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-[var(--terminal-border)] text-center">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
            >
              <ArrowLeft className="w-3 h-3" />
              Return to Access Terminal
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
