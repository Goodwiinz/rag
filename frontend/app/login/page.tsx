'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { ArrowRight, Loader2, Lock, Mail, Terminal, Eye, EyeOff, Sparkles, Shield, Zap, Database } from 'lucide-react';
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
  const [terminalText, setTerminalText] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'SECURE ACCESS TERMINAL v2.0';
    let index = 0;
    const interval = setInterval(() => {
      if (index <= fullText.length) {
        setTerminalText(fullText.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
      }
    }, 50);
    return () => clearInterval(interval);
  }, [mounted]);

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
    { icon: Sparkles, text: 'AI-powered semantic search' },
    { icon: Database, text: 'Multi-format document processing' },
    { icon: Zap, text: 'Knowledge graph visualization' },
    { icon: Shield, text: 'Enterprise-grade security' },
  ];

  return (
    <div className="min-h-screen flex bg-[#0a0a0f] relative overflow-hidden">
      {/* CRT Scanlines Overlay */}
      <div className="pointer-events-none fixed inset-0 z-50 opacity-[0.03]">
        <div className="h-full w-full" style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 159, 0.03) 2px, rgba(0, 255, 159, 0.03) 4px)',
        }} />
      </div>

      {/* Background Grid */}
      <div className="absolute inset-0 opacity-[0.02]">
        <div className="h-full w-full" style={{
          backgroundImage: `
            linear-gradient(${PHOSPHOR_GREEN}20 1px, transparent 1px),
            linear-gradient(90deg, ${PHOSPHOR_GREEN}20 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
        }} />
      </div>

      {/* Ambient Glow Effects */}
      <div className="absolute top-0 left-1/4 w-[600px] h-[600px] rounded-full blur-[150px] opacity-20"
        style={{ background: `radial-gradient(circle, ${PHOSPHOR_GREEN}30, transparent 70%)` }} />
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] rounded-full blur-[120px] opacity-15"
        style={{ background: `radial-gradient(circle, ${AMBER}20, transparent 70%)` }} />

      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden border-r border-[#00ff9f]/10">
        <div className="relative z-10 flex flex-col justify-center px-12 lg:px-16">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-3 mb-12"
          >
            <div className="flex items-center justify-center w-12 h-12 rounded border border-[#00ff9f]/30 bg-[#00ff9f]/10 shadow-lg shadow-[#00ff9f]/10">
              <Terminal className="w-6 h-6 text-[#00ff9f]" />
            </div>
            <div>
              <h1 className="text-2xl font-mono font-bold text-white/90">RAG System</h1>
              <p className="text-sm font-mono text-[#00ff9f]/70">Terminal Observatory</p>
            </div>
          </motion.div>

          {/* Hero Text */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <h2 className="text-4xl lg:text-5xl font-bold font-mono text-white/90 leading-tight mb-6">
              Transform Data Into
              <span className="block bg-gradient-to-r from-[#00ff9f] via-[#00ff9f]/80 to-[#ffb700] bg-clip-text text-transparent">
                Actionable Intelligence
              </span>
            </h2>
            <p className="text-lg font-mono text-white/50 max-w-md mb-8">
              Upload documents, extract entities with AI, build knowledge graphs,
              and search with semantic understanding.
            </p>
          </motion.div>

          {/* Features */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="space-y-4"
          >
            {features.map((feature, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="flex items-center justify-center w-8 h-8 rounded bg-[#00ff9f]/10 border border-[#00ff9f]/20">
                  <feature.icon className="w-4 h-4 text-[#00ff9f]" />
                </div>
                <span className="text-sm font-mono text-white/60">{feature.text}</span>
              </div>
            ))}
          </motion.div>

          {/* Terminal Status */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-12 p-4 rounded border border-white/10 bg-white/[0.02]"
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-[#00ff9f] animate-pulse" />
              <span className="text-xs font-mono text-[#00ff9f]/70">SYSTEM STATUS</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="flex items-center gap-2 text-white/40">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f]" />
                API Gateway: Online
              </div>
              <div className="flex items-center gap-2 text-white/40">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f]" />
                Vector Store: Online
              </div>
              <div className="flex items-center gap-2 text-white/40">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f]" />
                PostgreSQL: Online
              </div>
              <div className="flex items-center gap-2 text-white/40">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f]" />
                Neo4j Graph: Online
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-8 relative">
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center gap-3 mb-8">
            <div className="flex items-center justify-center w-10 h-10 rounded border border-[#00ff9f]/30 bg-[#00ff9f]/10">
              <Terminal className="w-5 h-5 text-[#00ff9f]" />
            </div>
            <span className="text-xl font-mono font-bold text-white/90">RAG System</span>
          </div>

          {/* Terminal Header */}
          <div className="rounded-t border border-b-0 border-white/10 bg-white/[0.02] px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
              </div>
              <div className="flex-1 flex items-center justify-center">
                <span className="text-xs font-mono text-white/40">
                  {terminalText}
                  <span className="animate-pulse">_</span>
                </span>
              </div>
              <Shield className="w-4 h-4 text-[#00ff9f]/50" />
            </div>
          </div>

          {/* Form Container */}
          <div className="rounded-b border border-white/10 bg-[#0d0d12] p-6 shadow-2xl shadow-black/50">
            {/* Form Header */}
            <div className="text-center mb-6">
              <h2 className="text-xl font-mono font-bold text-white/90">Authentication Required</h2>
              <p className="text-sm font-mono text-white/40 mt-1">
                Enter credentials to access the system
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded border border-red-500/30 bg-red-500/10 p-3"
                >
                  <p className="text-xs font-mono text-red-400">[ERROR] {error}</p>
                </motion.div>
              )}

              {/* Email Field */}
              <div className="space-y-2">
                <label htmlFor="email" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                  User Identifier
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                    <Mail className="w-4 h-4 text-white/30" />
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={formData.email}
                    onChange={handleChange}
                    className={cn(
                      "w-full pl-10 pr-4 py-3 rounded border font-mono text-sm",
                      "bg-white/[0.02] border-white/10 text-white/90",
                      "placeholder:text-white/30",
                      "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                      "transition-all"
                    )}
                    placeholder="user@domain.com"
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                    Access Key
                  </label>
                  <Link href="#" className="text-xs font-mono text-[#ffb700]/70 hover:text-[#ffb700] transition-colors">
                    Reset credentials
                  </Link>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                    <Lock className="w-4 h-4 text-white/30" />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={formData.password}
                    onChange={handleChange}
                    className={cn(
                      "w-full pl-10 pr-12 py-3 rounded border font-mono text-sm",
                      "bg-white/[0.02] border-white/10 text-white/90",
                      "placeholder:text-white/30",
                      "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                      "transition-all"
                    )}
                    placeholder="••••••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#00ff9f]/50 hover:text-[#00ff9f] transition-colors"
                    title={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {/* Remember Me */}
              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  className="h-4 w-4 rounded border-white/20 bg-white/5 text-[#00ff9f] focus:ring-[#00ff9f]/50"
                />
                <label htmlFor="remember-me" className="ml-2 text-xs font-mono text-white/50">
                  Maintain session for 30 cycles
                </label>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className={cn(
                  "group w-full flex items-center justify-center gap-2 py-3 px-4 rounded font-mono text-sm",
                  "bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30",
                  "hover:bg-[#00ff9f]/20 hover:border-[#00ff9f]/50 hover:shadow-[0_0_20px_rgba(0,255,159,0.2)]",
                  "disabled:opacity-50 disabled:cursor-not-allowed",
                  "transition-all duration-300"
                )}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>AUTHENTICATING...</span>
                  </>
                ) : (
                  <>
                    <span>INITIATE SESSION</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            {/* Register Link */}
            <div className="mt-6 pt-6 border-t border-white/10 text-center">
              <p className="text-xs font-mono text-white/40">
                No access credentials?{' '}
                <Link
                  href="/register"
                  className="text-[#00ff9f] hover:text-[#00ff9f]/80 transition-colors"
                >
                  Request new account
                </Link>
              </p>
            </div>

            {/* Quick Login (Dev Only) */}
            <div className="mt-4 p-3 rounded border border-dashed border-white/10 bg-white/[0.01]">
              <p className="text-[10px] font-mono text-white/30 text-center mb-2">[DEV] Quick Access</p>
              <div className="flex gap-2 text-[10px] font-mono">
                <button
                  type="button"
                  onClick={() => setFormData({ email: 'admin@multimodal-rag.com', password: 'admin123' })}
                  className="flex-1 py-1.5 rounded border border-white/10 text-white/40 hover:text-white/60 hover:bg-white/5 transition-colors"
                >
                  Admin
                </button>
                <button
                  type="button"
                  onClick={() => setFormData({ email: 'demo@multimodal-rag.com', password: 'demo123' })}
                  className="flex-1 py-1.5 rounded border border-white/10 text-white/40 hover:text-white/60 hover:bg-white/5 transition-colors"
                >
                  Demo
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
