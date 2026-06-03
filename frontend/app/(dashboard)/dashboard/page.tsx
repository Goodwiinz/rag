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
import { motion, MotionConfig } from 'framer-motion';
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
  TrendingUp,
  Upload,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

// Import enhanced components
import { KeyboardShortcuts } from '@/components/dashboard/KeyboardShortcuts';
import { QuickSearch } from '@/components/dashboard/QuickSearch';

// Icon mapping for document types returned by the backend
const DOC_TYPE_ICON_MAP: Record<string, typeof FileText> = {
  pdf: FileText,
  image: ImageIcon,
  images: ImageIcon,
  video: FileVideo,
  audio: Music,
};

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  // Only the total count is needed here, so fetch a single page, not 100 docs.
  const { pagination } = useDocuments({
    initialPageSize: 1,
    autoFetch: isAuthenticated && !authLoading,
  });
  const documentCount = pagination?.total ?? 0;

  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [showQuickSearch, setShowQuickSearch] = useState(false);

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
  const [recentActivity] = useState<
    Array<{ type: string; text: string; time: string }>
  >([]);

  // Analytics tracking
  useEffect(() => {
    try {
      const analytics = getAnalytics();
      analytics.trackPageView('/dashboard', 'Dashboard');
      if (isAuthenticated && user) {
        analytics.trackFeatureUsage('dashboard', 'viewed', {
          documentCount,
          authProvider: 'email',
        });
      }
    } catch {
      // Analytics not initialized
    }
  }, [isAuthenticated, user, documentCount]);

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
  }, [isAuthenticated, authLoading]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Stats — wired to real data, documents from useDocuments hook
  const stats = {
    documents: documentCount,
    searches: totalSearches,
    chats: totalChats,
    processing: processingCount,
  };

  // Quick actions
  const quickActions = [
    { icon: Upload, label: 'Upload', href: '/documents/upload' },
    { icon: Search, label: 'Search', href: '/search' },
    { icon: Bot, label: 'Chat', href: '/chat' },
    { icon: Database, label: 'arXiv', href: '/arxiv' },
  ];

  // System services — real data only. Loading / empty / error states render
  // honestly in the panel below; no fabricated "online" placeholders.
  const hasServiceData = services.length > 0;

  // Recent activity — real data only; an honest empty state renders below.
  // TODO: wire to /activity or /events endpoint when available
  const hasActivity = recentActivity.length > 0;

  // Document type breakdown — real /files/stats data only (no fabricated split).
  const totalDocCount = filesByType.reduce((sum, ft) => sum + ft.count, 0);
  const docTypes = filesByType.map((ft) => ({
    type: ft.type.toUpperCase(),
    count: ft.count,
    icon: DOC_TYPE_ICON_MAP[ft.type.toLowerCase()] ?? FileText,
  }));
  const hasDocTypes = docTypes.length > 0;

  const statCards = [
    { label: 'Documents', value: stats.documents, icon: FileText },
    { label: 'Searches', value: stats.searches, icon: Search },
    { label: 'Conversations', value: stats.chats, icon: MessageSquare },
    { label: 'Processing', value: stats.processing, icon: Zap },
  ];

  const insights = [
    {
      text: 'Knowledge-graph insights appear here as entities are extracted.',
      icon: Network,
    },
    {
      text: 'Search-quality metrics become available after your first 100 queries.',
      icon: TrendingUp,
    },
    {
      text: 'Pipeline stats populate as documents are processed.',
      icon: Gauge,
    },
  ];

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen bg-background relative flex flex-col">
        {/* Content */}
        <div className="relative p-6 space-y-6 flex-1 overflow-y-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-border bg-card shadow-sm"
          >
            <div className="p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Gauge
                      aria-hidden="true"
                      className="w-6 h-6 text-primary"
                    />
                  </div>
                  <div>
                    <h1 className="text-xl font-semibold text-foreground">
                      Overview
                      {user?.email ? `, ${user.email.split('@')[0]}` : ''}
                    </h1>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      Knowledge base metrics and status
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div
                    role="status"
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-primary/30 bg-primary/5"
                  >
                    <span
                      aria-hidden="true"
                      className="inline-flex h-2 w-2 rounded-full bg-primary"
                    />
                    <span className="text-xs font-medium text-primary">
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
                className="rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <motion.div
                  whileHover={{ y: -2 }}
                  className="group p-4 rounded-xl border border-border bg-card shadow-sm hover:border-[var(--nous-helios)] hover:shadow-md transition-all duration-300 cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      <action.icon aria-hidden="true" className="w-4 h-4" />
                    </div>
                    <span className="text-sm font-medium text-foreground">
                      {action.label}
                    </span>
                    <ChevronRight
                      aria-hidden="true"
                      className="w-3.5 h-3.5 text-muted-foreground ml-auto group-hover:text-primary group-hover:translate-x-0.5 transition-all"
                    />
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
            {statCards.map((stat, idx) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.2 + idx * 0.05 }}
                className="rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="p-2 rounded-lg bg-muted text-primary">
                    <stat.icon aria-hidden="true" className="w-4 h-4" />
                  </div>
                </div>
                <div className="text-2xl font-semibold text-foreground tabular-nums">
                  {stat.value}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {stat.label}
                </div>
              </motion.div>
            ))}
          </motion.div>

          {/* Main Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Service health */}
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden shadow-sm"
            >
              <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-muted/30">
                <Activity aria-hidden="true" className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-foreground">
                  Service health
                </span>
              </div>

              <div className="p-5">
                {servicesState === 'error' ? (
                  <div
                    role="alert"
                    className="flex flex-col items-start gap-3 p-4 rounded-xl border border-border bg-muted/20"
                  >
                    <p className="text-sm text-foreground">
                      Couldn&apos;t reach the service health endpoint.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setServicesState('loading');
                        fetchDashboardData();
                      }}
                      className="text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
                    >
                      Retry
                    </button>
                  </div>
                ) : !hasServiceData ? (
                  <div
                    role="status"
                    className="p-4 text-sm text-muted-foreground"
                  >
                    {servicesState === 'loading'
                      ? 'Checking service health…'
                      : 'No service data available.'}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {services.map((service) => {
                      const online = service.status === 'online';
                      const statusLabel = online ? 'Online' : service.status;
                      return (
                        <div
                          key={service.name}
                          className="p-4 rounded-xl border border-border bg-muted/20 hover:border-[var(--nous-helios)] hover:shadow-md transition-all group"
                        >
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                              {service.name}
                            </span>
                            <span className="flex items-center gap-1.5">
                              <span
                                aria-hidden="true"
                                className={cn(
                                  'w-1.5 h-1.5 rounded-full',
                                  online
                                    ? 'bg-[var(--nous-terra)]'
                                    : 'bg-[var(--nous-mars)]'
                                )}
                              />
                              <span className="text-[11px] text-muted-foreground">
                                {statusLabel}
                              </span>
                            </span>
                          </div>
                          <div className="flex items-baseline gap-2 mb-3">
                            <span className="text-lg font-medium text-foreground tabular-nums">
                              {service.latency}
                            </span>
                            <span className="text-[11px] text-muted-foreground">
                              latency
                            </span>
                          </div>
                          {/* Load bar */}
                          <div
                            className="h-1 bg-border rounded-full overflow-hidden"
                            role="progressbar"
                            aria-valuenow={service.load}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-label={`${service.name} resource load`}
                          >
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${service.load}%` }}
                              transition={{ duration: 1, delay: 0.5 }}
                              className={cn(
                                'h-full rounded-full',
                                service.load < 50 && 'bg-[var(--nous-terra)]',
                                service.load >= 50 &&
                                  service.load < 75 &&
                                  'bg-[var(--nous-helios)]',
                                service.load >= 75 && 'bg-[var(--nous-mars)]'
                              )}
                            />
                          </div>
                          <div className="text-[11px] text-muted-foreground mt-2">
                            {service.load}% resource load
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </motion.div>

            {/* Recent activity */}
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 }}
              className="rounded-xl border border-border bg-card overflow-hidden shadow-sm"
            >
              <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-muted/30">
                <Clock
                  aria-hidden="true"
                  className="w-4 h-4 text-muted-foreground"
                />
                <span className="text-sm font-medium text-foreground">
                  Recent activity
                </span>
              </div>

              <div className="p-4">
                {!hasActivity ? (
                  <p className="p-3 text-sm text-muted-foreground">
                    No recent activity yet.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {recentActivity.map((item, idx) => (
                      <motion.div
                        key={`${item.type}-${idx}`}
                        initial={{ opacity: 0, x: 5 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.5 + idx * 0.05 }}
                        className="flex items-start gap-3 p-3 rounded-lg border border-border bg-muted/10 hover:bg-muted/30 transition-colors group"
                      >
                        <div
                          aria-hidden="true"
                          className="w-1 h-4 rounded-full mt-0.5 shrink-0 bg-primary transition-all group-hover:h-6"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-foreground truncate">
                            {item.text}
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {item.time}
                          </p>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          </div>

          {/* Document types & Insights */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-6">
            {/* Document types */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="rounded-xl border border-border bg-card overflow-hidden shadow-sm"
            >
              <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-muted/30">
                <BarChart3
                  aria-hidden="true"
                  className="w-4 h-4 text-muted-foreground"
                />
                <span className="text-sm font-medium text-foreground">
                  Document types
                </span>
              </div>

              <div className="p-6">
                {!hasDocTypes ? (
                  <p className="text-sm text-muted-foreground">
                    No documents indexed yet.{' '}
                    <Link
                      href="/documents/upload"
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      Upload your first document
                    </Link>
                    .
                  </p>
                ) : (
                  <div className="space-y-4">
                    {docTypes.map((doc, idx) => (
                      <div key={doc.type} className="flex items-center gap-4">
                        <div className="p-2 rounded-lg bg-muted text-primary">
                          <doc.icon aria-hidden="true" className="w-4 h-4" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-sm font-medium text-foreground">
                              {doc.type}
                            </span>
                            <span className="text-sm text-muted-foreground tabular-nums">
                              {doc.count}
                            </span>
                          </div>
                          <div
                            className="h-1.5 bg-border rounded-full overflow-hidden"
                            role="progressbar"
                            aria-valuenow={doc.count}
                            aria-valuemin={0}
                            aria-valuemax={totalDocCount || doc.count}
                            aria-label={`${doc.type} document count`}
                          >
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{
                                width: `${(doc.count / (totalDocCount || 1)) * 100}%`,
                              }}
                              transition={{
                                duration: 1,
                                delay: 0.6 + idx * 0.1,
                              }}
                              className="h-full rounded-full bg-primary"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>

            {/* Insights */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="rounded-xl border border-border bg-card overflow-hidden shadow-sm"
            >
              <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-muted/30">
                <Brain aria-hidden="true" className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium text-foreground">
                  Insights
                </span>
              </div>

              <div className="p-6 space-y-4">
                {insights.map((insight, idx) => (
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.7 + idx * 0.1 }}
                    className="flex items-start gap-4 p-4 rounded-xl border border-border bg-muted/20"
                  >
                    <div className="p-2 rounded-lg bg-muted text-muted-foreground shrink-0">
                      <insight.icon aria-hidden="true" className="w-4 h-4" />
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {insight.text}
                    </p>
                  </motion.div>
                ))}

                <Link
                  href="/chat"
                  className="block rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <div className="flex items-center justify-between p-4 rounded-xl border border-primary/20 bg-primary/5 hover:border-primary/40 transition-all group">
                    <div className="flex items-center gap-3">
                      <Sparkles
                        aria-hidden="true"
                        className="w-4 h-4 text-primary"
                      />
                      <span className="text-sm font-medium text-primary">
                        Open the research chat
                      </span>
                    </div>
                    <ArrowUpRight
                      aria-hidden="true"
                      className="w-4 h-4 text-primary/60 group-hover:text-primary group-hover:translate-x-1 group-hover:-translate-y-1 transition-all"
                    />
                  </div>
                </Link>
              </div>
            </motion.div>
          </div>
        </div>

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
    </MotionConfig>
  );
}
