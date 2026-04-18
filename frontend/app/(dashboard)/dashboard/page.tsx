'use client';

import { useAuth } from '@/hooks/useAuth';
import { useDocuments } from '@/hooks/useDocuments';
import { getAnalytics } from '@/lib/analytics';
import { cn } from '@/lib/utils';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Bot,
  Brain,
  ChevronRight,
  Clock,
  Database,
  FileText,
  FileVideo,
  Gauge,
  Image as ImageIcon,
  MessageSquare,
  Music,
  Network,
  Search,
  Sparkles,
  Terminal,
  TrendingUp,
  Upload,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

// Import enhanced components
import { KeyboardShortcuts } from '@/components/dashboard/KeyboardShortcuts';
import { QuickSearch } from '@/components/dashboard/QuickSearch';
import { COLORS } from '@/theme/constants';

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const { documents, loading: docsLoading } = useDocuments({
    initialPageSize: 100,
    autoFetch: isAuthenticated && !authLoading,
  });

  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [showQuickSearch, setShowQuickSearch] = useState(false);
  const [currentTime, setCurrentTime] = useState('');

  // Hydration-safe mounting
  useEffect(() => {
    setMounted(true);
  }, []);

  // Update time
  useEffect(() => {
    if (!mounted) return;
    const updateTime = () => {
      setCurrentTime(
        new Date().toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [mounted]);

  // Analytics tracking
  useEffect(() => {
    try {
      const analytics = getAnalytics();
      analytics.trackPageView('/dashboard', 'Dashboard');
      if (isAuthenticated && user) {
        analytics.trackFeatureUsage('dashboard', 'viewed', {
          documentCount: documents?.length || 0,
          authProvider: 'email',
        });
      }
    } catch {
      // Analytics not initialized
    }
  }, [isAuthenticated, user, documents]);

  // Loading state
  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowQuickSearch(true);
      }
      if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
        e.preventDefault();
        setShowKeyboardShortcuts(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Stats
  const stats = {
    documents: documents?.length || 0,
    searches: 42,
    chats: 15,
    processing: 2,
  };

  // Quick actions
  const quickActions = [
    {
      icon: Upload,
      label: 'Upload',
      href: '/documents/upload',
      color: COLORS.phosphorGreen,
    },
    {
      icon: Search,
      label: 'Search',
      href: '/search',
      color: COLORS.phosphorGreen,
    },
    { icon: Bot, label: 'Chat', href: '/chat', color: COLORS.amber },
    {
      icon: Database,
      label: 'ArXiv',
      href: '/arxiv',
      color: COLORS.phosphorGreen,
    },
  ];

  // System services
  const services = [
    { name: 'API Gateway', status: 'online', latency: '12ms', load: 23 },
    { name: 'PostgreSQL', status: 'online', latency: '8ms', load: 45 },
    { name: 'Vector Store', status: 'online', latency: '15ms', load: 31 },
    { name: 'Neo4j Graph', status: 'online', latency: '22ms', load: 18 },
    { name: 'Redis Cache', status: 'online', latency: '3ms', load: 12 },
    { name: 'AI Engine', status: 'online', latency: '156ms', load: 67 },
  ];

  // Recent activity
  const recentActivity = [
    {
      type: 'process',
      text: 'Document parsed: attention_is_all_you_need.pdf',
      time: '2 mins ago',
    },
    {
      type: 'upload',
      text: 'System scaling: +2 node instances',
      time: '14 mins ago',
    },
    {
      type: 'search',
      text: 'Query resolved: 48ms latency',
      time: '1 hour ago',
    },
    {
      type: 'process',
      text: 'Vector embeddings generation completed',
      time: '2 hours ago',
    },
    { type: 'chat', text: 'Daily backup to cold storage', time: '5 hours ago' },
  ];

  // Document type breakdown
  const docTypes = [
    {
      type: 'PDF',
      count: Math.floor(stats.documents * 0.4),
      icon: FileText,
      color: COLORS.error,
    },
    {
      type: 'Images',
      count: Math.floor(stats.documents * 0.3),
      icon: ImageIcon,
      color: COLORS.info,
    },
    {
      type: 'Video',
      count: Math.floor(stats.documents * 0.2),
      icon: FileVideo,
      color: COLORS.chart4,
    },
    {
      type: 'Audio',
      count: Math.floor(stats.documents * 0.1),
      icon: Music,
      color: COLORS.amber,
    },
  ];

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-hidden flex flex-col">
      {/* Content */}
      <div className="relative p-6 space-y-6 flex-1 overflow-y-auto terminal-scrollbar">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-xl"
        >
          <div className="p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 flex items-center justify-center">
                  <Terminal className="w-6 h-6 text-[var(--phosphor-green)]" />
                </div>
                <div>
                  <h1 className="text-xl font-mono font-bold text-[var(--terminal-text)]">
                    System Overview
                    {user?.email ? `: ${user.email.split('@')[0]}` : ''}
                  </h1>
                  <p className="text-xs font-mono text-[var(--terminal-text-dim)] mt-0.5 uppercase tracking-widest">
                    Knowledge Base Metrics & Status
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50">
                  <span className="text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest">
                    UTC
                  </span>
                  <span className="text-xs font-mono text-[var(--phosphor-green)]">
                    {mounted ? currentTime : '--:--:--'}
                  </span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--phosphor-green)]/30 bg-[var(--phosphor-green)]/5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--phosphor-green)] opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--phosphor-green)]" />
                  </span>
                  <span className="text-[10px] font-mono font-bold text-[var(--phosphor-green)] uppercase tracking-widest">
                    Live
                  </span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {quickActions.map((action) => (
            <Link
              key={action.label}
              href={action.href}
              className="rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--phosphor-green)]"
            >
              <motion.div
                whileHover={{ y: -4 }}
                className={cn(
                  'group p-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg',
                  'hover:border-[var(--phosphor-green)]/30 hover:shadow-[0_0_15px_rgba(212,160,57,0.06)] transition-all duration-300 cursor-pointer'
                )}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="p-2 rounded-lg border border-transparent group-hover:border-current transition-colors"
                    style={{
                      backgroundColor: `${action.color}10`,
                      color: action.color,
                    }}
                  >
                    <action.icon className="w-4 h-4" />
                  </div>
                  <span className="font-mono text-xs font-bold text-[var(--terminal-text-dim)] group-hover:text-[var(--terminal-text)] transition-colors uppercase tracking-wider">
                    {action.label}
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-[var(--terminal-text-muted)]/40 ml-auto group-hover:text-[var(--phosphor-green)] group-hover:translate-x-0.5 transition-all" />
                </div>
              </motion.div>
            </Link>
          ))}
        </motion.div>

        {/* Stats Grid */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {[
            {
              label: 'Active Documents',
              value: stats.documents || '12,543',
              icon: FileText,
              change: '+12.5%',
              color: COLORS.phosphorGreen,
            },
            {
              label: 'Daily Queries',
              value: stats.searches || '8,921',
              icon: Search,
              change: '+5.2%',
              color: COLORS.phosphorGreen,
            },
            {
              label: 'Entity Extraction',
              value: '94.2%',
              icon: MessageSquare,
              change: '+1.8%',
              color: COLORS.amber,
            },
            {
              label: 'System Latency',
              value: '42ms',
              icon: Zap,
              change: '0',
              color: COLORS.phosphorGreen,
            },
          ].map((stat, idx) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 + idx * 0.05 }}
              className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-5 shadow-lg relative group overflow-hidden"
            >
              <div
                className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b opacity-40 group-hover:opacity-100 transition-opacity"
                style={{
                  backgroundImage: `linear-gradient(to bottom, ${stat.color}, transparent)`,
                }}
              />

              <div className="flex items-start justify-between mb-4">
                <div className="p-2 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                  <stat.icon
                    className="w-4 h-4"
                    style={{ color: stat.color }}
                  />
                </div>
                <span
                  className={cn(
                    'text-[10px] font-mono px-1.5 py-0.5 rounded-full border',
                    stat.change === '0'
                      ? 'hidden'
                      : stat.change.startsWith('+')
                        ? 'text-[var(--phosphor-green)] border-[var(--phosphor-green)]/20 bg-[var(--phosphor-green)]/5'
                        : 'text-[var(--terminal-text-dim)] border-[var(--terminal-border)] bg-white/5'
                  )}
                >
                  {stat.change}
                </span>
              </div>
              <div className="text-2xl font-mono font-bold text-[var(--terminal-text)]">
                {stat.value}
              </div>
              <div className="text-[11px] font-mono text-[var(--terminal-text-dim)] mt-1 uppercase tracking-widest">
                {stat.label}
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* System Status */}
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="lg:col-span-2 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30">
              <Activity className="w-4 h-4 text-[var(--phosphor-green)]" />
              <span className="text-xs font-mono font-bold text-[var(--terminal-text)] uppercase tracking-widest">
                Active Neural Nodes
              </span>
            </div>

            <div className="p-5">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {services.map((service) => (
                  <div
                    key={service.name}
                    className="p-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/20 hover:border-[var(--phosphor-green)]/20 transition-all group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[11px] font-mono text-[var(--terminal-text-muted)] group-hover:text-[var(--terminal-text)] transition-colors">
                        {service.name}
                      </span>
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] shadow-[0_0_8px_var(--phosphor-green)]" />
                    </div>
                    <div className="flex items-baseline gap-2 mb-3">
                      <span className="text-lg font-mono text-[var(--terminal-text)]">
                        {service.latency}
                      </span>
                      <span className="text-[9px] font-mono text-[var(--phosphor-green)] font-bold tracking-tighter">
                        DELAY
                      </span>
                    </div>
                    {/* Load bar */}
                    <div className="h-1 bg-[var(--terminal-border)] rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${service.load}%` }}
                        transition={{ duration: 1, delay: 0.5 }}
                        className={cn(
                          'h-full rounded-full',
                          service.load < 50 && 'bg-[var(--phosphor-green)]/50',
                          service.load >= 50 &&
                            service.load < 75 &&
                            'bg-[var(--amber-gold)]/60',
                          service.load >= 75 && 'bg-red-500/60'
                        )}
                      />
                    </div>
                    <div className="text-[9px] font-mono text-[var(--terminal-text-dim)] mt-2 uppercase tracking-tight">
                      {service.load}% resource load
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Activity Feed */}
          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 }}
            className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30">
              <Clock className="w-4 h-4 text-[var(--terminal-text-dim)]" />
              <span className="text-xs font-mono font-bold text-[var(--terminal-text)] uppercase tracking-widest">
                Neural Stream
              </span>
            </div>

            <div className="p-4">
              <div className="space-y-3">
                {recentActivity.map((item, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: 5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + idx * 0.05 }}
                    className="flex items-start gap-3 p-3 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/10 hover:bg-[var(--terminal-bg)]/30 transition-colors group"
                  >
                    <div
                      className={cn(
                        'w-1 h-4 rounded-full mt-0.5 shrink-0 transition-all group-hover:h-6',
                        item.type === 'upload' && 'bg-[var(--phosphor-green)]',
                        item.type === 'search' && 'bg-[var(--cyan)]',
                        item.type === 'chat' && 'bg-[var(--amber-gold)]',
                        item.type === 'process' && 'bg-purple-500',
                        idx === 0 && 'animate-pulse-live'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-mono text-[var(--terminal-text)] truncate">
                        {item.text}
                      </p>
                      <p className="text-[9px] font-mono text-[var(--terminal-text-dim)] mt-0.5">
                        {item.time}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Document Types & AI Insights */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-6">
          {/* Document Types */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30">
              <BarChart3 className="w-4 h-4 text-[var(--terminal-text-dim)]" />
              <span className="text-xs font-mono font-bold text-[var(--terminal-text)] uppercase tracking-widest">
                Corpus Distribution
              </span>
            </div>

            <div className="p-6">
              <div className="space-y-4">
                {docTypes.map((doc, idx) => (
                  <div key={doc.type} className="flex items-center gap-4">
                    <div className="p-2 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)]">
                      <doc.icon
                        className="w-4 h-4"
                        style={{ color: doc.color }}
                      />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-mono text-[var(--terminal-text)] font-medium uppercase tracking-tighter">
                          {doc.type}
                        </span>
                        <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                          {doc.count} units
                        </span>
                      </div>
                      <div className="h-1.5 bg-[var(--terminal-border)] rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{
                            width: `${(doc.count / stats.documents) * 100 || 0}%`,
                          }}
                          transition={{ duration: 1, delay: 0.6 + idx * 0.1 }}
                          className="h-full rounded-full"
                          style={{ backgroundColor: doc.color }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* AI Insights */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30">
              <Brain className="w-4 h-4 text-[var(--amber-gold)]" />
              <span className="text-xs font-mono font-bold text-[var(--terminal-text)] uppercase tracking-widest">
                Synthetic Insights
              </span>
            </div>

            <div className="p-6 space-y-4">
              {[
                {
                  text: 'Knowledge graph expanded with 23 new entities',
                  icon: Network,
                  color: COLORS.phosphorGreen,
                },
                {
                  text: 'Semantic search accuracy improved to 94.2%',
                  icon: TrendingUp,
                  color: COLORS.phosphorGreen,
                },
                {
                  text: 'Processing queue optimized, 45% faster',
                  icon: Gauge,
                  color: COLORS.amber,
                },
              ].map((insight, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -5 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.7 + idx * 0.1 }}
                  className="flex items-start gap-4 p-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/20"
                >
                  <div className="p-2 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] shrink-0">
                    <insight.icon
                      className="w-4 h-4"
                      style={{ color: insight.color }}
                    />
                  </div>
                  <p className="text-xs font-mono text-[var(--terminal-text-dim)] leading-relaxed">
                    {insight.text}
                  </p>
                </motion.div>
              ))}

              <Link href="/chat">
                <div className="flex items-center justify-between p-4 rounded-xl border border-[var(--amber-gold)]/20 bg-[var(--amber-gold)]/5 hover:border-[var(--amber-gold)]/40 transition-all cursor-pointer group">
                  <div className="flex items-center gap-3">
                    <Sparkles className="w-4 h-4 text-[var(--amber-gold)]" />
                    <span className="text-xs font-mono font-bold text-[var(--amber-gold)] uppercase tracking-widest">
                      Execute Neural Session
                    </span>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-[var(--amber-gold)]/60 group-hover:text-[var(--amber-gold)] group-hover:translate-x-1 group-hover:-translate-y-1 transition-all" />
                </div>
              </Link>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Loading Overlay */}
      <AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-[var(--terminal-bg)] z-50 flex items-center justify-center"
          >
            <div className="text-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                className="w-10 h-10 border-2 border-[var(--phosphor-green)]/10 border-t-[var(--phosphor-green)] rounded-full mx-auto"
              />
              <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] mt-4 uppercase tracking-widest">
                Initializing Neural Interface...
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modals */}
      <KeyboardShortcuts
        isOpen={showKeyboardShortcuts}
        onClose={() => setShowKeyboardShortcuts(false)}
      />
      <QuickSearch
        isOpen={showQuickSearch}
        onClose={() => setShowQuickSearch(false)}
      />
    </div>
  );
}
