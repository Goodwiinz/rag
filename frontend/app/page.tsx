'use client';

import { HeroAgentCard } from '@/components/hero-agent-card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
  Activity,
  ArrowRight,
  Box,
  Brain,
  Command,
  Cpu,
  Database,
  FileCode,
  Globe,
  LayoutDashboard,
  Link as LinkIcon,
  Lock,
  Network,
  Share2,
  Shield,
  Terminal,
  Zap
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

// --- Components ---

const Badge = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn("inline-flex items-center px-3 py-1 rounded border text-[10px] font-mono font-bold uppercase tracking-widest backdrop-blur-md", className)}>
    {children}
  </div>
);

const FeatureCard = ({ title, desc, icon: Icon, color, delay }: any) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ delay, duration: 0.5 }}
    className="group relative p-6 rounded-2xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] overflow-hidden hover:border-[var(--phosphor-green)]/30 transition-all duration-500"
  >
    <div className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[${color}] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
    <div className="mb-6 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] group-hover:scale-110 transition-transform duration-500">
      <Icon className="w-6 h-6" style={{ color }} />
    </div>
    <h3 className="text-lg font-bold font-mono text-[var(--terminal-text)] mb-3 tracking-tight group-hover:text-[var(--phosphor-green)] transition-colors">
      {title}
    </h3>
    <p className="text-sm font-mono text-[var(--terminal-text-muted)] leading-relaxed">
      {desc}
    </p>
  </motion.div>
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
        transition={{ repeat: Infinity, duration: 40, ease: "linear" }}
      >
        {[...techs, ...techs, ...techs].map((tech, i) => (
          <div key={i} className="flex items-center gap-3 opacity-30 hover:opacity-100 transition-opacity cursor-default group">
            <tech.icon className="w-5 h-5 group-hover:text-[var(--phosphor-green)] transition-colors" />
            <span className="font-mono text-xs font-bold tracking-widest text-[var(--terminal-text)]">{tech.name}</span>
          </div>
        ))}
      </motion.div>
    </div>
  );
};

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);
  const { scrollYProgress } = useScroll();

  const y = useTransform(scrollYProgress, [0, 1], ['0%', '20%']);
  const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-x-hidden flex flex-col noise-texture selection:bg-[var(--phosphor-green)] selection:text-[var(--terminal-bg)]">

      {/* Dynamic Background */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(0,255,159,0.03),transparent_50%)]" />
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[var(--terminal-border)] to-transparent opacity-20" />
        <div className="hidden md:block absolute inset-0 terminal-grid opacity-[0.03]" />
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/80 backdrop-blur-xl h-16">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-3 group cursor-pointer">
            <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 overflow-hidden">
              <div className="absolute inset-0 bg-[var(--phosphor-green)]/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
              <Terminal className="w-5 h-5 text-[var(--phosphor-green)] relative z-10" />
            </div>
            <div className="flex flex-col">
              <span className="font-mono font-bold text-[var(--terminal-text)] text-sm uppercase tracking-tighter leading-none group-hover:text-[var(--phosphor-green)] transition-colors">RAG_OS</span>
              <span className="font-mono text-[10px] text-[var(--terminal-text-dim)] uppercase tracking-widest leading-none mt-1">Terminal Observatory</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
             <div className="hidden md:flex items-center gap-6 mr-6">
                {['Features', 'Architecture', 'Docs'].map((item) => (
                    <button key={item} className="text-[11px] font-mono font-medium text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] uppercase tracking-wider transition-colors">
                        {item}
                    </button>
                ))}
             </div>
            {isAuthenticated ? (
              <Link href="/dashboard">
                <Button size="sm" className="h-9 font-mono text-[10px] font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)] hover:scale-105 transition-all">
                  <LayoutDashboard className="w-3.5 h-3.5 mr-2" />
                  ENTER_CONSOLE
                </Button>
              </Link>
            ) : (
              <div className="flex gap-3">
                <Link href="/login">
                  <Button size="sm" variant="ghost" className="h-9 font-mono text-[10px] text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]">
                    LOG_IN
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="sm" className="h-9 font-mono text-[10px] font-bold border border-[var(--terminal-border)] text-[var(--terminal-text)] bg-[var(--terminal-surface)] hover:bg-[var(--terminal-elevated)] hover:border-[var(--phosphor-green)]/50 transition-all">
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
            style={{ opacity }}
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: "circOut" }}
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
              Information
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-[var(--phosphor-green)] via-[var(--cyan)] to-[var(--phosphor-green)] bg-[length:200%_auto] animate-shine">
                Architecture
              </span>
            </h1>

            <p className="text-base md:text-lg font-mono text-[var(--terminal-text-muted)] leading-relaxed max-w-xl mb-10 border-l-2 border-[var(--terminal-border)] pl-6">
              Deploy an enterprise-grade <span className="text-[var(--terminal-text)] font-bold">Semantic Search Pipeline</span> in minutes.
              Local inference, knowledge graph extraction, and zero-trust security architecture.
            </p>

            <div className="flex flex-wrap gap-5">
              <Link href="/documents/upload">
                <Button size="lg" className="h-14 px-8 font-mono text-sm font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_30px_var(--phosphor-green-glow)] hover:bg-[var(--phosphor-green)] hover:-translate-y-1 transition-all duration-300 group rounded-none border border-[var(--phosphor-green)]">
                  INITIATE_PIPELINE
                  <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link href="/search">
                <Button size="lg" variant="outline" className="h-14 px-8 font-mono text-sm font-bold border-[var(--terminal-border)] text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)] hover:border-[var(--terminal-text)] backdrop-blur-sm rounded-none transition-all duration-300">
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
                    transition={{ repeat: Infinity, duration: 6, ease: "easeInOut" }}
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

      {/* Core Capabilities - Bento Grid */}
      <section className="py-24 px-6 relative z-10">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-6">
            <div>
              <h2 className="text-3xl md:text-4xl font-mono font-bold text-[var(--terminal-text)] mb-4">
                CORE_CAPABILITIES
              </h2>
              <p className="font-mono text-[var(--terminal-text-muted)] max-w-xl">
                Advanced structural components powering the next generation of knowledge retrieval.
              </p>
            </div>
            <Button variant="ghost" className="font-mono text-xs border border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)]">
              VIEW_DOCUMENTATION <ArrowRight className="w-3 h-3 ml-2" />
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[300px]">
            {/* Large Card */}
            <motion.div
               initial={{ opacity: 0, y: 20 }}
               whileInView={{ opacity: 1, y: 0 }}
               viewport={{ once: true }}
               className="md:col-span-2 rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 relative overflow-hidden group"
            >
               <div className="absolute inset-0 bg-gradient-to-br from-[var(--terminal-surface)] via-transparent to-[var(--phosphor-green)]/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
               <div className="relative z-10 h-full flex flex-col justify-between">
                  <div>
                    <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                      <Network className="w-6 h-6 text-[var(--phosphor-green)]" />
                    </div>
                    <h3 className="text-2xl font-mono font-bold text-[var(--terminal-text)] mb-2">Neural Knowledge Graph</h3>
                    <p className="font-mono text-[var(--terminal-text-muted)] text-sm max-w-md">
                        Automatically extract entities and relationships from unstructured text. Visualize complex data reliability chains in real-time.
                    </p>
                  </div>
                  <div className="w-full h-32 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] relative overflow-hidden">
                       <div className="absolute inset-0 flex items-center justify-center opacity-30">
                           <div className="w-full h-full terminal-grid animate-[pulse_4s_ease-in-out_infinite]" />
                       </div>
                       {/* Mock Graph Nodes */}
                       <div className="absolute top-1/2 left-1/4 w-3 h-3 rounded-full bg-[var(--phosphor-green)] shadow-[0_0_10px_var(--phosphor-green)]" />
                       <div className="absolute top-1/3 left-1/2 w-2 h-2 rounded-full bg-[var(--cyan)]" />
                       <div className="absolute top-2/3 right-1/3 w-2 h-2 rounded-full bg-[var(--amber-gold)]" />
                       <svg className="absolute inset-0 w-full h-full pointer-events-none stroke-[var(--terminal-border)] opacity-50">
                          <line x1="25%" y1="50%" x2="50%" y2="33%" />
                          <line x1="50%" y1="33%" x2="66%" y2="66%" />
                       </svg>
                  </div>
               </div>
            </motion.div>

            {/* Tall Card */}
            <motion.div
               initial={{ opacity: 0, y: 20 }}
               whileInView={{ opacity: 1, y: 0 }}
               viewport={{ once: true }}
               transition={{ delay: 0.1 }}
               className="md:row-span-2 rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 relative overflow-hidden group"
            >
                <div className="absolute top-0 right-0 p-32 bg-[var(--cyan)]/5 blur-3xl rounded-full translate-x-12 -translate-y-12" />
                <div className="relative z-10 h-full flex flex-col">
                    <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                      <Cpu className="w-6 h-6 text-[var(--cyan)]" />
                    </div>
                    <h3 className="text-2xl font-mono font-bold text-[var(--terminal-text)] mb-2">Local Inference</h3>
                    <p className="font-mono text-[var(--terminal-text-muted)] text-sm mb-8">
                        Privacy-first LLM execution directly in the browser via WebLLM. No data leaves your infrastructure.
                    </p>

                    <div className="flex-1 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] p-4 font-mono text-xs space-y-4 overflow-hidden">
                         <div className="flex justify-between text-[var(--terminal-text-dim)] border-b border-[var(--terminal-border-muted)] pb-2">
                            <span>MODEL_STATUS</span>
                            <span className="text-[var(--phosphor-green)]">READY</span>
                         </div>
                         <div className="space-y-2">
                            {['Loading weights...', 'Initializing WebGPU...', 'Compiling shaders...', 'Inference ready.'].map((log, i) => (
                                <div key={i} className="flex gap-3 items-center opacity-70">
                                    <span className="text-[var(--terminal-text-muted)]">{`00:0${i+1}`}</span>
                                    <span className="text-[var(--terminal-text)]">{log}</span>
                                </div>
                            ))}
                            <div className="flex gap-2 items-center mt-4">
                                <span className="text-[var(--phosphor-green)]">{'>'}</span>
                                <span className="animate-pulse bg-[var(--phosphor-green)] w-2 h-4 block" />
                            </div>
                         </div>
                    </div>
                </div>
            </motion.div>

            {/* Small Card 1 */}
            <motion.div
               initial={{ opacity: 0, y: 20 }}
               whileInView={{ opacity: 1, y: 0 }}
               viewport={{ once: true }}
               transition={{ delay: 0.2 }}
               className="rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 group hover:border-[var(--amber-gold)]/30 transition-colors"
            >
               <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                   <Zap className="w-6 h-6 text-[var(--amber-gold)]" />
               </div>
               <h3 className="text-xl font-mono font-bold text-[var(--terminal-text)] mb-2">Vector Search</h3>
               <p className="font-mono text-[var(--terminal-text-muted)] text-xs">
                HNSW index optimization for millisecond-latency retrieval across millions of vectors.
               </p>
            </motion.div>

            {/* Small Card 2 */}
            <motion.div
               initial={{ opacity: 0, y: 20 }}
               whileInView={{ opacity: 1, y: 0 }}
               viewport={{ once: true }}
               transition={{ delay: 0.3 }}
               className="rounded-3xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] p-8 group hover:border-[var(--terminal-text)]/30 transition-colors"
            >
               <div className="mb-4 p-3 w-fit rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                   <Lock className="w-6 h-6 text-[var(--terminal-text)]" />
               </div>
               <h3 className="text-xl font-mono font-bold text-[var(--terminal-text)] mb-2">Zero Trust</h3>
               <p className="font-mono text-[var(--terminal-text-muted)] text-xs">
                Role-based access control (RBAC) integrated directly into the retrieval pipeline.
               </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* System Metrics CTA */}
      <section className="py-24 border-y border-[var(--terminal-border)] bg-[var(--terminal-surface)] relative overflow-hidden">
         <div className="absolute inset-0 opacity-10">
             <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,var(--terminal-border)_25%,var(--terminal-border)_50%,transparent_50%,transparent_75%,var(--terminal-border)_75%,var(--terminal-border)_100%)] bg-[length:20px_20px]" />
         </div>

         <div className="max-w-5xl mx-auto px-6 text-center relative z-10">
             <h2 className="text-3xl font-mono font-bold text-[var(--terminal-text)] mb-8">
                SYSTEM_METRICS_OBSERVATORY
             </h2>

             <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
                {[
                    { label: 'Documents', val: '1.2M+' },
                    { label: 'Entities', val: '54M+' },
                    { label: 'Avg Latency', val: '12ms' },
                    { label: 'Uptime', val: '99.99%' },
                ].map((stat, i) => (
                    <div key={i} className="p-6 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                        <div className="text-2xl md:text-3xl font-bold font-mono text-[var(--phosphor-green)] mb-1">{stat.val}</div>
                        <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--terminal-text-muted)] opacity-70">{stat.label}</div>
                    </div>
                ))}
             </div>

             <Link href="/dashboard">
                <Button size="lg" className="h-14 px-10 font-mono text-sm font-bold bg-[var(--terminal-text)] text-[var(--terminal-bg)] hover:bg-[var(--terminal-text)]/90 hover:scale-105 transition-all">
                   INITIALIZE_DASHBOARD <LayoutDashboard className="w-4 h-4 ml-2" />
                </Button>
             </Link>
         </div>
      </section>

      {/* Footer */}
      <footer className="bg-[var(--terminal-bg)] pt-20 pb-10 border-t border-[var(--terminal-border)]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-16">
            <div className="col-span-2 md:col-span-1">
               <div className="flex items-center gap-2 mb-4">
                  <Terminal className="w-5 h-5 text-[var(--phosphor-green)]" />
                  <span className="font-mono font-bold text-[var(--terminal-text)]">RAG_OS</span>
               </div>
               <p className="font-mono text-xs text-[var(--terminal-text-muted)] leading-relaxed">
                  Next-generation knowledge retrieval system for enterprise intelligence.
               </p>
            </div>

            {[
                { head: 'Product', links: ['Features', 'Integrations', 'Security', 'Changelog'] },
                { head: 'Resources', links: ['Documentation', 'API Reference', 'Status', 'Community'] },
                { head: 'Company', links: ['About', 'Blog', 'Careers', 'Contact'] },
            ].map((col, i) => (
                <div key={i}>
                    <h4 className="font-mono text-xs font-bold text-[var(--terminal-text)] mb-4 uppercase tracking-wider">{col.head}</h4>
                    <ul className="space-y-2">
                        {col.links.map((l) => (
                            <li key={l}>
                                <Link href="#" className="font-mono text-xs text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] transition-colors">
                                    {l}
                                </Link>
                            </li>
                        ))}
                    </ul>
                </div>
            ))}
          </div>

          <div className="pt-8 border-t border-[var(--terminal-border)] flex flex-col md:flex-row justify-between items-center gap-4">
             <div className="font-mono text-[10px] text-[var(--terminal-text-muted)]">
                © 2024 RAG_OS SYSTEMS INC. ALL RIGHTS RESERVED.
             </div>
             <div className="flex items-center gap-6">
                 {[Globe, Activity, Command].map((Icon, i) => (
                     <Icon key={i} className="w-4 h-4 text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)] cursor-pointer transition-colors" />
                 ))}
             </div>
          </div>
        </div>
      </footer>
    </div>
  );
}