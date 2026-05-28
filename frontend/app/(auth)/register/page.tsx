'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { RegisterRequest } from '@/types';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Building2,
  Database,
  Eye,
  EyeOff,
  Lock,
  Mail,
  RefreshCw,
  Shield,
  Sparkles,
  User,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';
import PendingEmailConfirmation from '@/components/auth/PendingEmailConfirmation';
import { useAuthStore } from '@/stores/authStore';

interface RegisterFormData {
  email: string;
  password: string;
  confirmPassword: string;
  first_name: string;
  last_name: string;
  organization_name: string;
}

const FEATURES = [
  { icon: Sparkles, text: 'Semantic search across everything you read' },
  { icon: Database, text: 'Multimodal documents, papers, and data' },
  { icon: Zap, text: 'Knowledge graph synthesis' },
  { icon: Shield, text: 'Cited, traceable answers' },
] as const;

export default function RegisterPage() {
  const { register, isAuthenticated, isLoading, pendingEmailConfirmation } =
    useAuth();
  const router = useRouter();
  const [formData, setFormData] = useState<RegisterFormData>({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    organization_name: '',
  });
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      const registerData: RegisterRequest = {
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        organization_name: formData.organization_name || undefined,
      };

      const result = await register(registerData);
      if (!result.requiresEmailConfirmation) {
        router.push('/');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Account creation failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const passwordStrength = () => {
    const password = formData.password;
    if (!password) return { level: 0, text: '', color: '' };
    if (password.length < 6)
      return { level: 1, text: 'Weak', color: 'bg-[var(--nous-mars)]' };
    if (password.length < 8)
      return { level: 2, text: 'Fair', color: 'bg-[var(--nous-corona)]' };
    if (password.length < 12)
      return { level: 3, text: 'Good', color: 'bg-[var(--nous-sol)]' };
    return { level: 4, text: 'Strong', color: 'bg-[var(--nous-sol)]' };
  };

  const strength = passwordStrength();

  const handleResetConfirmation = () => {
    useAuthStore.setState({ pendingEmailConfirmation: false });
    setFormData({
      email: '',
      password: '',
      confirmPassword: '',
      first_name: '',
      last_name: '',
      organization_name: '',
    });
  };

  // Email confirmation screen
  if (pendingEmailConfirmation) {
    return (
      <PendingEmailConfirmation
        email={formData.email}
        onReset={handleResetConfirmation}
      />
    );
  }

  const inputClass =
    'w-full pl-11 pr-4 py-2.5 rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] text-sm text-[var(--nous-fg-1)] placeholder:text-[var(--nous-fg-3)] transition-colors hover:border-[var(--nous-border-2)] focus-visible:outline-none focus-visible:border-[var(--nous-sol)] focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/30';

  return (
    <div className="min-h-screen flex bg-[var(--nous-bg-1)] text-[var(--nous-fg-1)] selection:bg-[var(--nous-sol)]/20">
      {/* Brand panel */}
      <aside className="hidden lg:flex lg:w-5/12 flex-col justify-center px-16 lg:px-20 border-r border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]">
        <div className="max-w-md">
          <p className="nous-overline mb-5">Multimodal Intelligence</p>
          <p className="nous-wordmark text-5xl mb-6">NOUS</p>
          <p className="nous-body text-lg mb-10 max-w-[60ch]">
            Create an account to start turning documents, papers, and data into
            a connected body of knowledge.
          </p>

          <ul className="space-y-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3">
                <span className="flex items-center justify-center w-8 h-8 rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-3)] text-[var(--nous-fg-accent-safe)]">
                  <Icon className="w-4 h-4" aria-hidden="true" />
                </span>
                <span className="nous-ui text-[var(--nous-fg-2)]">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex items-center justify-center px-6 py-12 lg:px-8 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-lg"
        >
          <div className="lg:hidden mb-10 text-center">
            <p className="nous-wordmark text-3xl">NOUS</p>
          </div>

          <header className="mb-8">
            <h1 className="nous-h2 mb-1">Create account</h1>
            <p className="nous-caption">A few details and you&apos;re in.</p>
          </header>

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {error && (
              <div
                role="alert"
                className="rounded-[var(--nous-radius-md)] border border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/10 px-3.5 py-3"
              >
                <p className="nous-ui text-sm font-semibold text-[var(--nous-mars)]">
                  We couldn&apos;t create your account
                </p>
                <p className="nous-caption mt-0.5 text-[var(--nous-fg-2)]">
                  {error}
                </p>
              </div>
            )}

            {/* Name fields */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="first_name"
                  className="nous-ui block text-sm font-medium"
                >
                  First name
                </label>
                <div className="relative">
                  <User
                    className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                    aria-hidden="true"
                  />
                  <input
                    id="first_name"
                    name="first_name"
                    type="text"
                    required
                    value={formData.first_name}
                    onChange={handleChange}
                    className={inputClass}
                    placeholder="Ada"
                    autoComplete="given-name"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="last_name"
                  className="nous-ui block text-sm font-medium"
                >
                  Last name
                </label>
                <div className="relative">
                  <User
                    className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                    aria-hidden="true"
                  />
                  <input
                    id="last_name"
                    name="last_name"
                    type="text"
                    required
                    value={formData.last_name}
                    onChange={handleChange}
                    className={inputClass}
                    placeholder="Lovelace"
                    autoComplete="family-name"
                  />
                </div>
              </div>
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="nous-ui block text-sm font-medium"
              >
                Email
              </label>
              <div className="relative">
                <Mail
                  className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                  aria-hidden="true"
                />
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={handleChange}
                  className={inputClass}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </div>
            </div>

            {/* Organization */}
            <div className="space-y-1.5">
              <label
                htmlFor="organization_name"
                className="nous-ui block text-sm font-medium"
              >
                Organization{' '}
                <span className="text-[var(--nous-fg-3)] font-normal">
                  (optional)
                </span>
              </label>
              <div className="relative">
                <Building2
                  className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                  aria-hidden="true"
                />
                <input
                  id="organization_name"
                  name="organization_name"
                  type="text"
                  value={formData.organization_name}
                  onChange={handleChange}
                  className={inputClass}
                  placeholder="Acme Research"
                  autoComplete="organization"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="nous-ui block text-sm font-medium"
              >
                Password
              </label>
              <div className="relative">
                <Lock
                  className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                  aria-hidden="true"
                />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={formData.password}
                  onChange={handleChange}
                  className={cn(inputClass, 'pr-12')}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  aria-describedby="password-strength"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-colors focus-visible:outline-none focus-visible:text-[var(--nous-sol)]"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" aria-hidden="true" />
                  ) : (
                    <Eye className="w-4 h-4" aria-hidden="true" />
                  )}
                </button>
              </div>
              {formData.password && (
                <div
                  id="password-strength"
                  className="flex items-center gap-2 pt-1"
                  aria-live="polite"
                >
                  <div className="flex-1 flex gap-1">
                    {[1, 2, 3, 4].map((level) => (
                      <div
                        key={level}
                        className={cn(
                          'h-1 flex-1 rounded-full transition-colors duration-300',
                          level <= strength.level
                            ? strength.color
                            : 'bg-[var(--nous-border-1)]'
                        )}
                      />
                    ))}
                  </div>
                  <span className="nous-caption text-[var(--nous-fg-2)]">
                    {strength.text}
                  </span>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div className="space-y-1.5">
              <label
                htmlFor="confirmPassword"
                className="nous-ui block text-sm font-medium"
              >
                Confirm password
              </label>
              <div className="relative">
                <Lock
                  className="absolute inset-y-0 left-3.5 my-auto w-4 h-4 text-[var(--nous-fg-3)]"
                  aria-hidden="true"
                />
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  required
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className={cn(inputClass, 'pr-12')}
                  placeholder="Re-enter password"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)] transition-colors focus-visible:outline-none focus-visible:text-[var(--nous-sol)]"
                  aria-label={
                    showConfirmPassword ? 'Hide password' : 'Show password'
                  }
                >
                  {showConfirmPassword ? (
                    <EyeOff className="w-4 h-4" aria-hidden="true" />
                  ) : (
                    <Eye className="w-4 h-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                'w-full flex items-center justify-center gap-2 py-3 px-4 rounded-[var(--nous-radius-md)]',
                'nous-ui text-sm font-semibold',
                'bg-[var(--nous-sol)] text-[var(--nous-erebus)]',
                'transition-colors hover:bg-[var(--nous-helios)] active:scale-[0.99]',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--nous-bg-1)]',
                'disabled:opacity-60 disabled:cursor-not-allowed'
              )}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw
                    className="w-4 h-4 animate-spin"
                    aria-hidden="true"
                  />
                  <span>Creating account</span>
                </>
              ) : (
                <>
                  <span>Create account</span>
                  <ArrowRight className="w-4 h-4" aria-hidden="true" />
                </>
              )}
            </button>
          </form>

          <p className="nous-caption mt-8 text-center">
            Already have an account?{' '}
            <Link
              href="/login"
              className="rounded-sm font-medium text-[var(--nous-fg-accent-safe)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
            >
              Sign in
            </Link>
          </p>
        </motion.div>
      </main>
    </div>
  );
}
