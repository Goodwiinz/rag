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
  Shield,
  Sparkles,
  Terminal,
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

// Brand accent constants (Sol gold). Retained for reference.
const _PHOSPHOR_GREEN = '#D4A039';
const _AMBER = '#ffb700';

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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
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
      setError(
        err instanceof Error ? err.message : 'Could not create your account'
      );
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

  const features = [
    { icon: Sparkles, text: 'Semantic search across your documents' },
    { icon: Database, text: 'Ingest text, tables, and images together' },
    { icon: Zap, text: 'Connected answers from a knowledge graph' },
    { icon: Shield, text: 'Private by default, scoped to your team' },
  ];

  const passwordStrength = () => {
    const password = formData.password;
    if (!password) return { level: 0, text: '', color: '' };
    if (password.length < 6)
      return { level: 1, text: 'Weak', color: 'bg-destructive' };
    if (password.length < 8)
      return { level: 2, text: 'Fair', color: 'bg-amber-500' };
    if (password.length < 12)
      return { level: 3, text: 'Good', color: 'bg-primary' };
    return { level: 4, text: 'Strong', color: 'bg-primary' };
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

  if (!mounted) return null;

  // Email confirmation screen
  if (pendingEmailConfirmation) {
    return (
      <PendingEmailConfirmation
        email={formData.email}
        onReset={handleResetConfirmation}
      />
    );
  }

  const inputClasses =
    'w-full pl-11 pr-4 py-2.5 rounded-lg bg-background border border-border text-sm text-foreground placeholder:text-muted-foreground/70 outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/40';

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Left panel — brand */}
      <div className="hidden lg:flex lg:w-5/12 relative border-r border-border">
        <div className="relative z-10 flex flex-col justify-center px-16 lg:px-20">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="flex items-center gap-3 mb-14"
          >
            <div className="flex items-center justify-center w-12 h-12 rounded-xl border border-border bg-card">
              <Terminal className="w-6 h-6 text-primary" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-foreground">
                NOUS
              </h1>
              <p className="text-sm text-muted-foreground">
                Document intelligence
              </p>
            </div>
          </motion.div>

          {/* Hero */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <h2 className="text-4xl font-semibold tracking-tight text-foreground leading-tight mb-5">
              Make sense of everything you read.
            </h2>
            <p
              className="text-base text-muted-foreground max-w-sm mb-12 leading-relaxed"
              style={{ fontFamily: 'var(--nous-font-body)' }}
            >
              Create an account to search, connect, and synthesize your
              documents in one place.
            </p>
          </motion.div>

          {/* Features */}
          <motion.ul
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="space-y-4"
          >
            {features.map((feature, i) => (
              <li key={i} className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-card border border-border">
                  <feature.icon
                    className="w-4 h-4 text-primary"
                    aria-hidden="true"
                  />
                </div>
                <span className="text-sm text-muted-foreground">
                  {feature.text}
                </span>
              </li>
            ))}
          </motion.ul>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-8 py-12 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-lg"
        >
          <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
            {/* Header */}
            <div className="mb-8">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                Create your account
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground">
                Set up access for you and your team.
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5"
                >
                  <p className="text-sm text-destructive">{error}</p>
                </div>
              )}

              {/* Name fields */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label
                    htmlFor="first_name"
                    className="block text-sm font-medium text-foreground"
                  >
                    First name
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                      <User
                        className="w-4 h-4 text-muted-foreground"
                        aria-hidden="true"
                      />
                    </div>
                    <input
                      id="first_name"
                      name="first_name"
                      type="text"
                      required
                      value={formData.first_name}
                      onChange={handleChange}
                      className={inputClasses}
                      placeholder="Ada"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label
                    htmlFor="last_name"
                    className="block text-sm font-medium text-foreground"
                  >
                    Last name
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                      <User
                        className="w-4 h-4 text-muted-foreground"
                        aria-hidden="true"
                      />
                    </div>
                    <input
                      id="last_name"
                      name="last_name"
                      type="text"
                      required
                      value={formData.last_name}
                      onChange={handleChange}
                      className={inputClasses}
                      placeholder="Lovelace"
                    />
                  </div>
                </div>
              </div>

              {/* Email */}
              <div className="space-y-1.5">
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-foreground"
                >
                  Email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Mail
                      className="w-4 h-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={handleChange}
                    className={inputClasses}
                    placeholder="you@company.com"
                  />
                </div>
              </div>

              {/* Organization */}
              <div className="space-y-1.5">
                <label
                  htmlFor="organization_name"
                  className="block text-sm font-medium text-foreground"
                >
                  Organization{' '}
                  <span className="font-normal text-muted-foreground">
                    (optional)
                  </span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Building2
                      className="w-4 h-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </div>
                  <input
                    id="organization_name"
                    name="organization_name"
                    type="text"
                    value={formData.organization_name}
                    onChange={handleChange}
                    className={inputClasses}
                    placeholder="Acme Inc."
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-foreground"
                >
                  Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Lock
                      className="w-4 h-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={formData.password}
                    onChange={handleChange}
                    className={cn(inputClasses, 'pr-12')}
                    placeholder="At least 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={
                      showPassword ? 'Hide password' : 'Show password'
                    }
                    aria-pressed={showPassword}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-muted-foreground hover:text-foreground rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" aria-hidden="true" />
                    ) : (
                      <Eye className="w-4 h-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                {/* Strength */}
                {formData.password && (
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-1 flex gap-1" aria-hidden="true">
                      {[1, 2, 3, 4].map((level) => (
                        <div
                          key={level}
                          className={cn(
                            'h-1 flex-1 rounded-full transition-colors duration-300',
                            level <= strength.level
                              ? strength.color
                              : 'bg-muted'
                          )}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {strength.text}
                    </span>
                  </div>
                )}
              </div>

              {/* Confirm password */}
              <div className="space-y-1.5">
                <label
                  htmlFor="confirmPassword"
                  className="block text-sm font-medium text-foreground"
                >
                  Confirm password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Lock
                      className="w-4 h-4 text-muted-foreground"
                      aria-hidden="true"
                    />
                  </div>
                  <input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className={cn(inputClasses, 'pr-12')}
                    placeholder="Re-enter your password"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      showConfirmPassword
                        ? setShowConfirmPassword(false)
                        : setShowConfirmPassword(true)
                    }
                    aria-label={
                      showConfirmPassword
                        ? 'Hide confirmation password'
                        : 'Show confirmation password'
                    }
                    aria-pressed={showConfirmPassword}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-muted-foreground hover:text-foreground rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
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
                  'group w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-medium',
                  'bg-primary text-primary-foreground',
                  'hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card',
                  'disabled:opacity-60 disabled:cursor-not-allowed transition-colors'
                )}
              >
                {isSubmitting ? (
                  <span>Creating account…</span>
                ) : (
                  <>
                    <span>Create account</span>
                    <ArrowRight
                      className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </>
                )}
              </button>
            </form>

            {/* Login link */}
            <div className="mt-6 pt-6 border-t border-border text-center">
              <p className="text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link
                  href="/login"
                  className="font-medium text-primary hover:underline rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
