"use client";

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
    Zap
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
      setCurrentTime(new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      }));
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
    { icon: Upload, label: 'Upload', href: '/documents/upload', color: COLORS.phosphorGreen },
    { icon: Search, label: 'Search', href: '/search', color: COLORS.phosphorGreen },
    { icon: Bot, label: 'Chat', href: '/llm-chat', color: COLORS.amber },
    { icon: Database, label: 'ArXiv', href: '/arxiv', color: COLORS.phosphorGreen },
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
    { type: 'upload', text: 'research_paper.pdf uploaded', time: '2m ago' },
    { type: 'search', text: 'Query: "transformer architecture"', time: '5m ago' },
    { type: 'chat', text: 'AI chat session completed', time: '12m ago' },
    { type: 'process', text: 'Document indexed successfully', time: '15m ago' },
    { type: 'upload', text: 'dataset_v2.csv uploaded', time: '23m ago' },
  ];

  // Document type breakdown
  const docTypes = [
    { type: 'PDF', count: Math.floor(stats.documents * 0.4), icon: FileText, color: COLORS.error },
    { type: 'Images', count: Math.floor(stats.documents * 0.3), icon: ImageIcon, color: COLORS.info },
    { type: 'Video', count: Math.floor(stats.documents * 0.2), icon: FileVideo, color: COLORS.chart4 },
    { type: 'Audio', count: Math.floor(stats.documents * 0.1), icon: Music, color: COLORS.amber },
  ];

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-hidden">
        {/* CRT Scanlines */}
        <div className="pointer-events-none fixed inset-0 z-50 opacity-[0.03]">
          <div className="h-full w-full" style={{
            backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 159, 0.03) 2px, rgba(0, 255, 159, 0.03) 4px)',
          }} />
        </div>

        {/* Background Grid */}
        <div className="absolute inset-0 opacity-[0.02]">
          <div className="h-full w-full" style={{
            backgroundImage: `
              linear-gradient(${COLORS.phosphorGreen}20 1px, transparent 1px),
              linear-gradient(90deg, ${COLORS.phosphorGreen}20 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px',
          }} />
        </div>

        {/* Ambient Glow */}
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full blur-[150px] opacity-10"
          style={{ background: `radial-gradient(circle, ${COLORS.phosphorGreen}, transparent 70%)` }} />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full blur-[120px] opacity-10"
          style={{ background: `radial-gradient(circle, ${COLORS.amber}, transparent 70%)` }} />

        {/* Content */}
        <div className="relative p-6 space-y-6">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
          >
            {/* Terminal Chrome */}
            <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[var(--terminal-border)] bg-white/[0.02]">
              <div className="w-2 h-2 rounded-full bg-red-500/60" />
              <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
              <div className="w-2 h-2 rounded-full bg-green-500/60" />
              <span className="ml-2 text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
                Command Center
              </span>
              <span className="ml-auto text-[10px] font-mono text-[var(--phosphor-green-dim)]">
                {mounted ? currentTime : '--:--:--'}
              </span>
            </div>

            <div className="p-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-mono font-bold text-[var(--terminal-text)] flex items-center gap-3">
                    <Terminal className="w-6 h-6 text-[var(--phosphor-green)]" />
                    Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}
                  </h1>
                  <p className="text-sm font-mono text-[var(--terminal-text-muted)] mt-1">
                    Knowledge base status overview
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-[var(--terminal-border)] bg-white/[0.02]">
                    <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-[var(--terminal-text-muted)] bg-white/5 rounded border border-[var(--terminal-border)]">
                      ⌘K
                    </kbd>
                    <span className="text-xs font-mono text-[var(--terminal-text-muted)]">Search</span>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 rounded border border-[var(--phosphor-green-dim)] bg-[var(--phosphor-green)]/5">
                    <span className="w-2 h-2 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
                    <span className="text-xs font-mono text-[var(--phosphor-green)]">All Systems Online</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-3"
          >
            {quickActions.map((action) => (
              <Link key={action.label} href={action.href}>
                <motion.div
                  whileHover={{ scale: 1.02, y: -2 }}
                  className={cn(
                    "group p-4 rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)]",
                    "hover:border-[var(--phosphor-green-dim)] hover:shadow-[0_0_20px_rgba(0,255,159,0.1)]",
                    "transition-all duration-300 cursor-pointer"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="p-2 rounded border transition-colors"
                      style={{
                        backgroundColor: `${action.color}10`,
                        borderColor: `${action.color}30`
                      }}
                    >
                      <action.icon className="w-5 h-5" style={{ color: action.color }} />
                    </div>
                    <span className="font-mono text-sm text-[var(--terminal-text-muted)] group-hover:text-white transition-colors">
                      {action.label}
                    </span>
                    <ChevronRight className="w-4 h-4 text-[var(--terminal-text-muted)]/20 ml-auto group-hover:text-[var(--phosphor-green)] group-hover:translate-x-1 transition-all" />
                  </div>
                </motion.div>
              </Link>
            ))}
          </motion.div>

          {/* Stats Grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-2 lg:grid-cols-4 gap-4"
          >
            {[
              { label: 'Total Documents', value: stats.documents, icon: FileText, change: '+12%', color: COLORS.phosphorGreen },
              { label: 'Search Queries', value: stats.searches, icon: Search, change: '+8%', color: COLORS.phosphorGreen },
              { label: 'AI Interactions', value: stats.chats, icon: MessageSquare, change: '+23%', color: COLORS.amber },
              { label: 'Processing Queue', value: stats.processing, icon: Zap, change: '0', color: COLORS.phosphorGreen },
            ].map((stat, idx) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 + idx * 0.1 }}
                className="rounded overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
              >
                {/* Mini Terminal Chrome */}
                <div className="flex items-center gap-1 px-2 py-1 border-b border-white/5 bg-white/[0.01]">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500/40" />
                  <div className="w-1.5 h-1.5 rounded-full bg-yellow-500/40" />
                  <div className="w-1.5 h-1.5 rounded-full bg-green-500/40" />
                </div>

                <div className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div
                      className="p-2 rounded border"
                      style={{ backgroundColor: `${stat.color}10`, borderColor: `${stat.color}20` }}
                    >
                      <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                    </div>
                    <span className={cn(
                      "text-[10px] font-mono px-1.5 py-0.5 rounded",
                      stat.change.startsWith('+') ? 'text-[var(--phosphor-green)] bg-[var(--phosphor-green)]/10' : 'text-[var(--terminal-text-muted)] bg-white/5'
                    )}>
                      {stat.change}
                    </span>
                  </div>
                  <div className="text-2xl font-mono font-bold text-white/90">{stat.value}</div>
                  <div className="text-xs font-mono text-white/40 mt-1">{stat.label}</div>
                </div>
              </motion.div>
            ))}
          </motion.div>

          {/* Main Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* System Status */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="lg:col-span-2 rounded overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
            >
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[var(--terminal-border)] bg-white/[0.02]">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                <div className="w-2 h-2 rounded-full bg-green-500/60" />
                <span className="ml-2 text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
                  System Performance
                </span>
                <Activity className="w-3 h-3 text-[var(--phosphor-green)] ml-auto animate-pulse" />
              </div>

              <div className="p-4">
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {services.map((service) => (
                    <div
                      key={service.name}
                      className="p-3 rounded border border-[var(--terminal-border)] bg-white/[0.02] hover:border-[var(--phosphor-green)]/20 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-mono text-[var(--terminal-text-muted)]">{service.name}</span>
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
                      </div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[10px] font-mono text-[var(--terminal-text-muted)]">{service.latency}</span>
                        <span className="text-[10px] font-mono text-[var(--phosphor-green)]">ONLINE</span>
                      </div>
                      {/* Load bar */}
                      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${service.load}%` }}
                          transition={{ duration: 1, delay: 0.5 }}
                          className="h-full rounded-full"
                          style={{
                            background: service.load > 60
                              ? `linear-gradient(90deg, ${COLORS.amber}, ${COLORS.amber})`
                              : `linear-gradient(90deg, ${COLORS.phosphorGreen}, ${COLORS.phosphorGreen}80)`
                          }}
                        />
                      </div>
                      <div className="text-[10px] font-mono text-[var(--terminal-text-muted)] mt-1">{service.load}% load</div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>

            {/* Activity Feed */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 }}
              className="rounded overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
            >
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[var(--terminal-border)] bg-white/[0.02]">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                <div className="w-2 h-2 rounded-full bg-green-500/60" />
                <span className="ml-2 text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
                  Activity Log
                </span>
                <Clock className="w-3 h-3 text-[var(--terminal-text-muted)] ml-auto" />
              </div>

              <div className="p-3">
                <div className="space-y-2">
                  {recentActivity.map((item, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: 10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.5 + idx * 0.1 }}
                      className="flex items-start gap-2 p-2 rounded border border-[var(--terminal-border)] bg-white/[0.01] hover:border-white/10 transition-colors"
                    >
                      <div className={cn(
                        "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0",
                        item.type === 'upload' && 'bg-[var(--phosphor-green)]',
                        item.type === 'search' && 'bg-blue-400',
                        item.type === 'chat' && 'bg-[var(--amber-gold)]',
                        item.type === 'process' && 'bg-purple-400'
                      )} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-mono text-[var(--terminal-text-muted)] truncate">{item.text}</p>
                        <p className="text-[10px] font-mono text-[var(--terminal-text-muted)]">{item.time}</p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>

          {/* Document Types & AI Insights */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Document Types */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="rounded overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
            >
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[var(--terminal-border)] bg-white/[0.02]">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                <div className="w-2 h-2 rounded-full bg-green-500/60" />
                <span className="ml-2 text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
                  Document Distribution
                </span>
                <BarChart3 className="w-3 h-3 text-[var(--terminal-text-muted)] ml-auto" />
              </div>

              <div className="p-4">
                <div className="space-y-3">
                  {docTypes.map((doc, idx) => (
                    <div key={doc.type} className="flex items-center gap-3">
                      <div
                        className="p-1.5 rounded border"
                        style={{ backgroundColor: `${doc.color}15`, borderColor: `${doc.color}30` }}
                      >
                        <doc.icon className="w-3.5 h-3.5" style={{ color: doc.color }} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-mono text-[var(--terminal-text-muted)]">{doc.type}</span>
                          <span className="text-xs font-mono text-[var(--terminal-text-muted)]">{doc.count}</span>
                        </div>
                        <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${(doc.count / stats.documents) * 100 || 0}%` }}
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
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="rounded overflow-hidden border border-[var(--terminal-border)] bg-[var(--terminal-surface)]"
            >
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-[var(--terminal-border)] bg-white/[0.02]">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                <div className="w-2 h-2 rounded-full bg-green-500/60" />
                <span className="ml-2 text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
                  AI Insights
                </span>
                <Brain className="w-3 h-3 text-[var(--amber-gold)] ml-auto" />
              </div>

              <div className="p-4 space-y-3">
                {[
                  { text: 'Knowledge graph expanded with 23 new entities', icon: Network, color: COLORS.phosphorGreen },
                  { text: 'Semantic search accuracy improved to 94.2%', icon: TrendingUp, color: COLORS.phosphorGreen },
                  { text: 'Processing queue optimized, 45% faster', icon: Gauge, color: COLORS.amber },
                ].map((insight, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.7 + idx * 0.1 }}
                    className="flex items-start gap-3 p-3 rounded border border-[var(--terminal-border)] bg-white/[0.02]"
                  >
                    <div
                      className="p-1.5 rounded border shrink-0"
                      style={{ backgroundColor: `${insight.color}10`, borderColor: `${insight.color}30` }}
                    >
                      <insight.icon className="w-3.5 h-3.5" style={{ color: insight.color }} />
                    </div>
                    <p className="text-xs font-mono text-[var(--terminal-text-muted)] leading-relaxed">{insight.text}</p>
                  </motion.div>
                ))}

                <Link href="/llm-chat">
                  <div className="flex items-center justify-between p-3 rounded border border-[var(--amber-gold)]/20 bg-[var(--amber-gold)]/5 hover:border-[var(--amber-gold)]/40 transition-colors cursor-pointer group">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-[var(--amber-gold)]" />
                      <span className="text-xs font-mono text-[var(--amber-gold)]">Start AI Chat Session</span>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-[var(--amber-gold)]/60 group-hover:text-[var(--amber-gold)] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
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
                  transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                  className="w-12 h-12 border-2 border-[var(--phosphor-green)]/30 border-t-[var(--phosphor-green)] rounded-full mx-auto"
                />
                <p className="text-sm font-mono text-[var(--terminal-text-muted)] mt-4">Initializing dashboard...</p>
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
