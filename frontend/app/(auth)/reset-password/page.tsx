'use client';

import { createClient } from '@/lib/supabase/client';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Eye,
  EyeOff,
  Lock,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useRef, useState } from 'react';

const SESSION_TIMEOUT_MS = 5000;

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const sessionDetected = useRef(false);

  useEffect(() => {
    setMounted(true);

    const supabase = createClient();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') {
        sessionDetected.current = true;
        setSessionReady(true);
      }
    });

    const timeout = setTimeout(() => {
      if (!sessionDetected.current) {
        setSessionExpired(true);
      }
    }, SESSION_TIMEOUT_MS);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeout);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Security keys do not match');
      return;
    }

    if (password.length < 8) {
      setError('Security key must be at least 8 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      const supabase = createClient();
      const { error: updateError } = await supabase.auth.updateUser({
        password,
      });

      if (updateError) {
        throw new Error(updateError.message);
      }

      setSuccess(true);
      setTimeout(() => router.push('/login'), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!mounted) return null;

  if (sessionExpired) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="max-w-md w-full mx-6"
        >
          <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-10 text-center">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 mx-auto mb-6">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-[0.15em] mb-3">
              Link Expired
            </h2>
            <p className="text-sm font-mono text-[var(--nous-fg-3)] mb-6 leading-relaxed">
              This reset link is expired or invalid. Request a new one to
              continue.
            </p>
            <Link
              href="/forgot-password"
              className={cn(
                'inline-flex items-center gap-2 py-3 px-6 rounded-xl font-mono text-xs font-bold uppercase tracking-[0.2em]',
                'bg-[var(--nous-sol)] text-[var(--nous-bg-1)]',
                'hover:shadow-[0_0_25px_var(--nous-sol-glow)] hover:scale-[1.02] active:scale-[0.98]',
                'transition-all duration-300'
              )}
            >
              <span>Request New Link</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  if (!sessionReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)]">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <RefreshCw className="w-6 h-6 text-[var(--nous-sol)] animate-spin mx-auto mb-4" />
          <p className="text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-widest">
            Verifying recovery session...
          </p>
        </motion.div>
      </div>
    );
  }

  if (success) {
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
              Key Updated
            </h2>
            <p className="text-sm font-mono text-[var(--nous-fg-3)] mb-4 leading-relaxed">
              Your security key has been reset. Redirecting to login...
            </p>
            <div className="h-1 w-24 mx-auto rounded-full bg-[var(--nous-border-1)] overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: '100%' }}
                transition={{ duration: 3 }}
                className="h-full bg-[var(--nous-sol)]"
              />
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--nous-bg-1)] relative overflow-hidden">
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
        <div className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-8 shadow-2xl shadow-black/50">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[var(--nous-bg-3)] border border-[var(--nous-border-1)] mb-4">
              <Lock className="w-5 h-5 text-[var(--nous-sol)]" />
            </div>
            <h2 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] uppercase tracking-[0.2em]">
              New Security Key
            </h2>
            <p className="text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-wider mt-2">
              Enter your new access credentials
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
                  Reset Error: {error}
                </p>
              </motion.div>
            )}

            <div className="space-y-2">
              <label
                htmlFor="password"
                className="block text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-[0.2em] font-bold pl-1"
              >
                New Security Key
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <Lock className="w-4 h-4 text-[var(--nous-fg-3)]" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-11 pr-12 py-3 rounded-xl bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)]/30 focus:border-[var(--nous-sol)]/50 focus:ring-0 outline-none transition-all"
                  placeholder="NEW_KEY_BUFFER"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)] transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="confirmPassword"
                className="block text-[10px] font-mono text-[var(--nous-fg-3)] uppercase tracking-[0.2em] font-bold pl-1"
              >
                Verify New Key
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <Lock className="w-4 h-4 text-[var(--nous-fg-3)]" />
                </div>
                <input
                  id="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full pl-11 pr-4 py-3 rounded-xl bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] font-mono text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)]/30 focus:border-[var(--nous-sol)]/50 focus:ring-0 outline-none transition-all"
                  placeholder="RE_ENTER_KEY"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                'group w-full flex items-center justify-center gap-3 py-3.5 px-4 rounded-xl font-mono text-xs font-bold uppercase tracking-[0.2em]',
                'bg-[var(--nous-sol)] text-[var(--nous-bg-1)]',
                'hover:shadow-[0_0_25px_var(--nous-sol-glow)] hover:scale-[1.02] active:scale-[0.98]',
                'disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300'
              )}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Updating...</span>
                </>
              ) : (
                <>
                  <span>Update Security Key</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-[var(--nous-border-1)] text-center">
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
