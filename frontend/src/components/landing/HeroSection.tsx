'use client';

import { HeroAgentCard } from '@/components/hero-agent-card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { MotionValue } from 'framer-motion';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Box,
  Brain,
  Database,
  FileCode,
  LayoutDashboard,
  Link as LinkIcon,
  Lock,
  Network,
  Share2,
  Shield,
  Terminal,
  Zap,
} from 'lucide-react';
import Link from 'next/link';

// --- Helper Components ---

const Badge = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <div
    className={cn(
      'inline-flex items-center px-3 py-1 rounded border text-[10px] font-mono font-bold uppercase tracking-widest backdrop-blur-md',
      className
    )}
  >
    {children}
  </div>
);

const TechTicker = () => {
  const techs = [
    { name: 'PYTHON', icon: FileCode },
    { name: 'REACT', icon: Box },
    { name: 'OPENAI', icon: Brain },
    { name: 'LANGCHAIN', icon: LinkIcon },
    { name: 'PINECONE', icon: Database },
    { name: 'DOCKER', icon: Box },
    { name: 'KUBERNETES', icon: Network },
    { name: 'GRAPHQL', icon: Share2 },
  ];

  return (
    <div className="w-full bg-[var(--terminal-bg)] border-y border-[var(--terminal-border)] overflow-hidden py-4 relative">
      <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-[var(--terminal-bg)] to-transparent z-10" />
      <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-[var(--terminal-bg)] to-transparent z-10" />

      <motion.div
        className="flex gap-12 whitespace-nowrap"
        animate={{ x: [0, -1000] }}
        transition={{ repeat: Infinity, duration: 40, ease: 'linear' }}
      >
        {[...techs, ...techs, ...techs].map((tech, i) => (
          <div
            key={i}
            className="flex items-center gap-3 opacity-30 hover:opacity-100 transition-opacity cursor-default group"
          >
            <tech.icon className="w-5 h-5 group-hover:text-[var(--phosphor-green)] transition-colors" />
            <span className="font-mono text-xs font-bold tracking-widest text-[var(--terminal-text)]">
              {tech.name}
            </span>
          </div>
        ))}
      </motion.div>
    </div>
  );
};

// --- Main Component ---

interface HeroSectionProps {
  isAuthenticated: boolean;
  scrollOpacity: MotionValue<number>;
}

export function HeroSection({ isAuthenticated, scrollOpacity }: HeroSectionProps) {
  return (
    <>
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/80 backdrop-blur-xl h-16">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-3 group cursor-pointer">
            <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 overflow-hidden">
              <div className="absolute inset-0 bg-[var(--phosphor-green)]/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
              <Terminal className="w-5 h-5 text-[var(--phosphor-green)] relative z-10" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-[var(--terminal-text)] text-sm uppercase tracking-[0.18em] leading-none group-hover:text-[var(--phosphor-green)] transition-colors">
                NOUS
              </span>
              <span className="font-mono text-[9px] text-[var(--phosphor-green)]/60 uppercase tracking-[0.12em] leading-none mt-1">
                Multimodal Intelligence
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-6 mr-6">
              {['Features', 'Architecture', 'Docs'].map((item) => (
                <button
                  key={item}
                  className="text-[11px] font-mono font-medium text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] uppercase tracking-wider transition-colors"
                >
                  {item}
                </button>
              ))}
            </div>
            {isAuthenticated ? (
              <Link href="/dashboard">
                <Button
                  size="sm"
                  className="h-9 font-mono text-[10px] font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)] hover:scale-105 transition-all"
                >
                  <LayoutDashboard className="w-3.5 h-3.5 mr-2" />
                  ENTER_CONSOLE
                </Button>
              </Link>
            ) : (
              <div className="flex gap-3">
                <Link href="/login">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-9 font-mono text-[10px] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]"
                  >
                    LOG_IN
                  </Button>
                </Link>
                <Link href="/register">
                  <Button
                    size="sm"
                    className="h-9 font-mono text-[10px] font-bold border border-[var(--terminal-border)] text-[var(--terminal-text)] bg-[var(--terminal-surface)] hover:bg-[var(--terminal-elevated)] hover:border-[var(--phosphor-green)]/50 transition-all"
                  >
                    REQ_ACCESS
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 pt-32 pb-24 md:pt-48 md:pb-32 px-6 overflow-visible">
        {/* Background Glow */}
        <div className="absolute top-1/2 right-0 -translate-y-1/2 translate-x-1/4 w-[800px] h-[800px] bg-[var(--phosphor-green)]/5 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute top-1/4 right-1/4 w-[400px] h-[400px] bg-[var(--cyan)]/5 rounded-full blur-[100px] pointer-events-none" />

        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center relative">
          {/* Decorative Corner Brackets */}
          <div className="absolute -top-10 -left-10 w-20 h-20 border-l-2 border-t-2 border-[var(--terminal-border)] opacity-50" />
          <div className="absolute -bottom-10 -right-10 w-20 h-20 border-r-2 border-b-2 border-[var(--terminal-border)] opacity-50" />

          <motion.div
            style={{ opacity: scrollOpacity }}
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: 'circOut' }}
            className="relative z-10"
          >
            <div className="inline-flex items-center gap-2 mb-8 px-3 py-1.5 rounded-full border border-[var(--phosphor-green)]/20 bg-[var(--phosphor-green)]/5 backdrop-blur-md">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--phosphor-green)] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--phosphor-green)]"></span>
              </span>
              <span className="font-mono text-[10px] font-bold text-[var(--phosphor-green)] tracking-widest uppercase">
                SYSTEM_ONLINE_v2.0
              </span>
            </div>

            <h1 className="text-5xl md:text-7xl lg:text-8xl font-mono font-bold text-[var(--terminal-text)] mb-8 tracking-tighter leading-[0.9]">
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-[var(--phosphor-green)] via-[var(--amber-gold)] to-[var(--phosphor-green)] bg-[length:200%_auto] animate-shine">
                νοῦς
              </span>
              <span className="block text-[0.4em] tracking-[0.2em] text-[var(--terminal-text-dim)] mt-2 uppercase">
                Multimodal Intelligence
              </span>
            </h1>

            <p className="text-base md:text-lg font-mono text-[var(--terminal-text-muted)] leading-relaxed max-w-xl mb-10 border-l-2 border-[var(--phosphor-green)]/30 pl-6">
              Semantic search, knowledge graph extraction, and AI-powered
              research workflows —{' '}
              <span className="text-[var(--terminal-text)] font-bold">
                unified in one neural architecture
              </span>
              .
            </p>

            <div className="flex flex-wrap gap-5">
              <Link href="/documents/upload">
                <Button
                  size="lg"
                  className="h-14 px-8 font-mono text-sm font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_30px_var(--phosphor-green-glow)] hover:bg-[var(--phosphor-green)] hover:-translate-y-1 transition-all duration-300 group rounded-none border border-[var(--phosphor-green)]"
                >
                  INITIATE_PIPELINE
                  <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link href="/search">
                <Button
                  size="lg"
                  variant="outline"
                  className="h-14 px-8 font-mono text-sm font-bold border-[var(--terminal-border)] text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] hover:border-[var(--terminal-text)] backdrop-blur-sm rounded-none transition-all duration-300"
                >
                  LIVE_DEMO
                </Button>
              </Link>
            </div>

            <div className="mt-16 pt-8 border-t border-[var(--terminal-border)] flex flex-wrap items-center gap-8 text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-wider">
              <div className="flex items-center gap-2 group cursor-help">
                <div className="p-1 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] group-hover:border-[var(--terminal-text-muted)] transition-colors">
                  <Shield className="w-3.5 h-3.5 text-[var(--terminal-text-muted)]" />
                </div>
                <span>SOC2_READY</span>
              </div>
              <div className="flex items-center gap-2 group cursor-help">
                <div className="p-1 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] group-hover:border-[var(--amber-gold)] transition-colors">
                  <Zap className="w-3.5 h-3.5 text-[var(--amber-gold)]" />
                </div>
                <span>&lt;20MS_LATENCY</span>
              </div>
              <div className="flex items-center gap-2 group cursor-help">
                <div className="p-1 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] group-hover:border-[var(--cyan)] transition-colors">
                  <Lock className="w-3.5 h-3.5 text-[var(--cyan)]" />
                </div>
                <span>E2E_ENCRYPTED</span>
              </div>
            </div>
          </motion.div>

          {/* Hero Visual - Layered HUD */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.2 }}
            className="relative h-[500px] lg:h-[600px] flex items-center justify-center pointer-events-none"
          >
            <div className="relative w-full max-w-[600px] aspect-square">
              {/* Concentric Rings */}
              <div className="absolute inset-0 rounded-full border border-[var(--terminal-border)] opacity-20 animate-[spin_120s_linear_infinite]" />
              <div className="absolute inset-12 rounded-full border border-dashed border-[var(--terminal-border)] opacity-20 animate-[spin_60s_linear_infinite_reverse]" />
              <div className="absolute inset-32 rounded-full border border-[var(--phosphor-green)] opacity-5 animate-[spin_30s_linear_infinite]" />

              {/* Floating Cards Depth */}

              {/* Card 2 (Background) */}
              <motion.div
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.5 }}
                className="absolute top-[40%] right-[10%] w-64 p-4 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] opacity-40 blur-[2px] z-0"
              >
                <div className="flex items-center gap-2 mb-2 border-b border-[var(--terminal-border)] pb-2">
                  <div className="w-3 h-3 rounded-full bg-[var(--terminal-text-muted)]" />
                  <div className="h-1.5 w-16 bg-[var(--terminal-border-muted)] rounded" />
                </div>
              </motion.div>

              {/* Card 1 (Main) */}
              <motion.div
                animate={{ y: [-15, 5, -15] }}
                transition={{
                  repeat: Infinity,
                  duration: 6,
                  ease: 'easeInOut',
                }}
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20"
              >
                <HeroAgentCard />
              </motion.div>

              {/* Decorative Elements */}
              <div className="absolute top-20 right-10 p-3 rounded-xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] animate-float-delayed shadow-xl">
                <Database className="w-6 h-6 text-[var(--cyan)]" />
              </div>
              <div className="absolute bottom-20 left-10 p-3 rounded-xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] animate-float shadow-xl">
                <Network className="w-6 h-6 text-[var(--amber-gold)]" />
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Ecosystem Ticker */}
      <TechTicker />
    </>
  );
}
