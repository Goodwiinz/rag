'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { RegisterRequest } from '@/types';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Loader2,
  Lock,
  Mail,
  Terminal,
  Eye,
  EyeOff,
  User,
  Building2,
  Shield,
  CheckCircle2,
  Sparkles,
  Database,
  Zap,
} from 'lucide-react';

interface RegisterFormData {
  email: string;
  password: string;
  confirmPassword: string;
  first_name: string;
  last_name: string;
  organization_name: string;
}

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';

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
  const [terminalText, setTerminalText] = useState('');
  const [mounted, setMounted] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'ACCOUNT PROVISIONING TERMINAL';
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
    { icon: Sparkles, text: 'AI-powered semantic search' },
    { icon: Database, text: 'Multi-format document processing' },
    { icon: Zap, text: 'Knowledge graph visualization' },
    { icon: Shield, text: 'Enterprise-grade security' },
  ];

  const passwordStrength = () => {
    const password = formData.password;
    if (!password) return { level: 0, text: '', color: '' };
    if (password.length < 6) return { level: 1, text: 'Weak', color: 'bg-red-500' };
    if (password.length < 8) return { level: 2, text: 'Fair', color: 'bg-yellow-500' };
    if (password.length < 12) return { level: 3, text: 'Good', color: 'bg-[#00ff9f]' };
    return { level: 4, text: 'Strong', color: 'bg-[#00ff9f]' };
  };

  const strength = passwordStrength();

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
      <div className="absolute top-0 right-1/4 w-[600px] h-[600px] rounded-full blur-[150px] opacity-20"
        style={{ background: `radial-gradient(circle, ${PHOSPHOR_GREEN}30, transparent 70%)` }} />
      <div className="absolute bottom-0 left-1/4 w-[500px] h-[500px] rounded-full blur-[120px] opacity-15"
        style={{ background: `radial-gradient(circle, ${AMBER}20, transparent 70%)` }} />

      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-5/12 relative overflow-hidden border-r border-[#00ff9f]/10">
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
            <h2 className="text-3xl lg:text-4xl font-bold font-mono text-white/90 leading-tight mb-6">
              Initialize Your
              <span className="block bg-gradient-to-r from-[#00ff9f] via-[#00ff9f]/80 to-[#ffb700] bg-clip-text text-transparent">
                Knowledge Network
              </span>
            </h2>
            <p className="text-base font-mono text-white/50 max-w-md mb-8">
              Create an account to start building your personal knowledge graph with AI-powered document processing.
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

          {/* Getting Started Steps */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.6 }}
            className="mt-12 p-4 rounded border border-white/10 bg-white/[0.02]"
          >
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-[#00ff9f] animate-pulse" />
              <span className="text-xs font-mono text-[#00ff9f]/70">QUICK START GUIDE</span>
            </div>
            <div className="space-y-2 text-xs font-mono">
              <div className="flex items-center gap-2 text-white/50">
                <span className="w-5 h-5 rounded-full border border-[#00ff9f]/30 flex items-center justify-center text-[#00ff9f] text-[10px]">1</span>
                Create your account
              </div>
              <div className="flex items-center gap-2 text-white/40">
                <span className="w-5 h-5 rounded-full border border-white/20 flex items-center justify-center text-[10px]">2</span>
                Upload your first document
              </div>
              <div className="flex items-center gap-2 text-white/40">
                <span className="w-5 h-5 rounded-full border border-white/20 flex items-center justify-center text-[10px]">3</span>
                Ask questions with AI
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Right Panel - Register Form */}
      <div className="flex-1 flex items-center justify-center px-4 sm:px-6 lg:px-8 py-8 relative overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-lg"
        >
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center justify-center gap-3 mb-6">
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
              <h2 className="text-xl font-mono font-bold text-white/90">Create New Account</h2>
              <p className="text-sm font-mono text-white/40 mt-1">
                Provision your access credentials
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded border border-red-500/30 bg-red-500/10 p-3"
                >
                  <p className="text-xs font-mono text-red-400">[ERROR] {error}</p>
                </motion.div>
              )}

              {/* Name Fields */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label htmlFor="first_name" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                    First Name
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                      <User className="w-4 h-4 text-white/30" />
                    </div>
                    <input
                      id="first_name"
                      name="first_name"
                      type="text"
                      required
                      value={formData.first_name}
                      onChange={handleChange}
                      className={cn(
                        "w-full pl-10 pr-4 py-2.5 rounded border font-mono text-sm",
                        "bg-white/[0.02] border-white/10 text-white/90",
                        "placeholder:text-white/30",
                        "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                        "transition-all"
                      )}
                      placeholder="John"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="last_name" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                    Last Name
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                      <User className="w-4 h-4 text-white/30" />
                    </div>
                    <input
                      id="last_name"
                      name="last_name"
                      type="text"
                      required
                      value={formData.last_name}
                      onChange={handleChange}
                      className={cn(
                        "w-full pl-10 pr-4 py-2.5 rounded border font-mono text-sm",
                        "bg-white/[0.02] border-white/10 text-white/90",
                        "placeholder:text-white/30",
                        "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                        "transition-all"
                      )}
                      placeholder="Doe"
                    />
                  </div>
                </div>
              </div>

              {/* Email Field */}
              <div className="space-y-2">
                <label htmlFor="email" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                  Email Address
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
                      "w-full pl-10 pr-4 py-2.5 rounded border font-mono text-sm",
                      "bg-white/[0.02] border-white/10 text-white/90",
                      "placeholder:text-white/30",
                      "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                      "transition-all"
                    )}
                    placeholder="you@company.com"
                  />
                </div>
              </div>

              {/* Organization Field */}
              <div className="space-y-2">
                <label htmlFor="organization_name" className="block text-xs font-mono text-white/50 uppercase tracking-wider">
                  Organization <span className="text-white/30">(Optional)</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                    <Building2 className="w-4 h-4 text-white/30" />
                  </div>
                  <input
                    id="organization_name"
                    name="organization_name"
                    type="text"
                    value={formData.organization_name}
                    onChange={handleChange}
                    className={cn(
                      "w-full pl-10 pr-4 py-2.5 rounded border font-mono text-sm",
                      "bg-white/[0.02] border-white/10 text-white/90",
                      "placeholder:text-white/30",
                      "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                      "transition-all"
                    )}
                    placeholder="Acme Corporation"
                  />
                </div>
              </div>

              {/* Password Field */}
              <div className="space-y-2">
                <label htmlFor="password" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                  Access Key
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                    <Lock className="w-4 h-4 text-white/30" />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={formData.password}
                    onChange={handleChange}
                    className={cn(
                      "w-full pl-10 pr-12 py-2.5 rounded border font-mono text-sm",
                      "bg-white/[0.02] border-white/10 text-white/90",
                      "placeholder:text-white/30",
                      "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                      "transition-all"
                    )}
                    placeholder="Min. 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-white/30 hover:text-white/60 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {/* Password Strength Indicator */}
                {formData.password && (
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-1 flex gap-1">
                      {[1, 2, 3, 4].map((level) => (
                        <div
                          key={level}
                          className={cn(
                            "h-1 flex-1 rounded-full transition-colors",
                            level <= strength.level ? strength.color : "bg-white/10"
                          )}
                        />
                      ))}
                    </div>
                    <span className="text-[10px] font-mono text-white/50">{strength.text}</span>
                  </div>
                )}
              </div>

              {/* Confirm Password Field */}
              <div className="space-y-2">
                <label htmlFor="confirmPassword" className="block text-xs font-mono text-[#00ff9f]/70 uppercase tracking-wider">
                  Confirm Access Key
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                    <Lock className="w-4 h-4 text-white/30" />
                  </div>
                  <input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className={cn(
                      "w-full pl-10 pr-12 py-2.5 rounded border font-mono text-sm",
                      "bg-white/[0.02] border-white/10 text-white/90",
                      "placeholder:text-white/30",
                      "focus:outline-none focus:border-[#00ff9f]/50 focus:ring-1 focus:ring-[#00ff9f]/20",
                      "transition-all",
                      formData.confirmPassword && formData.password === formData.confirmPassword && "border-[#00ff9f]/30"
                    )}
                    placeholder="Re-enter access key"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-white/30 hover:text-white/60 transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {formData.confirmPassword && formData.password === formData.confirmPassword && (
                  <div className="flex items-center gap-1 text-[10px] font-mono text-[#00ff9f]">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Keys match</span>
                  </div>
                )}
              </div>

              {/* Terms */}
              <div className="p-3 rounded border border-white/5 bg-white/[0.01]">
                <p className="text-[10px] font-mono text-white/40 text-center">
                  By creating an account, you agree to our{' '}
                  <Link href="#" className="text-[#00ff9f]/70 hover:text-[#00ff9f]">Terms of Service</Link>
                  {' '}and{' '}
                  <Link href="#" className="text-[#00ff9f]/70 hover:text-[#00ff9f]">Privacy Policy</Link>
                </p>
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
                    <span>PROVISIONING ACCOUNT...</span>
                  </>
                ) : (
                  <>
                    <span>CREATE ACCOUNT</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </form>

            {/* Login Link */}
            <div className="mt-6 pt-6 border-t border-white/10 text-center">
              <p className="text-xs font-mono text-white/40">
                Already have credentials?{' '}
                <Link
                  href="/login"
                  className="text-[#00ff9f] hover:text-[#00ff9f]/80 transition-colors"
                >
                  Sign in here
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
