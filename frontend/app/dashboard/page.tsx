"use client";

import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { useDocuments } from '@/hooks/useDocuments';
import { getAnalytics } from '@/lib/analytics';
import {
  Activity,
  FileText,
  Search,
  MessageSquare,
  Zap,
  BarChart3,
  Database,
  Sparkles,
  Brain,
  Network,
  TrendingUp,
  Command,
  FileVideo,
  Image as ImageIcon,
  Music,
} from 'lucide-react';
import { motion, AnimatePresence, useMotionValue, useSpring } from 'framer-motion';
import { useState, useEffect } from 'react';

// Import enhanced components
import { StatsCard } from '@/components/dashboard/StatsCard';
import { StatsCardEnhanced } from '@/components/dashboard/StatsCardEnhanced';
import { AIInsightsPanelEnhanced } from '@/components/dashboard/AIInsightsPanelEnhanced';
import { ActivityFeedEnhanced } from '@/components/dashboard/ActivityFeedEnhanced';
import { QuickActionsGrid } from '@/components/dashboard/QuickActionsGrid';
import { SimpleLayout } from '@/components/layout/SimpleLayout';

// Import chart components
import {
  UploadTrendsChart,
  DocumentTypeDistribution,
  SearchActivitySparkline,
} from '@/components/dashboard/DashboardCharts';

// Import skeleton loaders
import {
  StatsCardSkeleton,
  AIInsightSkeleton,
  ActivityFeedSkeleton,
  ChartSkeleton,
} from '@/components/dashboard/SkeletonLoader';

// Import keyboard shortcuts and quick search
import { KeyboardShortcuts } from '@/components/dashboard/KeyboardShortcuts';
import { QuickSearch } from '@/components/dashboard/QuickSearch';

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading, user } = useAuth();
  const { documents, loading: docsLoading } = useDocuments({
    initialPageSize: 100,
    autoFetch: isAuthenticated && !authLoading,
  });

  // State management
  const [isLoading, setIsLoading] = useState(true);
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false);
  const [showQuickSearch, setShowQuickSearch] = useState(false);

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
    } catch (error) {
      // Analytics not initialized, silently ignore
    }
  }, [isAuthenticated, user, documents]);

  // Simulate loading state
  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  // Calculate stats
  const stats = {
    documents: documents?.length || 0,
    searches: 42,
    chats: 15,
    processing: 2,
  };

  // Sample data for charts
  const uploadTrendsData = [
    { date: 'Mon', uploads: 12 },
    { date: 'Tue', uploads: 19 },
    { date: 'Wed', uploads: 15 },
    { date: 'Thu', uploads: 25 },
    { date: 'Fri', uploads: 22 },
    { date: 'Sat', uploads: 30 },
    { date: 'Sun', uploads: 28 },
  ];

  const documentTypeData = [
    { type: 'PDF', count: stats.documents * 0.4, color: '#ef4444' },
    { type: 'Image', count: stats.documents * 0.3, color: '#3b82f6' },
    { type: 'Video', count: stats.documents * 0.2, color: '#8b5cf6' },
    { type: 'Audio', count: stats.documents * 0.1, color: '#f59e0b' },
  ];

  const searchActivityData = [
    { time: '00:00', searches: 5 },
    { time: '04:00', searches: 2 },
    { time: '08:00', searches: 15 },
    { time: '12:00', searches: 25 },
    { time: '16:00', searches: 20 },
    { time: '20:00', searches: 12 },
    { time: '23:59', searches: 8 },
  ];

  // Enhanced stats data for the new component
  const enhancedStats = [
    {
      id: '1',
      title: 'Total Documents',
      value: stats.documents.toString(),
      change: 12,
      changeType: 'increase' as const,
      icon: <FileText className="h-6 w-6" />,
      iconBg: 'bg-gradient-to-br from-blue-500/10 to-indigo-500/10',
      trend: [60, 70, 65, 80, 75, 90, 85, 100],
      description: '12% increase from last month',
    },
    {
      id: '2',
      title: 'Search Queries',
      value: stats.searches.toString(),
      change: 8,
      changeType: 'increase' as const,
      icon: <Search className="h-6 w-6" />,
      iconBg: 'bg-gradient-to-br from-emerald-500/10 to-green-500/10',
      trend: [40, 45, 50, 45, 60, 55, 70, 65],
      description: 'Avg response time: 0.34s',
    },
    {
      id: '3',
      title: 'AI Interactions',
      value: stats.chats.toString(),
      change: 23,
      changeType: 'increase' as const,
      icon: <MessageSquare className="h-6 w-6" />,
      iconBg: 'bg-gradient-to-br from-purple-500/10 to-pink-500/10',
      trend: [30, 40, 35, 50, 45, 60, 55, 70],
      description: 'High satisfaction rate',
    },
    {
      id: '4',
      title: 'Processing Queue',
      value: stats.processing.toString(),
      change: 0,
      changeType: 'neutral' as const,
      icon: <Zap className="h-6 w-6" />,
      iconBg: 'bg-gradient-to-br from-amber-500/10 to-orange-500/10',
      trend: [50, 45, 40, 35, 30, 25, 20, 15],
      description: 'All systems operational',
    },
  ];

  // Motion values for interactive effects
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const backgroundX = useSpring(mouseX);
  const backgroundY = useSpring(mouseY);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    mouseX.set(x - rect.width / 2);
    mouseY.set(y - rect.height / 2);
  };

  // Keyboard shortcuts handler
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

  return (
    <SimpleLayout>
      <motion.div
        className="relative min-h-full p-6 overflow-hidden"
        onMouseMove={handleMouseMove}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
      >
        {/* Enhanced animated background */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {/* Mouse-following gradients */}
          <motion.div
            className="absolute top-0 left-1/4 w-[800px] h-[800px] rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(251,191,36,0.06) 0%, transparent 70%)',
              x: backgroundX,
              y: backgroundY,
            }}
          />
          <motion.div
            className="absolute top-1/3 right-1/4 w-[600px] h-[600px] rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(251,146,60,0.04) 0%, transparent 70%)',
              x: -backgroundX,
              y: -backgroundY,
            }}
          />

          {/* Floating orbs with complex paths */}
          <motion.div
            animate={{
              y: [0, -50, 0, 50, 0],
              x: [0, 30, -20, 10, 0],
              rotate: [0, 180, 360],
            }}
            transition={{
              duration: 12,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="absolute top-20 right-20 w-96 h-96 bg-gradient-to-br from-amber-400/8 to-orange-400/8 rounded-full blur-3xl"
          />
          <motion.div
            animate={{
              y: [0, 40, 0, -30, 0],
              x: [0, -25, 15, -10, 0],
              rotate: [0, -180, -360],
            }}
            transition={{
              duration: 15,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 2,
            }}
            className="absolute bottom-20 left-20 w-[500px] h-[500px] bg-gradient-to-tr from-orange-400/8 to-amber-400/8 rounded-full blur-3xl"
          />

          {/* Animated pattern overlay */}
          <div className="absolute inset-0 opacity-30">
            <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <pattern id="dashboard-pattern" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
                  <circle cx="30" cy="30" r="1" fill="#f59e0b" className="opacity-20" />
                  <circle cx="10" cy="10" r="0.5" fill="#f97316" className="opacity-20" />
                  <circle cx="50" cy="50" r="0.5" fill="#f59e0b" className="opacity-20" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#dashboard-pattern)" />
            </svg>
          </div>
        </div>

        <div className="relative space-y-8">
          {/* Enhanced Welcome Header */}
          <motion.div
            className="relative overflow-hidden group"
            initial={{ opacity: 0, y: -30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-amber-500/5 via-transparent to-orange-500/5 backdrop-blur-xl" />
            <motion.div
              className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between p-6 rounded-2xl border border-amber-200/20 bg-white/60 backdrop-blur-lg shadow-lg hover:shadow-2xl transition-all duration-500"
              whileHover={{
                scale: 1.01,
                boxShadow: '0 20px 40px rgba(251,191,36,0.1)',
              }}
            >
              <div className="space-y-2">
                <motion.h1
                  className="text-4xl font-bold bg-gradient-to-r from-amber-700 via-orange-600 to-amber-700 bg-clip-text text-transparent"
                  initial={{ opacity: 0, x: -30 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.8, delay: 0.2 }}
                >
                  Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}!
                </motion.h1>
                <motion.p
                  className="text-lg text-gray-600"
                  initial={{ opacity: 0, x: -30 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.8, delay: 0.3 }}
                >
                  Here's what's happening with your knowledge base today.
                </motion.p>
                <motion.div
                  className="flex items-center gap-2 text-sm text-gray-500"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5 }}
                >
                  <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded-md text-xs">
                    ⌘K
                  </kbd>
                  <span>Quick search</span>
                  <span>•</span>
                  <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded-md text-xs">
                    ?
                  </kbd>
                  <span>Shortcuts</span>
                </motion.div>
              </div>

              <motion.div
                className="flex items-center gap-3 px-5 py-3 rounded-full bg-gradient-to-r from-emerald-500/10 to-emerald-600/10 border border-emerald-500/20 backdrop-blur-sm shadow-lg"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.8, delay: 0.4 }}
                whileHover={{
                  scale: 1.05,
                  boxShadow: '0 0 30px rgba(16,185,129,0.3)',
                }}
              >
                <motion.div
                  className="relative w-3 h-3 rounded-full bg-emerald-500"
                  animate={{
                    scale: [1, 1.3, 1],
                    opacity: [1, 0.7, 1],
                    boxShadow: ['0 0 0 0 rgba(16,185,129,0.7)', '0 0 0 10px rgba(16,185,129,0)', '0 0 0 0 rgba(16,185,129,0)'],
                  }}
                  transition={{ duration: 2, repeat: Infinity }}
                />
                <span className="text-sm font-medium text-emerald-700">All systems operational</span>
              </motion.div>
            </motion.div>
          </motion.div>

          {/* Enhanced Stats Grid with Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Enhanced Stats Cards */}
            <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <>
                    <StatsCardSkeleton />
                    <StatsCardSkeleton />
                    <StatsCardSkeleton />
                  </>
                ) : (
                  enhancedStats.map((stat, index) => (
                    <StatsCardEnhanced key={stat.id} stat={stat} index={index} />
                  ))
                )}
              </AnimatePresence>
            </div>

            {/* Search Activity Sparkline */}
            <div className="h-48">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <ChartSkeleton height="h-full" />
                ) : (
                  <div className="h-full p-4 rounded-2xl bg-white/60 backdrop-blur-lg border border-amber-200/20 shadow-lg">
                    <SearchActivitySparkline data={searchActivityData} />
                  </div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="h-64">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <ChartSkeleton height="h-full" />
                ) : (
                  <div className="h-full p-4 rounded-2xl bg-white/60 backdrop-blur-lg border border-amber-200/20 shadow-lg">
                    <UploadTrendsChart data={uploadTrendsData} />
                  </div>
                )}
              </AnimatePresence>
            </div>
            <div className="h-64">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <ChartSkeleton height="h-full" />
                ) : (
                  <div className="h-full p-4 rounded-2xl bg-white/60 backdrop-blur-lg border border-amber-200/20 shadow-lg">
                    <DocumentTypeDistribution data={documentTypeData} />
                  </div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column - AI Insights */}
            <div className="lg:col-span-2">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <div className="space-y-4">
                    <AIInsightSkeleton />
                    <AIInsightSkeleton />
                  </div>
                ) : (
                  <motion.div
                    initial={{ opacity: 0, x: -50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: 0.7 }}
                  >
                    <AIInsightsPanelEnhanced />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Right Column - Activity Feed */}
            <div className="lg:col-span-1">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <ActivityFeedSkeleton />
                ) : (
                  <motion.div
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.6, delay: 0.8 }}
                  >
                    <ActivityFeedEnhanced />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Quick Actions Grid */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.9 }}
          >
            <QuickActionsGrid />
          </motion.div>

          {/* System Performance Metrics */}
          <motion.div
            className="relative overflow-hidden group"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 1.0 }}
          >
            <div className="p-6 rounded-2xl bg-white/60 backdrop-blur-lg border border-amber-200/20 shadow-lg hover:shadow-2xl transition-all duration-500">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-amber-500" />
                  System Performance
                </h3>
                <TrendingUp className="h-4 w-4 text-emerald-500" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { name: 'Backend API', status: 'Online', latency: '42ms', icon: Zap, color: 'emerald' },
                  { name: 'Vector Store', status: 'Online', latency: '18ms', icon: Sparkles, color: 'blue' },
                  { name: 'Knowledge Graph', status: 'Online', latency: '24ms', icon: Network, color: 'amber' },
                  { name: 'AI Processing', status: 'Online', latency: '156ms', icon: Brain, color: 'purple' },
                ].map((service, index) => (
                  <motion.div
                    key={service.name}
                    className="relative p-4 rounded-xl bg-gradient-to-br from-gray-50/50 to-white/50 border border-gray-200/30 hover:shadow-lg transition-all duration-300"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 1.1 + index * 0.1 }}
                    whileHover={{
                      scale: 1.05,
                      backgroundColor: 'rgba(251,191,36,0.05)',
                    }}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`p-2 rounded-lg bg-${service.color}-100`}>
                        <service.icon className={`h-4 w-4 text-${service.color}-600`} />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-800">{service.name}</p>
                        <p className="text-xs text-gray-500">{service.latency}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <motion.div
                        className={`w-2 h-2 rounded-full bg-${service.color}-500`}
                        animate={{
                          scale: [1, 1.5, 1],
                          opacity: [1, 0.7, 1],
                        }}
                        transition={{ duration: 2, repeat: Infinity, delay: index * 0.2 }}
                      />
                      <span className={`text-xs font-medium text-${service.color}-600`}>{service.status}</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Loading Overlay */}
        <AnimatePresence>
          {isLoading && (
            <motion.div
              className="absolute inset-0 flex items-center justify-center bg-white/90 backdrop-blur-sm z-50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.div
                className="flex flex-col items-center gap-4"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.8, opacity: 0 }}
              >
                <motion.div
                  className="relative w-20 h-20"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                >
                  <div className="absolute inset-0 rounded-full border-4 border-gray-200" />
                  <div className="absolute inset-0 rounded-full border-4 border-amber-500 border-t-transparent" />
                  <div className="absolute inset-0 rounded-full border-4 border-orange-500 border-r-transparent" />
                </motion.div>
                <span className="text-sm text-gray-600">Loading amazing dashboard...</span>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Keyboard Shortcuts Modal */}
        <KeyboardShortcuts
          isOpen={showKeyboardShortcuts}
          onClose={() => setShowKeyboardShortcuts(false)}
        />

        {/* Quick Search Modal */}
        <QuickSearch
          isOpen={showQuickSearch}
          onClose={() => setShowQuickSearch(false)}
        />
      </motion.div>
    </SimpleLayout>
  );
}