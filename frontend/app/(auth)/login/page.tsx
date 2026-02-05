'use client';

import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Lock, Mail, Terminal } from 'lucide-react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useEffect, useState } from 'react';

const Activity = dynamic(() => import('lucide-react').then(mod => mod.Activity), { ssr: false });
const ArrowRight = dynamic(() => import('lucide-react').then(mod => mod.ArrowRight), { ssr: false });
const Cpu = dynamic(() => import('lucide-react').then(mod => mod.Cpu), { ssr: false });
const Database = dynamic(() => import('lucide-react').then(mod => mod.Database), { ssr: false });
const Eye = dynamic(() => import('lucide-react').then(mod => mod.Eye), { ssr: false });
const EyeOff = dynamic(() => import('lucide-react').then(mod => mod.EyeOff), { ssr: false });
const RefreshCw = dynamic(() => import('lucide-react').then(mod => mod.RefreshCw), { ssr: false });
const Shield = dynamic(() => import('lucide-react').then(mod => mod.Shield), { ssr: false });
const Sparkles = dynamic(() => import('lucide-react').then(mod => mod.Sparkles), { ssr: false });
const Zap = dynamic(() => import('lucide-react').then(mod => mod.Zap), { ssr: false });

interface LoginFormData {
  email: string;
  password: string;
}

const SYSTEM_LOGS = [
  "Initializing secure handshake...",
  "Verifying biometric signatures...",
  "Loading neural interface modules...",
  "Establishing encrypted tunnel...",
  "Syncing with distributed ledger...",
  "Calibrating quantum sensors...",
  "Optimizing bandwidth allocation...",
  "Scanning for unauthorized nodes..."
];

export default function LoginPage(): React.JSX.Element | null {
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
  const [logIndex, setLogIndex] = useState(0);
  const [enableTilt, setEnableTilt] = useState(false);

  // 3D Tilt Logic
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useTransform(y, [-100, 100], [5, -5]);
  const rotateY = useTransform(x, [-100, 100], [-5, 5]);
  
  const springConfig = { damping: 20, stiffness: 300 };
  const springRotateX = useSpring(rotateX, springConfig);
  const springRotateY = useSpring(rotateY, springConfig);

  function handleMouseMove(event: React.MouseEvent<HTMLDivElement>): void {
    const rect = event.currentTarget.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set(event.clientX - centerX);
    y.set(event.clientY - centerY);
  }

  function handleMouseLeave(): void {
    x.set(0);
    y.set(0);
  }

  useEffect(() => {
    setMounted(true);
    // Defer non-critical animations to improve initial paint
    const tiltTimer = setTimeout(() => {
      // Check for reduced motion preference
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!prefersReducedMotion) {
        setEnableTilt(true);
      }
    }, 100);
    const interval = setInterval(() => {
      setLogIndex((prev) => (prev + 1) % SYSTEM_LOGS.length);
    }, 2000);
    return () => {
      clearTimeout(tiltTimer);
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const features = React.useMemo(() => [
    { icon: Sparkles, text: 'Neural Semantic Search' },
    { icon: Database, text: 'Multimodal Stream Processing' },
    { icon: Zap, text: 'Knowledge Graph Synthesis' },
    { icon: Shield, text: 'Zero-Trust Protocol' },
  ], []);

  // SSR-friendly skeleton to improve LCP - render static content while hydrating
  if (!mounted) {
    return (
      <div className="min-h-screen flex bg-[var(--terminal-bg)] font-sans">
        {/* Left Panel - Static Branding (matches final layout) */}
        <div className="hidden lg:flex lg:w-1/2 relative z-10 flex-col justify-center px-16 lg:px-24 border-r border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30">
          <div className="flex items-center gap-4 mb-16">
            <div className="flex items-center justify-center w-16 h-16 rounded-2xl border border-[var(--phosphor-green)]/30 bg-[var(--terminal-elevated)]">
              <Terminal className="w-8 h-8 text-[var(--phosphor-green)]" />
            </div>
            <div>
              <h1 className="text-4xl font-mono font-bold text-[var(--terminal-text)] tracking-tighter">RAG SYSTEM</h1>
              <p className="text-[10px] font-mono font-bold text-[var(--phosphor-green)]/70 uppercase tracking-[0.3em]">Terminal Observatory V2.4</p>
            </div>
          </div>
          <h2 className="text-6xl font-mono font-bold text-[var(--terminal-text)] leading-[0.9] mb-8 tracking-tight">
            NEURAL DATA<br />
            <span className="text-[var(--phosphor-green)]">SYNTHESIS</span>
          </h2>
          <p className="text-sm font-mono text-[var(--terminal-text-muted)] max-w-md leading-relaxed uppercase tracking-wide border-l-2 border-[var(--phosphor-green)]/30 pl-4 py-2">
            Transforming unstructured streams into actionable intelligence protocols using advanced vector quantization.
          </p>
        </div>
        {/* Right Panel - Loading Form */}
        <div className="flex-1 flex items-center justify-center px-6 lg:px-8 relative z-10">
          <div className="w-full max-w-md">
            <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/90 p-8">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] mb-4">
                  <Lock className="w-5 h-5 text-[var(--phosphor-green)]" />
                </div>
                <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.2em]">Access Protocol</h2>
                <p className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider">Secure Connection Required</p>
              </div>
              <div className="space-y-5 animate-pulse">
                <div className="h-12 rounded-lg bg-[var(--terminal-bg)]" />
                <div className="h-12 rounded-lg bg-[var(--terminal-bg)]" />
                <div className="h-12 rounded-lg bg-[var(--phosphor-green)]/20" />
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-[var(--terminal-bg)] relative overflow-hidden terminal-scanlines crt-flicker font-sans text-foreground selection:bg-[var(--phosphor-green)] selection:text-[var(--terminal-bg)]">
      {/* Star Field & Noise */}
      <div className="absolute inset-0 star-field opacity-60 pointer-events-none" />
      <div className="absolute inset-0 noise-texture opacity-[0.03] pointer-events-none" />
      
      {/* Ambient Orbs */}
      <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-[var(--phosphor-green)]/5 rounded-full blur-[150px] ambient-orb pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-[var(--amber-gold)]/5 rounded-full blur-[120px] ambient-orb-delayed pointer-events-none mix-blend-screen" />

      {/* Dynamic Data Stream Background */}
       <div className="absolute inset-0 opacity-[0.03] pointer-events-none overflow-hidden">
          <div className="absolute top-0 left-[20%] w-[1px] h-full bg-gradient-to-b from-transparent via-[var(--phosphor-green)] to-transparent data-flow-line" style={{ animationDuration: '7s', animationDelay: '1s' }} />
          <div className="absolute top-0 left-[50%] w-[1px] h-full bg-gradient-to-b from-transparent via-[var(--phosphor-green)] to-transparent data-flow-line" style={{ animationDuration: '5s', animationDelay: '3s' }} />
          <div className="absolute top-0 left-[80%] w-[1px] h-full bg-gradient-to-b from-transparent via-[var(--phosphor-green)] to-transparent data-flow-line" style={{ animationDuration: '8s', animationDelay: '0s' }} />
       </div>

      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative z-10 flex-col justify-center px-16 lg:px-24 border-r border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30 backdrop-blur-[2px]">
        {/* Animated Radar - Decorative */}
        <div className="absolute right-[-100px] top-[20%] w-[300px] h-[300px] border border-[var(--phosphor-green)]/10 rounded-full flex items-center justify-center opacity-30 pointer-events-none">
            <div className="w-[80%] h-[80%] border border-[var(--phosphor-green)]/10 rounded-full" />
             <div className="w-[60%] h-[60%] border border-[var(--phosphor-green)]/10 rounded-full" />
             <div className="absolute w-full h-1 bg-gradient-to-r from-transparent via-[var(--phosphor-green)]/20 to-transparent rotate-45 animate-spin-slow" />
        </div>

        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6 }}
            className="relative z-20"
          >
            <div className="flex items-center gap-4 mb-16">
              <div className="relative group">
                 <div className="absolute inset-0 bg-[var(--phosphor-green)]/20 blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                 <div className="relative flex items-center justify-center w-16 h-16 rounded-2xl border border-[var(--phosphor-green)]/30 bg-[var(--terminal-elevated)] shadow-[0_0_30px_rgba(0,255,159,0.1)] overflow-hidden">
                   <div className="absolute inset-0 bg-gradient-to-br from-[var(--phosphor-green)]/10 to-transparent" />
                   <Terminal className="w-8 h-8 text-[var(--phosphor-green)] relative z-10" />
                 </div>
              </div>
              <div>
                <h1 className="text-4xl font-mono font-bold text-[var(--terminal-text)] tracking-tighter glitch-text" data-text="RAG SYSTEM">RAG SYSTEM</h1>
                <div className="flex items-center gap-2 mt-1">
                   <div className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
                   <p className="text-[10px] font-mono font-bold text-[var(--phosphor-green)]/70 uppercase tracking-[0.3em]">Terminal Observatory V2.4</p>
                </div>
              </div>
            </div>

            <h2 className="text-6xl font-mono font-bold text-[var(--terminal-text)] leading-[0.9] mb-8 tracking-tight">
              NEURAL DATA<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[var(--phosphor-green)] via-[var(--cyan)] to-[var(--phosphor-green)] bg-[length:200%_auto] animate-gradient">
                SYNTHESIS
              </span>
            </h2>
            <p className="text-sm font-mono text-[var(--terminal-text-muted)] max-w-md mb-12 leading-relaxed uppercase tracking-wide border-l-2 border-[var(--phosphor-green)]/30 pl-4 py-2">
              Transforming unstructured streams into actionable intelligence protocols using advanced vector quantization.
            </p>

            <div className="grid grid-cols-2 gap-6">
              {features.map((feature, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.4 + (i * 0.1) }}
                  className="flex items-center gap-3 group p-3 rounded-lg border border-transparent hover:border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)] transition-all duration-300"
                >
                  <div className="flex items-center justify-center w-8 h-8 rounded-md bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] group-hover:border-[var(--phosphor-green)]/50 group-hover:shadow-[0_0_15px_rgba(0,255,159,0.15)] transition-all">
                    <feature.icon className="w-4 h-4 text-[var(--phosphor-green)] group-hover:scale-110 transition-transform" />
                  </div>
                  <span className="text-[10px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-widest group-hover:text-[var(--terminal-text)] transition-colors">{feature.text}</span>
                </motion.div>
              ))}
            </div>
            
            {/* System Logs */}
            <div className="mt-16 font-mono text-[9px] text-[var(--terminal-text-muted)] border-t border-[var(--terminal-border)] pt-4 opacity-70">
                <div className="flex justify-between items-center mb-2">
                    <span className="uppercase tracking-wider">System Activity Log</span>
                    <span className="animate-pulse text-[var(--phosphor-green)]">● LIVE</span>
                </div>
                <div className="space-y-1 h-16 overflow-hidden relative">
                    <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--terminal-bg)] z-10" />
                     <AnimatePresence mode="popLayout">
                        <motion.div
                            key={logIndex}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="flex items-center gap-2"
                        >
                            <span className="text-[var(--phosphor-green)] opacity-50">{'>'}</span>
                            <span>{SYSTEM_LOGS[logIndex]}</span>
                        </motion.div>
                        <motion.div
                             key={logIndex - 1}
                             initial={{ opacity: 0.5 }}
                             animate={{ opacity: 0.3, y: -15 }}
                             className="flex items-center gap-2 absolute top-0 w-full"
                         >
                             <span className="text-[var(--phosphor-green)] opacity-30">{'>'}</span>
                             <span>{SYSTEM_LOGS[(logIndex - 1 + SYSTEM_LOGS.length) % SYSTEM_LOGS.length]}</span>
                         </motion.div>
                    </AnimatePresence>
                </div>
            </div>
          </motion.div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-8 relative z-10">
        <div style={{ perspective: "1000px" }} className="w-full max-w-md">
            <motion.div
              style={enableTilt ? { rotateX: springRotateX, rotateY: springRotateY, transformStyle: "preserve-3d" } : undefined}
              onMouseMove={enableTilt ? handleMouseMove : undefined}
              onMouseLeave={enableTilt ? handleMouseLeave : undefined}
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="relative group"
            >
              {/* Mobile Logo */}
              <div className="lg:hidden flex items-center justify-center gap-4 mb-8">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg border border-[var(--phosphor-green)]/30 bg-[var(--phosphor-green)]/10">
                  <Terminal className="w-5 h-5 text-[var(--phosphor-green)]" />
                </div>
                <span className="text-xl font-mono font-bold text-[var(--terminal-text)]">RAG_SYS</span>
              </div>

              {/* Holographic Form Container */}
              <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/90 backdrop-blur-xl p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)] relative overflow-hidden">
                {/* Decorative Elements */}
                <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-[var(--phosphor-green)]/10 to-transparent pointer-events-none" />
                <div className="absolute bottom-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[var(--phosphor-green)]/20 to-transparent" />
                <div className="scan-beam opacity-30" />
                
                {/* Form Header */}
                <div className="text-center mb-8 relative">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[var(--terminal-elevated)] border border-[var(--terminal-border)] mb-4 shadow-inner">
                        <Lock className="w-5 h-5 text-[var(--phosphor-green)]" />
                    </div>
                  <h2 className="text-xl font-mono font-bold text-[var(--terminal-text)] uppercase tracking-[0.2em] mb-1">Access Protocol</h2>
                  <p className="text-[10px] text-[var(--terminal-text-muted)] uppercase tracking-wider">Secure Connection Required</p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="space-y-5 relative z-10">
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 flex items-start gap-3"
                    >
                      <Activity className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                      <div>
                          <p className="text-[10px] font-mono text-red-400 font-bold uppercase tracking-tighter">Authentication Error</p>
                          <p className="text-[11px] text-red-300/80">{error}</p>
                      </div>
                    </motion.div>
                  )}

                  {/* Email Field */}
                  <div className="space-y-1.5">
                    <label htmlFor="email" className="flex items-center justify-between text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold pl-1">
                      <span>User Identifier</span>
                      <span className="text-[var(--phosphor-green)] opacity-50 text-[8px]">{formData.email.length > 0 ? 'ACTIVE' : 'REQUIRED'}</span>
                    </label>
                    <div className="relative group/input">
                      <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none transition-colors group-focus-within/input:text-[var(--phosphor-green)]">
                        <Mail className="w-4 h-4 text-[var(--terminal-text-muted)] group-focus-within/input:text-[var(--phosphor-green)] transition-colors" />
                      </div>
                      <input
                        id="email"
                        name="email"
                        type="email"
                        required
                        value={formData.email}
                        onChange={handleChange}
                        className="w-full pl-11 pr-4 py-3 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-1 focus:ring-[var(--phosphor-green)]/20 transition-all outline-none group-hover/input:border-[var(--terminal-border-glow)]"
                        placeholder="UID@DOMAIN.COM"
                        autoComplete="email"
                      />
                      <div className="absolute inset-0 rounded-lg bg-[var(--phosphor-green)]/5 opacity-0 group-focus-within/input:opacity-100 pointer-events-none transition-opacity duration-500" />
                    </div>
                  </div>

                  {/* Password Field */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between pl-1">
                      <label htmlFor="password" className="block text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] font-bold">
                        Security Key
                      </label>
                      <Link href="/forgot-password" className="text-[9px] text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors">
                        RECOVER_KEY?
                      </Link>
                    </div>
                    <div className="relative group/input">
                      <div className="absolute inset-y-0 left-0 flex items-center pl-3.5 pointer-events-none">
                        <Lock className="w-4 h-4 text-[var(--terminal-text-muted)] group-focus-within/input:text-[var(--phosphor-green)] transition-colors" />
                      </div>
                      <input
                        id="password"
                        name="password"
                        type={showPassword ? 'text' : 'password'}
                        required
                        value={formData.password}
                        onChange={handleChange}
                        className="w-full pl-11 pr-12 py-3 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] font-mono text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)]/30 focus:border-[var(--phosphor-green)]/50 focus:ring-1 focus:ring-[var(--phosphor-green)]/20 transition-all outline-none group-hover/input:border-[var(--terminal-border-glow)]"
                        placeholder="••••••••••••"
                        autoComplete="current-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      <div className="absolute inset-0 rounded-lg bg-[var(--phosphor-green)]/5 opacity-0 group-focus-within/input:opacity-100 pointer-events-none transition-opacity duration-500" />
                    </div>
                  </div>

                  {/* Submit Button */}
                  <div className="pt-2">
                      <button
                        type="submit"
                        disabled={isSubmitting}
                        className={cn(
                          "group w-full flex items-center justify-center gap-3 py-3.5 px-4 rounded-lg font-mono text-xs font-bold uppercase tracking-[0.2em] relative overflow-hidden",
                          "bg-[var(--phosphor-green)] text-[var(--terminal-bg)]",
                          "hover:shadow-[0_0_20px_var(--phosphor-green-glow)] transform active:scale-[0.98]",
                          "disabled:opacity-70 disabled:cursor-not-allowed transition-all duration-300"
                        )}
                      >
                        <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                        
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
                  </div>
                </form>

                {/* Footer Links */}
                <div className="mt-8 flex items-center justify-between pt-6 border-t border-[var(--terminal-border)]">
                  <div className="flex items-center gap-2 text-[9px] text-[var(--terminal-text-dim)]">
                      <Cpu className="w-3 h-3" />
                      <span>SECURE_ENCLAVE_ACTIVE</span>
                  </div>
                  <Link
                    href="/register"
                    className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest hover:text-[var(--phosphor-green)] transition-colors flex items-center gap-1 group"
                  >
                    <span>New Node Registration</span>
                    <span className="opacity-0 group-hover:opacity-100 transition-opacity">→</span>
                  </Link>
                </div>
              </div>
            </motion.div>
        </div>
      </div>
    </div>
  );
}
