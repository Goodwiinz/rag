'use client';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import {
  ArrowRight,
  Bot,
  ChevronRight,
  Database,
  FileText,
  LogIn,
  LogOut,
  Menu,
  Network,
  Search,
  Sparkles,
  Terminal,
  Zap,
  Cpu,
  Eye,
  Radio,
  Activity,
  Layers,
  Globe,
  Shield,
  BarChart3,
} from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';
const CYAN = '#00d4ff';

// Constellation star positions (memoized for performance)
const generateStars = (count: number) => {
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 2 + 1,
    delay: Math.random() * 5,
    duration: Math.random() * 3 + 2,
    color: Math.random() > 0.8 ? PHOSPHOR_GREEN : Math.random() > 0.9 ? AMBER : 'white',
  }));
};

// Radar blip positions
const radarBlips = [
  { angle: 45, distance: 30, label: 'API' },
  { angle: 120, distance: 50, label: 'DB' },
  { angle: 200, distance: 40, label: 'Vec' },
  { angle: 310, distance: 55, label: 'Neo' },
];

export default function HomePage() {
  const { isAuthenticated, isLoading: authLoading, logout } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [terminalText, setTerminalText] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const stars = useMemo(() => generateStars(60), []);

  // Hydration-safe mounting
  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'MULTIMODAL ENTERPRISE RAG SYSTEM v2.0.1';
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

  const features = [
    {
      icon: Search,
      title: 'Semantic Search',
      description: 'AI-powered vector search with contextual understanding across your knowledge base',
      href: '/search',
      status: 'ONLINE',
      metrics: { queries: '12.4k', latency: '45ms' },
    },
    {
      icon: Bot,
      title: 'Terminal Chat',
      description: 'Local LLM inference with WebLLM - runs entirely in your browser',
      href: '/chat',
      status: 'ACTIVE',
      metrics: { sessions: '3.2k', models: '4' },
    },
    {
      icon: FileText,
      title: 'Document Pipeline',
      description: 'Multimodal ingestion with OCR, transcription, and entity extraction',
      href: '/documents/upload',
      status: 'READY',
      metrics: { processed: '8.7k', formats: '12' },
    },
    {
      icon: Database,
      title: 'ArXiv Research',
      description: 'Direct research paper ingestion and semantic indexing from arXiv',
      href: '/arxiv',
      status: 'SYNC',
      metrics: { papers: '2.1k', domains: '15' },
    },
  ];

  const systemStatus = [
    { label: 'API Gateway', status: 'online', latency: '12ms', icon: Zap, load: 23 },
    { label: 'PostgreSQL', status: 'online', latency: '8ms', icon: Database, load: 45 },
    { label: 'Vector Store', status: 'online', latency: '15ms', icon: Sparkles, load: 67 },
    { label: 'Neo4j Graph', status: 'online', latency: '22ms', icon: Network, load: 34 },
  ];

  const capabilities = [
    { label: 'Document Formats', value: 'PDF, DOCX, TXT', icon: FileText, detail: '12 supported' },
    { label: 'OCR Extraction', value: 'Images & Scans', icon: Eye, detail: 'Tesseract + Vision' },
    { label: 'Audio/Video', value: 'Transcription', icon: Radio, detail: 'Whisper AI' },
    { label: 'Vector Search', value: 'Semantic AI', icon: Cpu, detail: 'Qdrant + BGE' },
  ];

  return (
    <div className="min-h-screen bg-[#0a0a0f] relative overflow-hidden">
      {/* Constellation Starfield Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        {mounted && stars.map((star) => (
          <motion.div
            key={star.id}
            className="absolute rounded-full"
            style={{
              left: `${star.x}%`,
              top: `${star.y}%`,
              width: star.size,
              height: star.size,
              backgroundColor: star.color,
              opacity: 0.3,
            }}
            animate={{
              opacity: [0.2, 0.8, 0.2],
              scale: [1, 1.2, 1],
            }}
            transition={{
              duration: star.duration,
              delay: star.delay,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        ))}
      </div>

      {/* CRT Scanlines Overlay */}
      <div className="pointer-events-none fixed inset-0 z-50 opacity-[0.02]">
        <div className="h-full w-full" style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 159, 0.03) 2px, rgba(0, 255, 159, 0.03) 4px)',
        }} />
      </div>

      {/* Hex Grid Background */}
      <div className="absolute inset-0 hex-grid-bg opacity-30" />

      {/* Ambient Glow Orbs */}
      <div className="absolute top-0 left-1/4 w-[800px] h-[800px] rounded-full blur-[200px] opacity-15 ambient-orb"
        style={{ background: `radial-gradient(circle, ${PHOSPHOR_GREEN}40, transparent 70%)` }} />
      <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] rounded-full blur-[150px] opacity-10 ambient-orb-delayed"
        style={{ background: `radial-gradient(circle, ${CYAN}30, transparent 70%)` }} />
      <div className="absolute top-1/2 right-0 w-[500px] h-[500px] rounded-full blur-[120px] opacity-10"
        style={{ background: `radial-gradient(circle, ${AMBER}25, transparent 70%)` }} />

      {/* Navigation Header */}
      <nav className="relative z-40 border-b border-white/5 backdrop-blur-xl bg-[#0a0a0f]/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-3 group">
              <div className="relative">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg border border-[#00ff9f]/30 bg-[#00ff9f]/5 group-hover:bg-[#00ff9f]/10 group-hover:border-[#00ff9f]/50 transition-all duration-300">
                  <Terminal className="w-5 h-5 text-[#00ff9f]" />
                </div>
                <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-[#00ff9f] animate-pulse" />
              </div>
              <div className="flex flex-col">
                <span className="font-display font-semibold text-white/90 text-base tracking-tight">RAG System</span>
                <span className="text-[10px] font-mono text-[#00ff9f]/60 tracking-widest uppercase">Terminal Observatory</span>
              </div>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-1">
              {[
                { href: '/search', label: 'Search' },
                { href: '/chat', label: 'Chat' },
                { href: '/documents/upload', label: 'Documents' },
                { href: '/dashboard', label: 'Dashboard' },
              ].map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="px-4 py-2 font-mono text-sm text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-all duration-200"
                >
                  {item.label}
                </Link>
              ))}
            </div>

            {/* Auth Buttons */}
            <div className="hidden md:flex items-center gap-3">
              {isAuthenticated ? (
                <>
                  <Link href="/dashboard">
                    <Button
                      size="sm"
                      className="font-mono text-xs bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 hover:bg-[#00ff9f]/20 hover:border-[#00ff9f]/50 transition-all"
                    >
                      <BarChart3 className="w-3.5 h-3.5 mr-1.5" />
                      Dashboard
                    </Button>
                  </Link>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => logout()}
                    className="font-mono text-xs text-white/50 hover:text-white hover:bg-white/5"
                  >
                    <LogOut className="w-3.5 h-3.5 mr-1.5" />
                    Sign Out
                  </Button>
                </>
              ) : (
                <>
                  <Link href="/login">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="font-mono text-xs text-white/50 hover:text-white hover:bg-white/5"
                    >
                      <LogIn className="w-3.5 h-3.5 mr-1.5" />
                      Sign In
                    </Button>
                  </Link>
                  <Link href="/register">
                    <Button
                      size="sm"
                      className="font-mono text-xs bg-gradient-to-r from-[#00ff9f]/20 to-[#00d4ff]/20 text-[#00ff9f] border border-[#00ff9f]/40 hover:border-[#00ff9f]/60 hover:shadow-[0_0_20px_rgba(0,255,159,0.2)] transition-all duration-300"
                    >
                      Get Started
                      <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                    </Button>
                  </Link>
                </>
              )}
            </div>

            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-white/60 hover:text-white rounded-lg hover:bg-white/5"
            >
              <Menu className="w-5 h-5" />
            </button>
          </div>

          {/* Mobile Menu */}
          <AnimatePresence>
            {mobileMenuOpen && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="md:hidden border-t border-white/10 py-4"
              >
                <div className="flex flex-col gap-2">
                  {[
                    { href: '/search', label: 'Search' },
                    { href: '/chat', label: 'Chat' },
                    { href: '/documents/upload', label: 'Documents' },
                    { href: '/dashboard', label: 'Dashboard' },
                  ].map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="font-mono text-sm text-white/60 hover:text-white py-2 px-3 rounded-lg hover:bg-white/5"
                    >
                      {item.label}
                    </Link>
                  ))}
                  <div className="border-t border-white/10 pt-3 mt-2 flex gap-2">
                    {isAuthenticated ? (
                      <>
                        <Link href="/dashboard" className="flex-1">
                          <Button size="sm" className="w-full font-mono text-xs bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30">
                            Dashboard
                          </Button>
                        </Link>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => logout()}
                          className="font-mono text-xs border-white/20 text-white/60"
                        >
                          Sign Out
                        </Button>
                      </>
                    ) : (
                      <>
                        <Link href="/login" className="flex-1">
                          <Button size="sm" variant="outline" className="w-full font-mono text-xs border-white/20 text-white/60">
                            Sign In
                          </Button>
                        </Link>
                        <Link href="/register" className="flex-1">
                          <Button size="sm" className="w-full font-mono text-xs bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30">
                            Get Started
                          </Button>
                        </Link>
                      </>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="relative border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 sm:pt-20 pb-20 sm:pb-24">
          {/* Terminal Header Badge */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="flex items-center justify-center mb-8"
          >
            <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full border border-[#00ff9f]/20 bg-[#00ff9f]/5 backdrop-blur-sm">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00ff9f] opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00ff9f]"></span>
                </span>
                <Terminal className="w-4 h-4 text-[#00ff9f]/80" />
              </div>
              <span className="font-mono text-sm text-[#00ff9f]/90 tracking-wider">
                {terminalText}
                <span className="cursor-glow text-[#00ff9f]">_</span>
              </span>
            </div>
          </motion.div>

          {/* Main Heading */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }}
            className="text-center mb-12"
          >
            <h1 className="font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6 leading-[1.1]">
              <span className="text-white/95">Transform Data Into</span>
              <br />
              <span className="text-gradient-premium">
                Actionable Intelligence
              </span>
            </h1>
            <p className="text-lg sm:text-xl text-white/40 max-w-3xl mx-auto font-light leading-relaxed">
              Process documents, extract entities, build knowledge graphs, and query with semantic understanding.
              <span className="text-white/60"> All running locally in your browser.</span>
            </p>
          </motion.div>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="flex flex-wrap justify-center gap-4 mb-16"
          >
            <Link href="/documents/upload">
              <Button
                size="lg"
                className="h-12 px-6 font-mono text-sm bg-[#00ff9f] text-[#0a0a0f] hover:bg-[#00ff9f]/90 transition-colors"
              >
                START PROCESSING
              </Button>
            </Link>
            <Link href="/chat">
              <Button
                size="lg"
                className="h-12 px-6 font-mono text-sm bg-transparent border border-[#00ff9f] text-[#00ff9f] hover:bg-[#00ff9f]/10 transition-colors"
              >
                OPEN TERMINAL
              </Button>
            </Link>
          </motion.div>

          {/* Capability Stats */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 max-w-4xl mx-auto"
          >
            {capabilities.map((cap, i) => (
              <motion.div
                key={cap.label}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.7 + i * 0.1 }}
                className="group relative p-4 sm:p-5 rounded-xl border border-white/10 bg-white/[0.02] hover:border-[#00ff9f]/30 hover:bg-[#00ff9f]/[0.02] transition-all duration-300"
              >
                <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[#00ff9f]/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <cap.icon className="w-5 h-5 text-[#00ff9f]/60 mb-3 group-hover:text-[#00ff9f] transition-colors" />
                <div className="text-sm font-medium text-white/80 mb-1">{cap.value}</div>
                <div className="text-xs font-mono text-white/30">{cap.label}</div>
                <div className="text-[10px] font-mono text-[#00ff9f]/50 mt-2">{cap.detail}</div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <h2 className="font-display text-2xl sm:text-3xl font-semibold text-white/90 mb-3">
            Mission Control
          </h2>
          <p className="text-white/40 font-mono text-sm">
            Access core system modules and capabilities
          </p>
        </motion.div>

        {/* Feature Grid - Premium Cards */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-16"
        >
          {features.map((feature, index) => (
            <Link key={feature.title} href={feature.href}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ y: -6 }}
                className={cn(
                  "group relative h-full rounded-xl overflow-hidden cursor-pointer card-premium",
                  "border border-white/10 bg-[#0d0d12]/80 backdrop-blur-sm"
                )}
              >
                {/* Scan beam effect on hover */}
                <div className="absolute inset-0 overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-500">
                  <div className="scan-beam" />
                </div>

                {/* Terminal Window Chrome */}
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 bg-white/[0.02]">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded-full bg-red-500/50" />
                    <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
                    <div className="w-2 h-2 rounded-full bg-green-500/50" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f] animate-pulse" />
                    <span className="text-[10px] font-mono text-[#00ff9f]/70 tracking-wider">
                      [{feature.status}]
                    </span>
                  </div>
                </div>

                <div className="p-5">
                  {/* Icon and Title */}
                  <div className="flex items-start gap-4 mb-4">
                    <div className="relative">
                      <div className="p-3 rounded-lg bg-[#00ff9f]/5 border border-[#00ff9f]/20 group-hover:border-[#00ff9f]/40 group-hover:bg-[#00ff9f]/10 transition-all duration-300">
                        <feature.icon className="w-5 h-5 text-[#00ff9f]" />
                      </div>
                      <div className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full border border-[#00ff9f]/30 bg-[#0d0d12] flex items-center justify-center">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#00ff9f]/60" />
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-display text-base font-medium text-white/90 group-hover:text-[#00ff9f] transition-colors mb-1">
                        {feature.title}
                      </h3>
                      <p className="text-xs text-white/40 leading-relaxed line-clamp-2">
                        {feature.description}
                      </p>
                    </div>
                  </div>

                  {/* Metrics Bar */}
                  <div className="flex items-center justify-between pt-4 border-t border-white/5">
                    <div className="flex items-center gap-4">
                      {Object.entries(feature.metrics).map(([key, value]) => (
                        <div key={key} className="text-center">
                          <div className="text-xs font-mono text-white/70">{value}</div>
                          <div className="text-[9px] font-mono text-white/30 uppercase">{key}</div>
                        </div>
                      ))}
                    </div>
                    <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-[#00ff9f] group-hover:translate-x-1 transition-all" />
                  </div>
                </div>
              </motion.div>
            </Link>
          ))}
        </motion.div>

        {/* System Status - Radar Style */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="relative"
        >
          <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#0d0d12]/80 backdrop-blur-sm">
            {/* Terminal Chrome */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-white/[0.02]">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-500/50" />
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/50" />
                  <div className="w-2.5 h-2.5 rounded-full bg-green-500/50" />
                </div>
                <div className="h-4 w-px bg-white/10" />
                <Shield className="w-4 h-4 text-[#00ff9f]/60" />
                <span className="text-xs font-mono text-white/40 tracking-wider uppercase">
                  System Status Monitor
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#00ff9f] animate-pulse" />
                <span className="text-[10px] font-mono text-[#00ff9f]">ALL SYSTEMS OPERATIONAL</span>
              </div>
            </div>

            <div className="p-6">
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                {/* Radar Display */}
                <div className="lg:col-span-2 flex items-center justify-center">
                  <div className="relative w-48 h-48 sm:w-56 sm:h-56">
                    {/* Radar circles */}
                    <div className="absolute inset-0 rounded-full border border-[#00ff9f]/10" />
                    <div className="absolute inset-4 rounded-full border border-[#00ff9f]/10" />
                    <div className="absolute inset-8 rounded-full border border-[#00ff9f]/10" />
                    <div className="absolute inset-12 rounded-full border border-[#00ff9f]/10" />

                    {/* Crosshairs */}
                    <div className="absolute top-1/2 left-0 right-0 h-px bg-[#00ff9f]/10" />
                    <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#00ff9f]/10" />

                    {/* Radar sweep */}
                    <div className="absolute inset-0 radar-sweep">
                      <div
                        className="absolute top-1/2 left-1/2 w-1/2 h-0.5 origin-left"
                        style={{
                          background: `linear-gradient(90deg, ${PHOSPHOR_GREEN}80 0%, transparent 100%)`,
                        }}
                      />
                    </div>

                    {/* Blips */}
                    {radarBlips.map((blip, i) => {
                      const radians = (blip.angle * Math.PI) / 180;
                      const x = 50 + Math.cos(radians) * blip.distance;
                      const y = 50 + Math.sin(radians) * blip.distance;
                      return (
                        <motion.div
                          key={i}
                          className="absolute w-3 h-3"
                          style={{ left: `${x}%`, top: `${y}%`, transform: 'translate(-50%, -50%)' }}
                          animate={{
                            opacity: [0.4, 1, 0.4],
                            scale: [1, 1.2, 1],
                          }}
                          transition={{
                            duration: 2,
                            delay: i * 0.5,
                            repeat: Infinity,
                          }}
                        >
                          <div className="w-full h-full rounded-full bg-[#00ff9f] shadow-[0_0_10px_rgba(0,255,159,0.5)]" />
                          <span className="absolute top-4 left-1/2 -translate-x-1/2 text-[8px] font-mono text-[#00ff9f]/60">
                            {blip.label}
                          </span>
                        </motion.div>
                      );
                    })}

                    {/* Center dot */}
                    <div className="absolute top-1/2 left-1/2 w-3 h-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#00ff9f]/20 border border-[#00ff9f]/40 glow-ring" />
                  </div>
                </div>

                {/* Status Grid */}
                <div className="lg:col-span-3 grid grid-cols-2 gap-3">
                  {systemStatus.map((service, i) => (
                    <motion.div
                      key={service.label}
                      initial={{ opacity: 0, x: 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.4, delay: i * 0.1 }}
                      className="group relative p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:border-[#00ff9f]/20 transition-all"
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <div className="p-2 rounded-lg bg-[#00ff9f]/5 border border-[#00ff9f]/10 group-hover:border-[#00ff9f]/30 transition-colors">
                          <service.icon className="w-4 h-4 text-[#00ff9f]" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-white/80">{service.label}</p>
                          <div className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f]" />
                            <span className="text-[10px] font-mono text-[#00ff9f]">Online</span>
                          </div>
                        </div>
                      </div>

                      {/* Load bar */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[10px] font-mono">
                          <span className="text-white/30">LOAD</span>
                          <span className="text-white/50">{service.load}%</span>
                        </div>
                        <div className="h-1 rounded-full bg-white/5 overflow-hidden">
                          <motion.div
                            className="h-full rounded-full bg-gradient-to-r from-[#00ff9f]/60 to-[#00ff9f]"
                            initial={{ width: 0 }}
                            whileInView={{ width: `${service.load}%` }}
                            viewport={{ once: true }}
                            transition={{ duration: 1, delay: 0.5 + i * 0.1 }}
                          />
                        </div>
                        <div className="flex items-center justify-between text-[10px] font-mono text-white/30">
                          <span>Latency</span>
                          <span className="text-[#00ff9f]/70">{service.latency}</span>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Footer CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mt-16 text-center"
        >
          <p className="text-white/40 font-mono text-sm mb-4">
            Ready to get started?
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/documents/upload">
              <Button
                className="font-mono text-xs bg-transparent border border-[#00ff9f]/50 text-[#00ff9f] hover:bg-[#00ff9f]/10 transition-colors"
              >
                <FileText className="w-3.5 h-3.5 mr-1.5" />
                Upload Documents
              </Button>
            </Link>
            <Link href="/search">
              <Button
                className="font-mono text-xs bg-transparent border border-[#00ff9f]/50 text-[#00ff9f] hover:bg-[#00ff9f]/10 transition-colors"
              >
                <Search className="w-3.5 h-3.5 mr-1.5" />
                Search Knowledge Base
              </Button>
            </Link>
            <Link href="/chat">
              <Button
                className="font-mono text-xs bg-transparent border border-[#00ff9f]/50 text-[#00ff9f] hover:bg-[#00ff9f]/10 transition-colors"
              >
                <Bot className="w-3.5 h-3.5 mr-1.5" />
                Open Chat Terminal
              </Button>
            </Link>
          </div>
        </motion.div>
      </div>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-white/30 text-xs font-mono">
              <Terminal className="w-3.5 h-3.5" />
              <span>Terminal Observatory v2.0.1</span>
            </div>
            <div className="flex items-center gap-4 text-white/30 text-xs font-mono">
              <Link href="/analytics" className="hover:text-white/60 transition-colors">Analytics</Link>
              <Link href="/dashboard" className="hover:text-white/60 transition-colors">Dashboard</Link>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="hover:text-white/60 transition-colors flex items-center gap-1">
                <Globe className="w-3 h-3" />
                GitHub
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
