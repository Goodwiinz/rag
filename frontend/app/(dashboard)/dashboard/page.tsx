'use client';

import { useAuth } from '@/hooks/useAuth';
import { useDocuments } from '@/hooks/useDocuments';
import { getAnalytics } from '@/lib/analytics';
import { cn } from '@/lib/utils';
import {
  documentAnalyticsApi,
  searchAnalyticsApi,
  performanceApi,
} from '@/services/documentAnalyticsApi';
import type { FileTypeStats } from '@/services/documentAnalyticsApi';
import analyticsService from '@/services/analyticsService';
import type { ServiceStatus } from '@/services/analyticsService';
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
import { useCallback, useEffect, useState } from 'react';

// Import enhanced components
import { KeyboardShortcuts } from '@/components/dashboard/KeyboardShortcuts';
import { QuickSearch } from '@/components/dashboard/QuickSearch';
import { COLORS } from '@/theme/constants';

// Icon mapping for document types returned by the backend
const DOC_TYPE_ICON_MAP: Record<string, typeof FileText> = {
  pdf: FileText,
  image: ImageIcon,
  images: ImageIcon,
  video: FileVideo,
  audio: Music,
};

const DOC_TYPE_COLOR_MAP: Record<string, string> = {
  pdf: COLORS.error,
  image: COLORS.info,
  images: COLORS.info,
  video: COLORS.chart4,
  audio: COLORS.amber,
};

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

  // Live data state
  const [totalSearches, setTotalSearches] = useState<number>(0);
  const [totalChats, setTotalChats] = useState<number>(0);
  const [processingCount, setProcessingCount] = useState<number>(0);
  const [filesByType, setFilesByType] = useState<FileTypeStats[]>([]);
  const [services, setServices] = useState<
    Array<{ name: string; status: string; latency: string; load: number }>
  >([]);
  const [servicesState, setServicesState] = useState<
    'loading' | 'loaded' | 'error'
  >('loading');
  const [recentActivity, setRecentActivity] = useState<
    Array<{ type: string; text: string; time: string }>
  >([]);

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

  // Fetch dashboard data from backend APIs
  const fetchDashboardData = useCallback(async () => {
    if (!isAuthenticated || authLoading) return;

    // Fetch search stats
    searchAnalyticsApi
      .getCombinedSearchAnalytics()
      .then((data) => {
        setTotalSearches(data.totalSearches ?? 0);
      })
      .catch(() => {
        /* graceful fallback — keeps existing state */
      });

    // Fetch performance/realtime metrics (processing files + chat proxy)
    performanceApi
      .getDashboardOverview()
      .then((data) => {
        setTotalChats(data.totalSessions ?? 0);
      })
      .catch(() => {});

    // Fetch file stats (type breakdown + processing counts)
    documentAnalyticsApi
      .getFileStats()
      .then((data) => {
        setFilesByType(data.files_by_type ?? []);
        const pending = (data.processing_stats ?? [])
          .filter((s) => s.status === 'pending' || s.status === 'processing')
          .reduce((sum, s) => sum + s.count, 0);
        setProcessingCount(pending);
      })
      .catch(() => {});

    // Fetch service status via performance metrics
    analyticsService
      .getPerformanceMetrics()
      .then((data) => {
        const mappedServices = (data.services ?? []).map(
          (svc: ServiceStatus) => ({
            name: svc.name,
            status: svc.status === 'healthy' ? 'online' : svc.status,
            latency: `${svc.response_time}ms`,
            load: Math.min(100, Math.round((svc.response_time / 500) * 100)),
          })
        );
        if (mappedServices.length > 0) {
          setServices(mappedServices);
        }
        setServicesState('loaded');
      })
      .catch(() => {
        setServicesState('error');
      });

    // TODO: wire to /activity or /events endpoint when available
    // Recent activity has no backend endpoint yet — use empty or keep defaults
  }, [isAuthenticated, authLoading]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Stats — wired to real data, documents from useDocuments hook
  const stats = {
    documents: documents?.length ?? 0,
    searches: totalSearches,
    chats: totalChats,
    processing: processingCount,
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

  // System services — fallback to defaults when API hasn't responded yet
  const displayServices =
    services.length > 0
      ? services
      : [
          // TODO: wire to /health endpoint when available
          { name: 'API Gateway', status: 'online', latency: '—', load: 0 },
          { name: 'PostgreSQL', status: 'online', latency: '—', load: 0 },
          { name: 'Vector Store', status: 'online', latency: '—', load: 0 },
          { name: 'Neo4j Graph', status: 'online', latency: '—', load: 0 },
          { name: 'Redis Cache', status: 'online', latency: '—', load: 0 },
          { name: 'AI Engine', status: 'online', latency: '—', load: 0 },
        ];

  // Recent activity — wired to state, with fallback placeholder
  // TODO: wire to /activity or /events endpoint when available
  const displayActivity =
    recentActivity.length > 0
      ? recentActivity
      : [
          {
            type: 'process',
            text: 'Waiting for activity data...',
            time: 'just now',
          },
        ];

  // Document type breakdown — wired to real /files/stats data
  const totalDocCount = filesByType.reduce((sum, ft) => sum + ft.count, 0);
  const docTypes =
    filesByType.length > 0
      ? filesByType.map((ft) => ({
          type: ft.type.toUpperCase(),
          count: ft.count,
          icon: DOC_TYPE_ICON_MAP[ft.type.toLowerCase()] ?? FileText,
          color: DOC_TYPE_COLOR_MAP[ft.type.toLowerCase()] ?? COLORS.info,
        }))
      : [
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
    <div className="min-h-screen bg-[var(--nous-bg-1)] relative overflow-hidden flex flex-col">
      {/* Content */}
      <div className="relative p-6 space-y-6 flex-1 overflow-y-auto nous-scrollbar">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl overflow-hidden border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-xl"
        >
          <div className="h-0.5 bg-gradient-to-r from-[var(--nous-sol)] via-[var(--nous-sol)]/40 to-transparent" />
          <div className="p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/20 flex items-center justify-center">
                  <Terminal className="w-6 h-6 text-[var(--nous-sol)]" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-[var(--nous-fg-1)]">
                    System Overview
                    {user?.email ? `: ${user.email.split('@')[0]}` : ''}
                  </h1>
                  <p className="text-xs text-[var(--nous-fg-3)] mt-0.5 ">
                    Knowledge Base Metrics & Status
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/50">
                  <span className="text-[10px] text-[var(--nous-fg-3)] ">
                    UTC
                  </span>
                  <span className="text-xs text-[var(--nous-sol)]">
                    {mounted ? currentTime : '--:--:--'}
                  </span>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[var(--nous-sol)]/30 bg-[var(--nous-sol)]/5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--nous-sol)] opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--nous-sol)]" />
                  </span>
                  <span className="text-[10px] font-bold text-[var(--nous-sol)] ">
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
              className="rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--nous-sol)]"
            >
              <motion.div
                whileHover={{ y: -4 }}
                className={cn(
                  'group p-4 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] shadow-lg',
                  'hover:border-[var(--nous-sol)]/30 hover:shadow-[0_0_15px_rgba(212,160,57,0.06)] transition-all duration-300 cursor-pointer'
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
                  <span className="text-xs font-bold text-[var(--nous-fg-3)] group-hover:text-[var(--nous-fg-1)] transition-colors ">
                    {action.label}
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-[var(--nous-fg-3)]/40 ml-auto group-hover:text-[var(--nous-sol)] group-hover:translate-x-0.5 transition-all" />
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
              value: stats.documents,
              icon: FileText,
              color: COLORS.phosphorGreen,
            },
            {
              label: 'Daily Queries',
              value: stats.searches,
              icon: Search,
              color: COLORS.phosphorGreen,
            },
            {
              label: 'Active Conversations',
              value: stats.chats,
              icon: MessageSquare,
              color: COLORS.amber,
            },
            {
              label: 'Processing Queue',
              value: stats.processing,
              icon: Zap,
              color: COLORS.phosphorGreen,
            },
          ].map((stat, idx) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 + idx * 0.05 }}
              className="rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] p-5 shadow-lg relative group overflow-hidden"
            >
              <div
                className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b opacity-40 group-hover:opacity-100 transition-opacity"
                style={{
                  backgroundImage: `linear-gradient(to bottom, ${stat.color}, transparent)`,
                }}
              />

              <div className="flex items-start justify-between mb-4">
                <div className="p-2 rounded-lg bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)]">
                  <stat.icon
                    className="w-4 h-4"
                    style={{ color: stat.color }}
                  />
                </div>
              </div>
              <div className="text-2xl font-bold text-[var(--nous-fg-1)]">
                {stat.value}
              </div>
              <div className="text-[11px] text-[var(--nous-fg-3)] mt-1 ">
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
            className="lg:col-span-2 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/30">
              <Activity className="w-4 h-4 text-[var(--nous-sol)]" />
              <span className="text-xs font-bold text-[var(--nous-fg-1)] ">
                Active services
              </span>
            </div>

            <div className="p-5">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {displayServices.map((service) => (
                  <div
                    key={service.name}
                    className="p-4 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/20 hover:border-[var(--nous-sol)]/20 hover:shadow-[0_0_20px_rgba(212,160,57,0.06)] transition-all group"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[11px] text-[var(--nous-fg-3)] group-hover:text-[var(--nous-fg-1)] transition-colors">
                        {service.name}
                      </span>
                      {servicesState === 'loading' ? (
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--nous-helios)] opacity-75" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--nous-helios)]" />
                        </span>
                      ) : servicesState === 'error' ? (
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]" />
                      ) : (
                        <div className="w-1.5 h-1.5 rounded-full bg-[var(--nous-sol)] shadow-[0_0_8px_var(--nous-sol)]" />
                      )}
                    </div>
                    <div className="flex items-baseline gap-2 mb-3">
                      <span className="text-lg text-[var(--nous-fg-1)]">
                        {servicesState === 'loading' ? '...' : service.latency}
                      </span>
                      <span className="text-[9px] text-[var(--nous-fg-3)] font-bold ">
                        {servicesState === 'loading'
                          ? 'connecting'
                          : servicesState === 'error'
                            ? 'unreachable'
                            : 'DELAY'}
                      </span>
                    </div>
                    {/* Load bar */}
                    <div className="h-1 bg-[var(--nous-border-1)] rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${service.load}%` }}
                        transition={{ duration: 1, delay: 0.5 }}
                        className={cn(
                          'h-full rounded-full',
                          service.load < 50 && 'bg-[var(--nous-sol)]/50',
                          service.load >= 50 &&
                            service.load < 75 &&
                            'bg-[var(--nous-helios)]/60',
                          service.load >= 75 && 'bg-red-500/60'
                        )}
                      />
                    </div>
                    <div className="text-[9px] text-[var(--nous-fg-3)] mt-2 ">
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
            className="rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/30">
              <Clock className="w-4 h-4 text-[var(--nous-fg-3)]" />
              <span className="text-xs font-bold text-[var(--nous-fg-1)] ">
                Activity feed
              </span>
            </div>

            <div className="p-4">
              <div className="space-y-3">
                {displayActivity.map((item, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: 5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.5 + idx * 0.05 }}
                    className="flex items-start gap-3 p-3 rounded-lg border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/10 hover:bg-[var(--nous-bg-1)]/30 transition-colors group"
                  >
                    <div
                      className={cn(
                        'w-1 h-4 rounded-full mt-0.5 shrink-0 transition-all group-hover:h-6',
                        item.type === 'upload' && 'bg-[var(--nous-sol)]',
                        item.type === 'search' && 'bg-[var(--nous-helios)]',
                        item.type === 'chat' && 'bg-[var(--nous-helios)]',
                        item.type === 'process' && 'bg-purple-500',
                        idx === 0 && 'animate-pulse-live'
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] text-[var(--nous-fg-1)] truncate">
                        {item.text}
                      </p>
                      <p className="text-[9px] text-[var(--nous-fg-3)] mt-0.5">
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
            className="rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/30">
              <BarChart3 className="w-4 h-4 text-[var(--nous-fg-3)]" />
              <span className="text-xs font-bold text-[var(--nous-fg-1)] ">
                Corpus Distribution
              </span>
            </div>

            <div className="p-6">
              <div className="space-y-4">
                {docTypes.map((doc, idx) => (
                  <div key={doc.type} className="flex items-center gap-4">
                    <div className="p-2 rounded-lg bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)]">
                      <doc.icon
                        className="w-4 h-4"
                        style={{ color: doc.color }}
                      />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-[var(--nous-fg-1)] font-medium ">
                          {doc.type}
                        </span>
                        <span className="text-xs text-[var(--nous-fg-3)]">
                          {doc.count} units
                        </span>
                      </div>
                      <div className="h-1.5 bg-[var(--nous-border-1)] rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{
                            width: `${(doc.count / (totalDocCount || stats.documents || 1)) * 100}%`,
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
            className="rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)] overflow-hidden shadow-xl"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/30">
              <Brain className="w-4 h-4 text-[var(--nous-helios)]" />
              <span className="text-xs font-bold text-[var(--nous-fg-1)] ">
                Insights
              </span>
            </div>

            <div className="p-6 space-y-4">
              {[
                {
                  text: 'Knowledge graph insights will appear here as entities are extracted',
                  icon: Network,
                  color: COLORS.phosphorGreen,
                },
                {
                  text: 'Search quality metrics available after first 100 queries',
                  icon: TrendingUp,
                  color: COLORS.phosphorGreen,
                },
                {
                  text: 'Pipeline optimization stats populate with document processing',
                  icon: Gauge,
                  color: COLORS.amber,
                },
              ].map((insight, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -5 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.7 + idx * 0.1 }}
                  className="flex items-start gap-4 p-4 rounded-xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-1)]/20"
                >
                  <div className="p-2 rounded-lg bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] shrink-0">
                    <insight.icon
                      className="w-4 h-4"
                      style={{ color: insight.color }}
                    />
                  </div>
                  <p className="text-xs text-[var(--nous-fg-3)] leading-relaxed">
                    {insight.text}
                  </p>
                </motion.div>
              ))}

              <Link href="/chat">
                <div className="flex items-center justify-between p-4 rounded-xl border border-[var(--nous-helios)]/20 bg-[var(--nous-helios)]/5 hover:border-[var(--nous-helios)]/40 transition-all cursor-pointer group">
                  <div className="flex items-center gap-3">
                    <Sparkles className="w-4 h-4 text-[var(--nous-helios)]" />
                    <span className="text-xs font-bold text-[var(--nous-helios)] ">
                      Open chat
                    </span>
                  </div>
                  <ArrowUpRight className="w-4 h-4 text-[var(--nous-helios)]/60 group-hover:text-[var(--nous-helios)] group-hover:translate-x-1 group-hover:-translate-y-1 transition-all" />
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
            className="fixed inset-0 bg-[var(--nous-bg-1)] z-50 flex items-center justify-center"
          >
            <div className="text-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                className="w-10 h-10 border-2 border-[var(--nous-sol)]/10 border-t-[var(--nous-sol)] rounded-full mx-auto"
              />
              <p className="text-[10px] text-[var(--nous-fg-3)] mt-4 ">
                Loading dashboard…
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
