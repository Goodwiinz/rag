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
    Terminal,
    User,
    Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';

interface RegisterFormData {
  email: string;
  password: string;
  confirmPassword: string;
  first_name: string;
  last_name: string;
  organization_name: string;
}

// Terminal Observatory Theme Constants
const _PHOSPHOR_GREEN = '#00ff9f';
const _AMBER = '#ffb700';

export default function RegisterPage() {
  const { register, isAuthenticated, isLoading } = useAuth();
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
      setError('Access keys do not match');
      return;
    }

    // Validate password strength
    if (formData.password.length < 8) {
      setError('Access key must be at least 8 characters');
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

      await register(registerData);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Account provisioning failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const features = [
    { icon: Sparkles, text: 'Neural Semantic Search' },
    { icon: Database, text: 'Multimodal Ingestion' },
    { icon: Zap, text: 'Knowledge Graph Synthesis' },
    { icon: Shield, text: 'Zero-Trust Protocol' },
  ];

  const passwordStrength = () => {
    const password = formData.password;
    if (!password) return { level: 0, text: '', color: '' };
    if (password.length < 6) return { level: 1, text: 'WEAK', color: 'bg-red-500' };
    if (password.length < 8) return { level: 2, text: 'FAIR', color: 'bg-yellow-500' };
    if (password.length < 12) return { level: 3, text: 'GOOD', color: 'bg-[var(--phosphor-green)]' };
    return { level: 4, text: 'OPTIMAL', color: 'bg-[var(--phosphor-green)]' };
  };

  const strength = passwordStrength();

  if (!mounted) return null;

  return (
    <div className="min-h-screen flex bg-[var(--terminal-bg)] relative overflow-hidden">
      {/* Background Grid */}
      <div className="absolute inset-0 opacity-[0.02] pointer-events-none">
        <div className="h-full w-full" style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }} />
      </div>

      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-5/12 relative overflow-hidden border-r border-[var(--terminal-border)]">
        <div className="relative z-10 flex flex-col justify-center px-16 lg:px-20">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-4 mb-16"
          >
            <div className="flex items-center justify-center w-14 h-14 rounded-xl border border-[var(--phosphor-green)]/30 bg-[var(--phosphor-green)]/10">
              <Terminal className="w-7 h-7 text-[var(--phosphor-green)]" />
            </div>
            <div>
              <h1 className="text-3xl font-mono font-bold text-[var(--terminal-text)] tracking-tighter">RAG SYSTEM</h1>
              <p className="text-[10px] font-mono font-bold text-[var(--phosphor-green)]/70 uppercase tracking-[0.3em]">Identity Registry</p>
            </div>
          </motion.div>

          {/* Hero Text */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <h2 className="text-4xl font-mono font-bold text-[var(--terminal-text)] leading-tight mb-8 tracking-tight uppercase">
              Initialize<br />
              <span className="bg-gradient-to-r from-[var(--phosphor-green)] to-[var(--cyan)] bg-clip-text text-transparent">
                New Node
              </span>
            </h2>
            <p className="text-sm font-mono text-[var(--terminal-text-muted)] max-w-sm mb-12 leading-relaxed uppercase tracking-wide">
              Provision access credentials for high-density document intelligence and synthesis.
            </p>
          </motion.div>

          {/* Features */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="space-y-5"
          >
            {features.map((feature, i) => (
              <div key={i} className="flex items-center gap-4 group">
                <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] group-hover:border-[var(--phosphor-green)]/50 transition-colors">
                  <feature.icon className="w-4 h-4 text-[var(--phosphor-green)]" />
                </div>
                <span className="text-[11px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-widest group-hover:text-[var(--terminal-text)] transition-colors">{feature.text}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </div>

      {/* Right Panel - Register Form */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-8 py-12 relative overflow-y-auto bg-[var(--terminal-bg)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-lg"
        >
          {/* Form Container */}
          <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-8 shadow-2xl shadow-black/50 relative overflow-hidden">
            {/* Form Header */}
            <div className="text-center mb-10">
              <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.2em]">Provisioning Terminal</h2>
              <div className="h-0.5 w-12 bg-[var(--phosphor-green)] mx-auto mt-3 opacity-50" />
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-lg border border-red-500/30 bg-red-500/5 p-3"
                >
                  <p className="text-[10px] font-mono text-red-400 font-bold uppercase tracking-tighter">Provisioning Error: {error}</p>
                </motion.div>
              )}

              {/* Name Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label htmlFor="first_name" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">First Name</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                      <User className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                    </div>
                    <input
                      id="first_name"
                      name="first_name"
                      type="text"
                      required
                      value={formData.first_name}
                      onChange={handleChange}
                      className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                      placeholder="FIRSTNAME"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="last_name" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">Last Name</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                      <User className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                    </div>
                    <input
                      id="last_name"
                      name="last_name"
                      type="text"
                      required
                      value={formData.last_name}
                      onChange={handleChange}
                      className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                      placeholder="LASTNAME"
                    />
                  </div>
                </div>
              </div>

              {/* Email Field */}
              <div className="space-y-2">
                <label htmlFor="email" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">Identity Protocol</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Mail className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    required
                    value={formData.email}
                    onChange={handleChange}
                    className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                    placeholder="UID@DOMAIN.COM"
                  />
                </div>
              </div>

              {/* Organization Field */}
              <div className="space-y-2">
                <label htmlFor="organization_name" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">Organization <span className="opacity-30">(OPTIONAL)</span></label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Building2 className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                  </div>
                  <input
                    id="organization_name"
                    name="organization_name"
                    type="text"
                    value={formData.organization_name}
                    onChange={handleChange}
                    className="w-full pl-11 pr-4 py-2.5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                    placeholder="CORP_IDENTIFIER"
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="space-y-2">
                <label htmlFor="password" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">Security Key</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Lock className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={formData.password}
                    onChange={handleChange}
                    className="w-full pl-11 pr-12 py-2.5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                    placeholder="KEY_BUFFER"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {/* Strength */}
                {formData.password && (
                  <div className="flex items-center gap-2 mt-2 px-1">
                    <div className="flex-1 flex gap-1">
                      {[1, 2, 3, 4].map((level) => (
                        <div
                          key={level}
                          className={cn(
                            "h-0.5 flex-1 rounded-full transition-all duration-500",
                            level <= strength.level ? strength.color : "bg-white/5"
                          )}
                        />
                      ))}
                    </div>
                    <span className="text-[8px] font-mono text-[var(--terminal-text-dim)] font-bold">{strength.text}</span>
                  </div>
                )}
              </div>

              {/* Confirm Field */}
              <div className="space-y-2">
                <label htmlFor="confirmPassword" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">Verify Key</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                    <Lock className="w-4 h-4 text-[var(--terminal-text-muted)]" />
                  </div>
                  <input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className="w-full pl-11 pr-12 py-2.5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 outline-none transition-all"
                    placeholder="RE_ENTER_KEY"
                  />
                  <button
                    type="button"
                    onClick={() => showConfirmPassword ? setShowConfirmPassword(false) : setShowConfirmPassword(true)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className={cn(
                  "group w-full flex items-center justify-center gap-3 py-3.5 px-4 rounded-xl font-mono text-xs font-bold uppercase tracking-[0.2em]",
                  "bg-[var(--phosphor-green)] text-[var(--terminal-bg)]",
                  "hover:shadow-[0_0_25px_var(--phosphor-green-glow)] hover:scale-[1.02] active:scale-[0.98]",
                  "disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
                )}
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Allocating Registry...</span>
                  </>
                ) : (
                  <>
                    <span>Commit Identity</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            {/* Login Link */}
            <div className="mt-8 pt-6 border-t border-[var(--terminal-border)] text-center">
              <Link
                href="/login"
                className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
              >
                Return to Access Terminal
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
