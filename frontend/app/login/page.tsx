'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { ArrowRight, Loader2, Lock, Mail, Terminal, Eye, EyeOff, Sparkles, Shield, Zap, Database, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface LoginFormData {
  email: string;
  password: string;
}

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';

export default function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [formData, setFormData] = useState<LoginFormData>({
    email: '',
    password: '',
  });
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login(formData.email, formData.password);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
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
    { icon: Database, text: 'Multimodal Stream Processing' },
    { icon: Zap, text: 'Knowledge Graph Synthesis' },
    { icon: Shield, text: 'Zero-Trust Protocol' },
  ];

  if (!mounted) return null;

  return (
    <div className="min-h-screen flex bg-[var(--terminal-bg)] relative overflow-hidden">
      {/* Background Grid - Subdued */}
      <div className="absolute inset-0 opacity-[0.02] pointer-events-none">
        <div className="h-full w-full" style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }} />
      </div>

      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden border-r border-[var(--terminal-border)]">
        <div className="relative z-10 flex flex-col justify-center px-16 lg:px-24">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-4 mb-16"
          >
            <div className="flex items-center justify-center w-14 h-14 rounded-xl border border-[var(--phosphor-green)]/30 bg-[var(--phosphor-green)]/10 shadow-xl shadow-[var(--phosphor-green)]/5">
              <Terminal className="w-7 h-7 text-[var(--phosphor-green)]" />
            </div>
            <div>
              <h1 className="text-3xl font-mono font-bold text-[var(--terminal-text)] tracking-tighter">RAG SYSTEM</h1>
              <p className="text-[10px] font-mono font-bold text-[var(--phosphor-green)]/70 uppercase tracking-[0.3em]">Terminal Observatory</p>
            </div>
          </motion.div>

          {/* Hero Text */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <h2 className="text-5xl font-mono font-bold text-[var(--terminal-text)] leading-tight mb-8 tracking-tight">
              NEURAL DATA<br />
              <span className="bg-gradient-to-r from-[var(--phosphor-green)] to-[var(--cyan)] bg-clip-text text-transparent">
                SYNTHESIS
              </span>
            </h2>
            <p className="text-sm font-mono text-[var(--terminal-text-muted)] max-w-sm mb-12 leading-relaxed uppercase tracking-wide">
              Transforming unstructured streams into actionable intelligence protocols.
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

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-8 relative bg-[var(--terminal-bg)]">
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center gap-4 mb-12">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl border border-[var(--phosphor-green)]/30 bg-[var(--phosphor-green)]/10">
              <Terminal className="w-6 h-6 text-[var(--phosphor-green)]" />
            </div>
            <span className="text-2xl font-mono font-bold text-[var(--terminal-text)]">RAG_SYS</span>
          </div>

          {/* Form Container */}
          <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-8 shadow-2xl shadow-black/50 relative overflow-hidden group">
            {/* Corner Accent */}
            <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-bl from-[var(--phosphor-green)]/10 to-transparent pointer-events-none" />
            
            {/* Form Header */}
            <div className="text-center mb-10">
              <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.2em]">Access Protocol</h2>
              <div className="h-0.5 w-12 bg-[var(--phosphor-green)] mx-auto mt-3 opacity-50" />
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-lg border border-red-500/30 bg-red-500/5 p-3"
                >
                  <p className="text-[10px] font-mono text-red-400 font-bold uppercase tracking-tighter">System Error: {error}</p>
                </motion.div>
              )}

              {/* Email Field */}
              <div className="space-y-2">
                <label htmlFor="email" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">
                  User Identifier
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
                    value={formData.email}
                    onChange={handleChange}
                    className="w-full pl-11 pr-4 py-3 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 transition-all outline-none"
                    placeholder="UID@DOMAIN.COM"
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="space-y-2">
                <div className="flex items-center justify-between pl-1">
                  <label htmlFor="password" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold">
                    Security Key
                  </label>
                </div>
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
                    className="w-full pl-11 pr-12 py-3 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-0 transition-all outline-none"
                    placeholder="••••••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
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
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <span>Initiate Link</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            {/* Registration */}
            <div className="mt-8 pt-6 border-t border-[var(--terminal-border)] text-center">
              <Link
                href="/register"
                className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors"
              >
                New Node Registration
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
