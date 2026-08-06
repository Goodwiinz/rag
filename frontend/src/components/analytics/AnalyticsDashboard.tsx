'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  documentAnalyticsApi,
  DocumentResponse,
  FileTypeStats,
  performanceApi,
  ProcessingStats,
  searchAnalyticsApi,
  TrendDataPoint,
  userBehaviorApi,
} from '@/services/documentAnalyticsApi';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle,
  Clock,
  Download,
  FileText,
  Info,
  MessageSquare,
  RefreshCw,
  Search,
  TrendingUp,
  Users,
  XCircle,
} from 'lucide-react';
import { motion, MotionConfig } from 'framer-motion';
import { useEffect, useMemo, useState } from 'react';
import { AnalyticsChart } from './AnalyticsChart';
import { AnalyticsOverview } from './AnalyticsOverview';
import {
  AnalyticsTable,
  createDocumentAnalyticsTable,
  createSearchAnalyticsTable,
} from './AnalyticsTable';

interface AnalyticsDashboardProps {
  className?: string;
}

// Generate fallback trend data when API returns empty
const generateFallbackTrendData = (): TrendDataPoint[] => {
  const now = new Date();
  const data: TrendDataPoint[] = [];

  for (let i = 29; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    data.push({
      date: date.toISOString().split('T')[0],
      name: date.toISOString().split('T')[0],
      pageViews: 0,
      uniqueVisitors: 0,
      documentsUploaded: 0,
      searchesPerformed: 0,
      chatsInitiated: 0,
    });
  }

  return data;
};

// Transform API document to table format
const transformDocumentToTableRow = (doc: DocumentResponse) => ({
  id: doc.id,
  filename: doc.filename,
  type: doc.document_type,
  size: doc.file_size_bytes,
  uploadedAt: doc.created_at,
  status: doc.processing_status,
});

// Transform file type stats for pie chart
const transformFileTypeForChart = (stats: FileTypeStats[]) =>
  stats.map((item) => ({
    name: item.type.toUpperCase(),
    value: item.count,
  }));

// Transform processing stats for display. Each status pairs an icon with its
// label, so color is never the only signal.
const transformProcessingStats = (stats: ProcessingStats[]) => {
  const statusConfig: Record<string, { icon: any; color: string }> = {
    completed: { icon: CheckCircle, color: 'text-[var(--nous-terra)]' },
    processing: { icon: Clock, color: 'text-primary' },
    failed: { icon: XCircle, color: 'text-[var(--nous-mars)]' },
    pending: { icon: Clock, color: 'text-muted-foreground' },
  };

  return stats.map((item) => ({
    status: item.status.charAt(0).toUpperCase() + item.status.slice(1),
    count: item.count,
    icon: statusConfig[item.status]?.icon || Clock,
    color: statusConfig[item.status]?.color || 'text-muted-foreground',
  }));
};

export function AnalyticsDashboard({ className }: AnalyticsDashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Names of the data sources that failed to load on the last fetch. Each
  // endpoint still falls back to an empty shape so the page never blanks, but
  // we record the failures so partial outages aren't silently shown as zeros.
  const [partialFailures, setPartialFailures] = useState<string[]>([]);
  const [data, setData] = useState<any>({
    overview: null,
    documents: [],
    searches: [],
    chartData: [],
    fileTypeDistribution: [],
    processingStats: [],
    realtimeMetrics: null,
  });

  // Load data from API
  const loadData = async () => {
    setLoading(true);
    setError(null);

    // Track which sources fail so we can tell the user honestly rather than
    // rendering a failed endpoint as a real "0".
    const failed: string[] = [];
    const note = (label: string) => failed.push(label);

    try {
      // Fetch data from multiple API endpoints in parallel
      const [
        fileStats,
        documentsResponse,
        searchAnalytics,
        userTrends,
        dashboardOverview,
        realtimeMetrics,
        trendData,
      ] = await Promise.all([
        documentAnalyticsApi.getFileStats().catch(() => {
          note('Documents');
          return {
            files_by_type: [],
            processing_stats: [],
          };
        }),
        documentAnalyticsApi.getDocuments({ page: 1, size: 25 }).catch(() => {
          note('Document list');
          return {
            documents: [],
            pagination: {
              page: 1,
              page_size: 25,
              total: 0,
              total_pages: 0,
              has_next: false,
              has_prev: false,
            },
          };
        }),
        searchAnalyticsApi.getCombinedSearchAnalytics().catch(() => {
          note('Search');
          return {
            topQueries: [],
            searchTypes: [],
            totalSearches: 0,
            avgResponseTime: 0,
          };
        }),
        userBehaviorApi.getOrganizationTrends(30).catch(() => {
          note('User trends');
          return {
            stats: {
              total_users: 0,
              active_users_today: 0,
              active_users_week: 0,
              active_users_month: 0,
              total_sessions: 0,
              avg_session_duration: 0,
              bounce_rate: 0,
              search_volume_today: 0,
              search_volume_week: 0,
              new_users: 0,
              returning_users: 0,
            },
            trendData: [],
          };
        }),
        performanceApi.getDashboardOverview().catch(() => {
          note('Overview');
          return {
            totalUsers: 0,
            activeUsers: 0,
            totalSessions: 0,
            totalSearches: 0,
            avgResponseTime: 0,
            errorRate: 0,
          };
        }),
        performanceApi.getRealtimeMetrics().catch(() => {
          note('Real-time metrics');
          return {
            activeUsers: 0,
            currentSearches: 0,
            processingFiles: 0,
            requestsPerMinute: 0,
          };
        }),
        performanceApi.getTrendData(30).catch(() => {
          note('Trends');
          return [];
        }),
      ]);

      // Transform API data
      const documentTableData = documentsResponse.documents.map(
        transformDocumentToTableRow
      );
      const fileTypeDistribution = transformFileTypeForChart(
        fileStats.files_by_type
      );
      const processingStats = transformProcessingStats(
        fileStats.processing_stats
      );

      // Use API trend data or fallback
      const chartData =
        trendData.length > 0
          ? trendData
          : userTrends.trendData.length > 0
            ? userTrends.trendData
            : generateFallbackTrendData();

      // Calculate totals from real data
      let totalDocuments = 0;
      fileStats.files_by_type.forEach((item) => {
        totalDocuments += item.count;
      });
      const completedDocs =
        fileStats.processing_stats.find((s) => s.status === 'completed')
          ?.count || 0;

      // Use real data from APIs, with fallbacks
      const totalUsers =
        dashboardOverview.totalUsers || userTrends.stats.total_users || 0;
      const activeUsers =
        dashboardOverview.activeUsers ||
        userTrends.stats.active_users_today ||
        0;
      const totalSessions =
        dashboardOverview.totalSessions || userTrends.stats.total_sessions || 0;
      const totalSearches =
        searchAnalytics.totalSearches ||
        dashboardOverview.totalSearches ||
        userTrends.stats.search_volume_week ||
        0;

      setData({
        overview: {
          totalUsers,
          activeUsers,
          totalSessions,
          totalPageViews: chartData.reduce(
            (sum: number, d: TrendDataPoint) => sum + d.pageViews,
            0
          ),
          averageSessionDuration: userTrends.stats.avg_session_duration || 0,
          bounceRate: userTrends.stats.bounce_rate || 0,
          documentsUploaded: totalDocuments,
          documentsCompleted: completedDocs,
          searchesPerformed: totalSearches,
          chatsInitiated: chartData.reduce(
            (sum: number, d: TrendDataPoint) => sum + d.chatsInitiated,
            0
          ),
          errorRate: dashboardOverview.errorRate || 0,
        },
        chartData,
        documents: documentTableData,
        searches: searchAnalytics.topQueries,
        searchTypes: searchAnalytics.searchTypes,
        fileTypeDistribution,
        processingStats,
        pagination: documentsResponse.pagination,
        realtimeMetrics,
      });

      // Surface a non-blocking note for any sources that didn't load, so a
      // partial outage isn't mistaken for genuine zero activity.
      setPartialFailures(Array.from(new Set(failed)));
    } catch (err) {
      console.error('Failed to load analytics data:', err);
      setError('Failed to load analytics data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    loadData();
  };

  // Serialize the currently loaded document rows to CSV and trigger a download.
  // This exports exactly the rows on screen, not an invented full-corpus export.
  const handleExport = () => {
    const rows = data.documents ?? [];
    if (rows.length === 0) return;

    const headers = ['Filename', 'Type', 'Size (bytes)', 'Uploaded', 'Status'];
    const escape = (value: unknown) => {
      const str = String(value ?? '');
      return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
    };
    const lines = [
      headers.join(','),
      ...rows.map((row: any) =>
        [row.filename, row.type, row.size, row.uploadedAt, row.status]
          .map(escape)
          .join(',')
      ),
    ];

    const blob = new Blob([lines.join('\n')], {
      type: 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `analytics-documents-${new Date()
      .toISOString()
      .slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleMetricClick = (metric: string) => {
    // Surface the selected metric's tab so the click resolves to something real
    // rather than a no-op. Document and search metrics map to their own tabs.
    const tabForMetric: Record<string, string> = {
      documents: 'documents',
      searches: 'search',
      activeUsers: 'realtime',
    };
    setActiveTab(tabForMetric[metric] ?? 'overview');
  };

  const documentTableConfig = useMemo(() => createDocumentAnalyticsTable(), []);
  const searchTableConfig = useMemo(() => createSearchAnalyticsTable(), []);

  // Summary stats shown in the top row. Consistent neutral cards with a single
  // warm-gold accent on the icon, matching the dashboard vocabulary.
  const summaryStats = [
    {
      label: 'Active users',
      value: data.overview?.totalUsers ?? 0,
      icon: Users,
    },
    {
      label: 'Documents',
      value: data.overview?.documentsUploaded ?? 0,
      icon: FileText,
    },
    {
      label: 'Searches',
      value: data.overview?.searchesPerformed ?? 0,
      icon: Search,
    },
    {
      label: 'Conversations',
      value: data.overview?.chatsInitiated ?? 0,
      icon: MessageSquare,
    },
  ];

  if (loading && !data.overview) {
    return (
      <div className={cn('w-full space-y-6', className)}>
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <div className="h-7 w-40 rounded-md bg-muted animate-pulse" />
            <div className="h-4 w-72 rounded-md bg-muted/60 animate-pulse" />
          </div>
          <div className="h-9 w-44 rounded-md bg-muted animate-pulse" />
        </div>

        {/* Stat card skeletons */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-card p-5 shadow-sm"
            >
              <div className="h-9 w-9 rounded-lg bg-muted animate-pulse" />
              <div className="mt-4 h-7 w-16 rounded-md bg-muted animate-pulse" />
              <div className="mt-2 h-3 w-20 rounded-md bg-muted/60 animate-pulse" />
            </div>
          ))}
        </div>

        {/* Body skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-card p-6 shadow-sm"
            >
              <div className="h-4 w-32 rounded-md bg-muted animate-pulse" />
              <div className="mt-4 h-[260px] rounded-lg bg-muted/40 animate-pulse" />
            </div>
          ))}
        </div>
        <span className="sr-only" role="status">
          Loading analytics
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('w-full', className)}>
        <div
          role="alert"
          className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-xl border border-border bg-card p-8 text-center shadow-sm"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[var(--nous-mars)]/10">
            <AlertTriangle
              aria-hidden="true"
              className="h-6 w-6 text-[var(--nous-mars)]"
            />
          </div>
          <div className="space-y-1">
            <p className="text-base font-semibold text-foreground">
              Couldn&apos;t load analytics
            </p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </div>
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw aria-hidden="true" className="mr-2 h-4 w-4" />
            Try again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className={cn('w-full space-y-6', className)}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between"
        >
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
              <BarChart3 aria-hidden="true" className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-foreground">
                Analytics
              </h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Pipeline throughput and activity across your knowledge base
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={loading}
              className="min-h-[44px] sm:min-h-0"
            >
              <RefreshCw
                aria-hidden="true"
                className={cn('mr-2 h-4 w-4', loading && 'animate-spin')}
              />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={loading || (data.documents?.length ?? 0) === 0}
              className="min-h-[44px] sm:min-h-0"
            >
              <Download aria-hidden="true" className="mr-2 h-4 w-4" />
              Export CSV
            </Button>
          </div>
        </motion.div>

        {/* Quick stats */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 gap-4 md:grid-cols-4"
        >
          {summaryStats.map((stat) => (
            <div
              key={stat.label}
              className="rounded-xl border border-border bg-card p-5 shadow-sm"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-primary">
                <stat.icon aria-hidden="true" className="h-4 w-4" />
              </div>
              <p className="mt-4 text-2xl font-semibold tabular-nums text-foreground">
                {stat.value.toLocaleString()}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{stat.label}</p>
            </div>
          ))}
        </motion.div>

        {/* Partial failure note. Non-blocking: the rest of the page still
            renders, but we don't pretend the missing numbers are real zeros. */}
        {partialFailures.length > 0 && (
          <div
            role="status"
            className="flex items-start gap-3 rounded-xl border border-[var(--nous-corona)]/30 bg-[var(--nous-corona)]/10 p-4"
          >
            <Info
              aria-hidden="true"
              className="mt-0.5 h-4 w-4 shrink-0 text-[var(--nous-corona)]"
            />
            <p className="text-sm text-foreground">
              Some data couldn&apos;t be loaded ({partialFailures.join(', ')}).
              Those sections may be incomplete. Try refreshing to load them
              again.
            </p>
          </div>
        )}

        {/* Main Content Tabs */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-2 sm:grid-cols-4">
            <TabsTrigger
              value="overview"
              className="flex min-h-[44px] items-center gap-2 sm:min-h-0"
            >
              <BarChart3 aria-hidden="true" className="h-4 w-4 shrink-0" />
              Overview
            </TabsTrigger>
            <TabsTrigger
              value="documents"
              className="flex min-h-[44px] items-center gap-2 sm:min-h-0"
            >
              <FileText aria-hidden="true" className="h-4 w-4 shrink-0" />
              Documents
            </TabsTrigger>
            <TabsTrigger
              value="search"
              className="flex min-h-[44px] items-center gap-2 sm:min-h-0"
            >
              <Search aria-hidden="true" className="h-4 w-4 shrink-0" />
              Search
            </TabsTrigger>
            <TabsTrigger
              value="realtime"
              className="flex min-h-[44px] items-center gap-2 sm:min-h-0"
            >
              <Activity aria-hidden="true" className="h-4 w-4 shrink-0" />
              Real-time
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            <AnalyticsOverview
              data={data.overview}
              loading={loading}
              onRefresh={handleRefresh}
              onExport={handleExport}
              onMetricClick={handleMetricClick}
            />

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <AnalyticsChart
                title="Page views trend"
                description="Daily page views over the last 30 days"
                data={data.chartData}
                dataKeys={['pageViews', 'uniqueVisitors']}
                labels={{
                  pageViews: 'Page views',
                  uniqueVisitors: 'Unique visitors',
                }}
                height={300}
              />

              <AnalyticsChart
                title="User activity"
                description="Document uploads and search activity"
                data={data.chartData}
                type="bar"
                dataKeys={['documentsUploaded', 'searchesPerformed']}
                labels={{
                  documentsUploaded: 'Documents',
                  searchesPerformed: 'Searches',
                }}
                height={300}
              />
            </div>
          </TabsContent>

          {/* Documents Tab */}
          <TabsContent value="documents" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <AnalyticsTable
                  title="Document analytics"
                  description="Your most recent document uploads and their processing status"
                  data={data.documents}
                  columns={documentTableConfig.columns}
                  loading={loading}
                />
              </div>

              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base font-medium">
                      File type distribution
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {data.fileTypeDistribution.length > 0 ? (
                      <AnalyticsChart
                        title="File types"
                        data={data.fileTypeDistribution}
                        type="pie"
                        height={250}
                        showLegend={true}
                        showGrid={false}
                      />
                    ) : (
                      <div className="flex h-[250px] items-center justify-center text-center text-muted-foreground">
                        <p className="text-sm">
                          No documents indexed yet. Upload a document to see the
                          breakdown here.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base font-medium">
                      Processing status
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {data.processingStats.length > 0 ? (
                      data.processingStats.map((item: any) => (
                        <div
                          key={item.status}
                          className="flex items-center justify-between"
                        >
                          <div className="flex items-center gap-2">
                            <item.icon
                              aria-hidden="true"
                              className={cn('h-4 w-4', item.color)}
                            />
                            <span className="text-sm font-medium text-foreground">
                              {item.status}
                            </span>
                          </div>
                          <Badge variant="secondary">{item.count}</Badge>
                        </div>
                      ))
                    ) : (
                      <div className="flex items-center justify-center py-4 text-muted-foreground">
                        <p className="text-sm">No processing data yet.</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Search Tab */}
          <TabsContent value="search" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <AnalyticsTable
                  title="Search analytics"
                  description="Your most popular search queries and how they performed"
                  data={data.searches}
                  columns={searchTableConfig.columns}
                  loading={loading}
                />
              </div>

              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base font-medium">
                      Search types
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {data.searchTypes && data.searchTypes.length > 0 ? (
                      <AnalyticsChart
                        title="Search types"
                        data={data.searchTypes}
                        type="donut"
                        height={250}
                        showLegend={true}
                        showGrid={false}
                      />
                    ) : (
                      <div className="flex h-[250px] items-center justify-center text-center text-muted-foreground">
                        <p className="text-sm">
                          No search data yet. Run a few searches to see how they
                          break down.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base font-medium">
                      <TrendingUp
                        aria-hidden="true"
                        className="h-4 w-4 text-primary"
                      />
                      Search quality
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      Result relevance and click-through metrics appear here
                      once enough queries have run to measure them reliably.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Real-time Tab */}
          <TabsContent value="realtime" className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  label: 'Active users',
                  value:
                    data.realtimeMetrics?.activeUsers ||
                    data.overview?.activeUsers ||
                    0,
                  icon: Users,
                },
                {
                  label: 'Current searches',
                  value: data.realtimeMetrics?.currentSearches || 0,
                  icon: Search,
                },
                {
                  label: 'Processing files',
                  value: data.realtimeMetrics?.processingFiles || 0,
                  icon: FileText,
                },
                {
                  label: 'Requests / min',
                  value: data.realtimeMetrics?.requestsPerMinute || 0,
                  icon: Activity,
                },
              ].map((metric) => (
                <Card key={metric.label}>
                  <CardContent className="p-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-primary">
                      <metric.icon aria-hidden="true" className="h-4 w-4" />
                    </div>
                    <p className="mt-4 text-2xl font-semibold tabular-nums text-foreground">
                      {metric.value.toLocaleString()}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {metric.label}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base font-medium">
                  Activity feed
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px] pr-4">
                  <div className="flex h-[360px] flex-col items-center justify-center gap-2 text-center">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                      <Activity aria-hidden="true" className="h-5 w-5" />
                    </div>
                    <p className="text-sm font-medium text-foreground">
                      No recent activity
                    </p>
                    <p className="max-w-xs text-sm text-muted-foreground">
                      Uploads, searches, and conversations will appear here as
                      they happen across your workspace.
                    </p>
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </MotionConfig>
  );
}

export default AnalyticsDashboard;
