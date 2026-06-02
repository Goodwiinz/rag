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
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: 'var(--nous-nyx)' }}
      >
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          <div
            className="rounded-2xl border p-10 text-center"
            style={{
              background: 'var(--nous-obsidian)',
              borderColor: 'var(--nous-shade)',
              boxShadow: 'var(--nous-shadow-xl)',
            }}
          >
            <div
              className="flex items-center justify-center w-14 h-14 rounded-full mx-auto mb-6"
              style={{
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
              }}
            >
              <AlertTriangle
                aria-hidden="true"
                className="w-6 h-6"
                style={{ color: 'var(--nous-mars)' }}
              />
            </div>
            <h1
              className="text-xl font-semibold mb-2"
              style={{ color: 'var(--nous-ivory)' }}
            >
              This link has expired
            </h1>
            <p
              className="text-sm mb-7 leading-relaxed"
              style={{
                color: 'var(--nous-parchment)',
                fontFamily: 'var(--nous-font-body)',
              }}
            >
              The reset link is no longer valid. Request a new one and we will
              email you a fresh link.
            </p>
            <Link
              href="/forgot-password"
              className="inline-flex items-center gap-2 py-2.5 px-5 rounded-lg text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              style={{
                background: 'var(--nous-sol)',
                color: 'var(--nous-erebus)',
                ['--tw-ring-color' as string]: 'var(--nous-sol)',
                ['--tw-ring-offset-color' as string]: 'var(--nous-obsidian)',
              }}
            >
              <span>Request a new link</span>
              <ArrowRight aria-hidden="true" className="w-4 h-4" />
            </Link>
          </div>
        </motion.div>
      </div>
    );
  }

  if (!sessionReady) {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: 'var(--nous-nyx)' }}
      >
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
          className="text-center"
        >
          <p
            className="text-sm"
            style={{
              color: 'var(--nous-parchment)',
              fontFamily: 'var(--nous-font-body)',
            }}
          >
            Verifying your recovery session…
          </p>
        </motion.div>
      </div>
    );
  }

  if (success) {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: 'var(--nous-nyx)' }}
      >
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-md"
        >
          <div
            className="rounded-2xl border p-10 text-center"
            style={{
              background: 'var(--nous-obsidian)',
              borderColor: 'var(--nous-shade)',
              boxShadow: 'var(--nous-shadow-xl)',
            }}
          >
            <div
              className="flex items-center justify-center w-14 h-14 rounded-full mx-auto mb-6"
              style={{
                background: 'var(--nous-ember)',
                border: '1px solid rgba(212, 160, 57, 0.3)',
              }}
            >
              <CheckCircle
                aria-hidden="true"
                className="w-6 h-6"
                style={{ color: 'var(--nous-sol)' }}
              />
            </div>
            <h1
              className="text-xl font-semibold mb-2"
              style={{ color: 'var(--nous-ivory)' }}
            >
              Your password has been updated
            </h1>
            <p
              className="text-sm mb-5 leading-relaxed"
              style={{
                color: 'var(--nous-parchment)',
                fontFamily: 'var(--nous-font-body)',
              }}
            >
              You can now sign in with your new password. Taking you to the sign
              in page…
            </p>
            <div
              className="h-1 w-24 mx-auto rounded-full overflow-hidden"
              style={{ background: 'var(--nous-shade)' }}
            >
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: '100%' }}
                transition={{ duration: 3 }}
                className="h-full"
                style={{ background: 'var(--nous-sol)' }}
              />
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-6"
      style={{ background: 'var(--nous-nyx)' }}
    >
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md"
      >
        <div
          className="rounded-2xl border p-8"
          style={{
            background: 'var(--nous-obsidian)',
            borderColor: 'var(--nous-shade)',
            boxShadow: 'var(--nous-shadow-xl)',
          }}
        >
          <div className="mb-7">
            <div
              className="inline-flex items-center justify-center w-11 h-11 rounded-full mb-4"
              style={{
                background: 'var(--nous-ember)',
                border: '1px solid rgba(212, 160, 57, 0.3)',
              }}
            >
              <Lock
                aria-hidden="true"
                className="w-5 h-5"
                style={{ color: 'var(--nous-sol)' }}
              />
            </div>
            <h1
              className="text-xl font-semibold"
              style={{ color: 'var(--nous-ivory)' }}
            >
              Set a new password
            </h1>
            <p
              className="text-sm mt-1.5 leading-relaxed"
              style={{
                color: 'var(--nous-parchment)',
                fontFamily: 'var(--nous-font-body)',
              }}
            >
              Choose a password with at least 8 characters.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <motion.div
                role="alert"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border p-3"
                style={{
                  background: 'rgba(239, 68, 68, 0.08)',
                  borderColor: 'rgba(239, 68, 68, 0.3)',
                }}
              >
                <p className="text-sm" style={{ color: 'var(--nous-mars)' }}>
                  {error}
                </p>
              </motion.div>
            )}

            <div className="space-y-2">
              <label
                htmlFor="password"
                className="block text-sm font-medium"
                style={{ color: 'var(--nous-parchment)' }}
              >
                New password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <Lock
                    aria-hidden="true"
                    className="w-4 h-4"
                    style={{ color: 'var(--nous-dust)' }}
                  />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-11 pr-12 py-2.5 rounded-lg text-sm outline-none transition-colors duration-200 focus-visible:ring-2"
                  style={{
                    background: 'var(--nous-nyx)',
                    border: '1px solid var(--nous-shade)',
                    color: 'var(--nous-ivory)',
                    ['--tw-ring-color' as string]: 'var(--nous-sol)',
                  }}
                  placeholder="Enter a new password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 transition-colors duration-200 rounded-r-lg focus-visible:outline-none focus-visible:ring-2"
                  style={{
                    color: 'var(--nous-dust)',
                    ['--tw-ring-color' as string]: 'var(--nous-sol)',
                  }}
                >
                  {showPassword ? (
                    <EyeOff aria-hidden="true" className="w-4 h-4" />
                  ) : (
                    <Eye aria-hidden="true" className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium"
                style={{ color: 'var(--nous-parchment)' }}
              >
                Confirm new password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                  <Lock
                    aria-hidden="true"
                    className="w-4 h-4"
                    style={{ color: 'var(--nous-dust)' }}
                  />
                </div>
                <input
                  id="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full pl-11 pr-4 py-2.5 rounded-lg text-sm outline-none transition-colors duration-200 focus-visible:ring-2"
                  style={{
                    background: 'var(--nous-nyx)',
                    border: '1px solid var(--nous-shade)',
                    color: 'var(--nous-ivory)',
                    ['--tw-ring-color' as string]: 'var(--nous-sol)',
                  }}
                  placeholder="Re-enter your new password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                'w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium',
                'transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
              style={{
                background: 'var(--nous-sol)',
                color: 'var(--nous-erebus)',
                ['--tw-ring-color' as string]: 'var(--nous-sol)',
                ['--tw-ring-offset-color' as string]: 'var(--nous-obsidian)',
              }}
            >
              {isSubmitting ? (
                <span>Updating…</span>
              ) : (
                <>
                  <span>Update password</span>
                  <ArrowRight aria-hidden="true" className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div
            className="mt-7 pt-6 border-t text-center"
            style={{ borderColor: 'var(--nous-shade)' }}
          >
            <Link
              href="/login"
              className="text-sm transition-colors duration-200 rounded focus-visible:outline-none focus-visible:ring-2"
              style={{
                color: 'var(--nous-sol)',
                ['--tw-ring-color' as string]: 'var(--nous-sol)',
              }}
            >
              Back to sign in
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
