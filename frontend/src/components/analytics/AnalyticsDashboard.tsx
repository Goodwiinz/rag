'use client';

import { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AnalyticsOverview } from './AnalyticsOverview';
import { AnalyticsChart } from './AnalyticsChart';
import { AnalyticsTable, createDocumentAnalyticsTable, createSearchAnalyticsTable } from './AnalyticsTable';
import {
  BarChart3,
  LineChart,
  PieChart,
  FileText,
  Search,
  MessageSquare,
  Users,
  Activity,
  Download,
  RefreshCw,
  Filter,
  Calendar,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface AnalyticsDashboardProps {
  className?: string;
}

// Mock data generation
const generateMockData = () => {
  const now = new Date();
  const data = [];

  for (let i = 29; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    data.push({
      date: date.toISOString().split('T')[0],
      pageViews: Math.floor(Math.random() * 1000) + 500,
      uniqueVisitors: Math.floor(Math.random() * 200) + 100,
      documentsUploaded: Math.floor(Math.random() * 50) + 10,
      searchesPerformed: Math.floor(Math.random() * 300) + 100,
      chatsInitiated: Math.floor(Math.random() * 100) + 20,
    });
  }

  return data;
};

const generateDocumentTableData = () => {
  const documents = [];
  const fileTypes = ['pdf', 'txt', 'jpg', 'png', 'mp3', 'mp4'];
  const statuses = ['completed', 'processing', 'failed', 'pending'];

  for (let i = 0; i < 25; i++) {
    documents.push({
      id: `doc_${i + 1}`,
      filename: `Document_${i + 1}.${fileTypes[Math.floor(Math.random() * fileTypes.length)]}`,
      type: fileTypes[Math.floor(Math.random() * fileTypes.length)],
      size: Math.floor(Math.random() * 10000000) + 100000,
      uploadedAt: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
      status: statuses[Math.floor(Math.random() * statuses.length)],
    });
  }

  return documents;
};

const generateSearchTableData = () => {
  const searches = [];
  const queries = [
    'machine learning basics',
    'how to implement RAG',
    'neural network architecture',
    'data preprocessing',
    'model evaluation metrics',
    'transfer learning',
    'attention mechanisms',
    'BERT model explanation',
    'vector databases',
    'semantic search',
  ];

  for (let i = 0; i < 15; i++) {
    const query = queries[Math.floor(Math.random() * queries.length)];
    searches.push({
      id: `search_${i + 1}`,
      query,
      type: ['semantic', 'keyword', 'hybrid'][Math.floor(Math.random() * 3)],
      results: Math.floor(Math.random() * 20) + 1,
      clickRate: Math.random(),
      lastSearched: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000).toISOString(),
    });
  }

  return searches;
};

export function AnalyticsDashboard({ className }: AnalyticsDashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>({
    overview: null,
    documents: [],
    searches: [],
  });

  // Load mock data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);

      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));

      const chartData = generateMockData();
      const documentTableData = generateDocumentTableData();
      const searchTableData = generateSearchTableData();

      setData({
        overview: {
          totalUsers: 1247,
          activeUsers: 234,
          totalSessions: 5678,
          totalPageViews: chartData.reduce((sum, d) => sum + d.pageViews, 0),
          averageSessionDuration: 3.5,
          bounceRate: 42.3,
          documentsUploaded: documentTableData.filter(d => d.status === 'completed').length,
          searchesPerformed: chartData.reduce((sum, d) => sum + d.searchesPerformed, 0),
          chatsInitiated: chartData.reduce((sum, d) => sum + d.chatsInitiated, 0),
          errorRate: 1.2,
        },
        chartData,
        documents: documentTableData,
        searches: searchTableData,
      });

      setLoading(false);
    };

    loadData();
  }, []);

  const handleRefresh = () => {
    setLoading(true);
    // Simulate refresh
    setTimeout(() => {
      loadData();
    }, 500);
  };

  const handleExport = (format: 'csv' | 'json') => {
    console.log(`Exporting analytics data as ${format}`);
    // Implementation would go here
  };

  const handleMetricClick = (metric: string) => {
    console.log(`Metric clicked: ${metric}`);
    // Implementation would go here
  };

  const documentTableConfig = useMemo(() => createDocumentAnalyticsTable(), []);
  const searchTableConfig = useMemo(() => createSearchAnalyticsTable(), []);

  if (loading && !data.overview) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-2">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('w-full space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analytics Dashboard</h1>
          <p className="text-muted-foreground">
            Comprehensive insights into your RAG system performance
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport('csv')}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Quick Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 border-amber-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Users className="h-8 w-8 text-amber-500" />
              <div>
                <p className="text-2xl font-bold">{data.overview?.totalUsers}</p>
                <p className="text-sm text-muted-foreground">Total Users</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border-blue-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{data.overview?.documentsUploaded}</p>
                <p className="text-sm text-muted-foreground">Documents</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-500/10 to-pink-500/10 border-purple-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Search className="h-8 w-8 text-purple-500" />
              <div>
                <p className="text-2xl font-bold">{data.overview?.searchesPerformed}</p>
                <p className="text-sm text-muted-foreground">Searches</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 border-green-500/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <MessageSquare className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{data.overview?.chatsInitiated}</p>
                <p className="text-sm text-muted-foreground">AI Chats</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="documents" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Documents
          </TabsTrigger>
          <TabsTrigger value="search" className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            Search
          </TabsTrigger>
          <TabsTrigger value="realtime" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Real-time
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <AnalyticsOverview
            data={data.overview}
            loading={loading}
            onRefresh={handleRefresh}
            onExport={() => handleExport('csv')}
            onMetricClick={handleMetricClick}
          />

          {/* Charts Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AnalyticsChart
              title="Page Views Trend"
              description="Daily page views over the last 30 days"
              data={data.chartData}
              dataKeys={['pageViews', 'uniqueVisitors']}
              labels={{
                pageViews: 'Page Views',
                uniqueVisitors: 'Unique Visitors',
              }}
              height={300}
            />

            <AnalyticsChart
              title="User Activity"
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
                title="Document Analytics"
                description="Recent document uploads and their processing status"
                data={data.documents}
                columns={documentTableConfig.columns}
                loading={loading}
                pagination={{
                  page: 1,
                  pageSize: 10,
                  total: data.documents.length,
                  onPageChange: () => {},
                  onPageSizeChange: () => {},
                }}
                search={{
                  placeholder: 'Search documents...',
                  onSearch: () => {},
                }}
                filters={{
                  options: [
                    { value: 'pdf', label: 'PDF' },
                    { value: 'txt', label: 'Text' },
                    { value: 'jpg', label: 'Image' },
                  ],
                  onFilter: () => {},
                }}
              />
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">File Type Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <AnalyticsChart
                    data={[
                      { name: 'PDF', value: 45 },
                      { name: 'Text', value: 25 },
                      { name: 'Images', value: 20 },
                      { name: 'Video', value: 10 },
                    ]}
                    type="pie"
                    height={250}
                    showLegend={true}
                    showGrid={false}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Processing Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {[
                    { status: 'Completed', count: 124, icon: CheckCircle, color: 'text-emerald-500' },
                    { status: 'Processing', count: 8, icon: Clock, color: 'text-blue-500' },
                    { status: 'Failed', count: 3, icon: AlertTriangle, color: 'text-rose-500' },
                    { status: 'Pending', count: 15, icon: Clock, color: 'text-muted-foreground' },
                  ].map((item) => (
                    <div key={item.status} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <item.icon className={cn('h-4 w-4', item.color)} />
                        <span className="text-sm font-medium">{item.status}</span>
                      </div>
                      <Badge variant="secondary">{item.count}</Badge>
                    </div>
                  ))}
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
                title="Search Analytics"
                description="Popular search queries and their performance"
                data={data.searches}
                columns={searchTableConfig.columns}
                loading={loading}
                pagination={{
                  page: 1,
                  pageSize: 10,
                  total: data.searches.length,
                  onPageChange: () => {},
                  onPageSizeChange: () => {},
                }}
                search={{
                  placeholder: 'Search queries...',
                  onSearch: () => {},
                }}
                filters={{
                  options: [
                    { value: 'semantic', label: 'Semantic Search' },
                    { value: 'keyword', label: 'Keyword Search' },
                    { value: 'hybrid', label: 'Hybrid Search' },
                  ],
                  onFilter: () => {},
                }}
              />
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Search Types</CardTitle>
                </CardHeader>
                <CardContent>
                  <AnalyticsChart
                    data={[
                      { name: 'Semantic', value: 45 },
                      { name: 'Keyword', value: 30 },
                      { name: 'Hybrid', value: 25 },
                    ]}
                    type="donut"
                    height={250}
                    showLegend={true}
                    showGrid={false}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Top Insights
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                    <p className="text-sm font-medium text-blue-900">
                      Most searches return results
                    </p>
                    <p className="text-xs text-blue-700">
                      87% of searches find relevant documents
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                    <p className="text-sm font-medium text-green-900">
                      High click-through rate
                    </p>
                    <p className="text-xs text-green-700">
                      Average CTR of 42% above industry standard
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* Real-time Tab */}
        <TabsContent value="realtime" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Active Users', value: '42', change: '+12%', icon: Users },
              { label: 'Current Searches', value: '8', change: '+3', icon: Search },
              { label: 'Processing Files', value: '3', change: '-1', icon: FileText },
              { label: 'API Requests/min', value: '156', change: '+24', icon: Activity },
            ].map((metric) => (
              <Card key={metric.label}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <metric.icon className="h-8 w-8 text-muted-foreground" />
                    <Badge variant="secondary">{metric.change}</Badge>
                  </div>
                  <p className="text-2xl font-bold mt-2">{metric.value}</p>
                  <p className="text-sm text-muted-foreground">{metric.label}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Live Activity Feed</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px] pr-4">
                <div className="space-y-3">
                  {[
                    { action: 'User logged in', user: 'john@example.com', time: '2 seconds ago' },
                    { action: 'Document uploaded', user: 'sarah@example.com', time: '15 seconds ago' },
                    { action: 'Search performed', user: 'mike@example.com', time: '32 seconds ago' },
                    { action: 'Chat session started', user: 'emma@example.com', time: '1 minute ago' },
                    { action: 'Document processed', user: 'alex@example.com', time: '2 minutes ago' },
                  ].map((activity, index) => (
                    <div key={index} className="flex items-center justify-between p-3 rounded-lg border">
                      <div>
                        <p className="text-sm font-medium">{activity.action}</p>
                        <p className="text-xs text-muted-foreground">{activity.user}</p>
                      </div>
                      <span className="text-xs text-muted-foreground">{activity.time}</span>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default AnalyticsDashboard;