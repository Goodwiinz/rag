'use client';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import {
  Activity,
  ArrowRight,
  Brain,
  ChevronRight,
  Cpu,
  Database,
  FileText,
  Globe,
  Layers,
  LayoutDashboard,
  Lock,
  Network,
  Radio,
  Satellite,
  Search,
  Shield,
  Sparkles,
  Terminal,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [terminalText, setTerminalText] = useState('');

  // Hydration-safe mounting
  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'SYSTEM_ONLINE :: WAITING_FOR_INPUT';
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

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-hidden flex flex-col star-field terminal-grid noise-texture">
      {/* Navigation Header */}
      <nav className="relative z-40 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/80 backdrop-blur-xl h-14 shrink-0">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20">
              <Terminal className="w-4 h-4 text-[var(--phosphor-green)]" />
            </div>
            <div className="flex flex-col">
              <span className="font-mono font-bold text-[var(--terminal-text)] text-sm uppercase tracking-tighter leading-none">RAG_OS</span>
              <span className="font-mono text-[9px] text-[var(--terminal-text-dim)] uppercase tracking-widest leading-none mt-0.5">Terminal Observatory</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link href="/dashboard">
                <Button size="sm" className="h-8 font-mono text-[10px] font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_15px_var(--phosphor-green-glow)] transition-all">
                  <LayoutDashboard className="w-3 h-3 mr-2" />
                  ENTER_CONSOLE
                </Button>
              </Link>
            ) : (
              <div className="flex gap-3">
                <Link href="/login">
                  <Button size="sm" variant="ghost" className="h-8 font-mono text-[10px] text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/5">
                    AUTHENTICATE
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="sm" className="h-8 font-mono text-[10px] font-bold border border-[var(--phosphor-green)]/30 text-[var(--phosphor-green)] bg-transparent hover:bg-[var(--phosphor-green)]/10">
                    REQ_ACCESS
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col items-center justify-center relative p-6">
        
        {/* Central Orbital Hero */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8 }}
          className="relative mb-12"
        >
          {/* Orbital Rings */}
          <div className="relative flex items-center justify-center h-80 w-80">
             <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-64 h-64 rounded-full border border-[var(--terminal-border)] animate-[spin_60s_linear_infinite]" />
             </div>
             <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-48 h-48 rounded-full border border-[var(--phosphor-green)]/20 animate-[spin_40s_linear_infinite_reverse]" />
             </div>
             <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-32 h-32 rounded-full border border-[var(--phosphor-green)]/40 animate-[spin_20s_linear_infinite]" />
             </div>
             
             {/* Central Core */}
             <div className="relative z-10 p-8 rounded-full bg-[var(--terminal-bg)]/80 backdrop-blur-xl border border-[var(--phosphor-green)]/30 shadow-[0_0_30px_rgba(0,255,159,0.15)] group">
                <Satellite className="w-16 h-16 text-[var(--phosphor-green)] float-gentle drop-shadow-[0_0_10px_var(--phosphor-green)]" />
                <div className="absolute inset-0 rounded-full border border-[var(--phosphor-green)]/50 scale-110 opacity-0 group-hover:opacity-100 group-hover:scale-100 transition-all duration-500" />
             </div>

             {/* Radar Sweep */}
             <div className="absolute inset-0 rounded-full bg-gradient-to-t from-transparent via-[var(--phosphor-green)]/5 to-transparent opacity-30 animate-spin-slow pointer-events-none mix-blend-screen" />
          </div>
        </motion.div>

        {/* Hero Text */}
        <div className="text-center max-w-2xl mb-16 relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded border border-[var(--phosphor-green)]/20 bg-[var(--phosphor-green)]/5 mb-6"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
            <span className="font-mono text-[10px] text-[var(--phosphor-green)] font-bold tracking-widest uppercase">
              {terminalText}
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-4xl md:text-5xl font-mono font-bold text-[var(--terminal-text)] mb-6 tracking-tight"
          >
            MULTIMODAL <span className="text-[var(--phosphor-green)]">INTELLIGENCE</span>
            <br />
            <span className="text-[var(--terminal-text-dim)] text-2xl md:text-3xl">GRID SYSTEM v2.0</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="text-xs md:text-sm font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider leading-relaxed max-w-lg mx-auto"
          >
            Enterprise-grade RAG pipeline featuring local LLM inference, semantic vector search, and knowledge graph extraction.
          </motion.p>
        </div>

        {/* Feature Grid */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 max-w-6xl w-full px-4"
        >
          {[
            { 
              icon: Brain, 
              title: "LOCAL_INFERENCE", 
              desc: "On-device LLM processing with WebLLM",
              color: "text-[var(--phosphor-green)]",
              border: "group-hover:border-[var(--phosphor-green)]/40"
            },
            { 
              icon: Network, 
              title: "KNOWLEDGE_GRAPH", 
              desc: "Semantic entity extraction & linking",
              color: "text-[var(--cyan)]",
              border: "group-hover:border-[var(--cyan)]/40"
            },
            { 
              icon: Database, 
              title: "VECTOR_INDEX", 
              desc: "High-dimensional similarity search",
              color: "text-[var(--amber-gold)]",
              border: "group-hover:border-[var(--amber-gold)]/40"
            },
            { 
              icon: Shield, 
              title: "SECURE_PIPELINE", 
              desc: "Zero-trust architecture & encryption",
              color: "text-[var(--terminal-text)]",
              border: "group-hover:border-[var(--terminal-text)]/40"
            }
          ].map((item, idx) => (
            <div 
              key={idx}
              className={`p-5 rounded-xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] transition-all duration-300 group hover:-translate-y-1 hover:shadow-lg ${item.border}`}
            >
              <div className={`mb-4 p-2 w-fit rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] ${item.color}`}>
                <item.icon className="w-5 h-5" />
              </div>
              <h3 className="text-xs font-bold font-mono text-[var(--terminal-text)] mb-2 tracking-wider">
                {item.title}
              </h3>
              <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] leading-relaxed">
                {item.desc}
              </p>
            </div>
          ))}
        </motion.div>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
          className="mt-16 flex flex-wrap justify-center gap-6"
        >
          <Link href="/documents/upload">
            <Button size="lg" className="h-12 px-8 font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)] hover:bg-[var(--phosphor-green-dim)]">
              INITIATE_UPLOAD
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
          <Link href="/chat">
            <Button size="lg" variant="outline" className="h-12 px-8 font-mono text-xs font-bold border-[var(--terminal-border)] text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] hover:border-[var(--phosphor-green)]/30">
              LAUNCH_TERMINAL
              <Terminal className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        </motion.div>

      </div>

      {/* Technical Footer */}
      <footer className="border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/90 backdrop-blur-sm p-2 shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)]" />
              SYSTEM_OPTIMAL
            </span>
            <span className="hidden sm:inline">LATENCY: 12ms</span>
          </div>
          <div className="flex items-center gap-4">
            <span>REGION: US-EAST-1</span>
            <span>BUILD: v2.0.1-ALPHA</span>
          </div>
        </div>
      </footer>
    </div>
  );
}