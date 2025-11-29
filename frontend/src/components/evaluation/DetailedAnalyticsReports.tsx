import React, { useState, useMemo, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  ScatterChart,
  Scatter,
  Treemap,
  FunnelChart,
  Funnel,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';
import {
  FileText,
  Download,
  Calendar,
  TrendingUp,
  TrendingDown,
  Users,
  Clock,
  BarChart3,
  PieChart as PieChartIcon,
  Filter,
  RefreshCw,
  Eye,
  Settings,
  Share2,
  Printer,
  Mail,
  ChevronDown,
  ChevronUp,
  Info,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Zap,
  Brain,
  Target,
  Database,
  Activity,
  Globe,
  Search,
  File,
  Image,
  Music,
  Video,
} from 'lucide-react';

// Types
export interface ReportConfig {
  id: string;
  name: string;
  description: string;
  category: 'performance' | 'usage' | 'quality' | 'compliance' | 'custom';
  timeRange: '1d' | '7d' | '30d' | '90d' | '1y' | 'custom';
  filters: {
    users?: string[];
    documentTypes?: string[];
    queryTypes?: string[];
    departments?: string[];
  };
  metrics: string[];
  visualizations: string[];
  format: 'html' | 'pdf' | 'excel' | 'csv';
  schedule?: {
    enabled: boolean;
    frequency: 'daily' | 'weekly' | 'monthly';
    recipients: string[];
  };
  created: string;
  updated: string;
  createdBy: string;
}

interface AnalyticsData {
  timeRange: {
    start: string;
    end: string;
  };
  overview: {
    totalQueries: number;
    uniqueUsers: number;
    documentsProcessed: number;
    averageLatency: number;
    successRate: number;
    userSatisfaction: number;
  };
  performance: {
    latencyTrends: Array<{
      date: string;
      avgLatency: number;
      p50Latency: number;
      p95Latency: number;
      p99Latency: number;
    }>;
    throughputTrends: Array<{
      date: string;
      queriesPerMinute: number;
      documentsPerHour: number;
    }>;
    errorRates: Array<{
      date: string;
      errorRate: number;
      errorType: string;
      count: number;
    }>;
  };
  usage: {
    queryPatterns: Array<{
      hour: number;
      queryCount: number;
      uniqueUsers: number;
    }>;
    modalityDistribution: Array<{
      modality: string;
      count: number;
      percentage: number;
    }>;
    fileTypeDistribution: Array<{
      fileType: string;
      count: number;
      sizeMB: number;
    }>;
    userActivity: Array<{
      userId: string;
      userName: string;
      queryCount: number;
      documentsUploaded: number;
      lastActive: string;
    }>;
  };
  quality: {
    ragTriadMetrics: Array<{
      date: string;
      answerRelevancy: number;
      faithfulness: number;
      contextualRelevancy: number;
    }>;
    qualityScores: Array<{
      metric: string;
      current: number;
      target: number;
      trend: 'up' | 'down' | 'stable';
      status: 'good' | 'warning' | 'critical';
    }>;
    hallucinationAnalysis: Array<{
      date: string;
      hallucinationScore: number;
      detectedCount: number;
      correctedCount: number;
    }>;
  };
  compliance: {
    securityMetrics: Array<{
      metric: string;
      value: number;
      threshold: number;
      status: 'compliant' | 'warning' | 'violation';
    }>;
    auditLogs: Array<{
      date: string;
      actionType: string;
      userId: string;
      result: 'success' | 'failure';
      risk: 'low' | 'medium' | 'high';
    }>;
  };
}

// Mock data generation
const generateMockAnalyticsData = (timeRange: string): AnalyticsData => {
  const days = timeRange === '1d' ? 1 : timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 365;
  const now = new Date();

  return {
    timeRange: {
      start: new Date(now.getTime() - days * 24 * 60 * 60 * 1000).toISOString(),
      end: now.toISOString(),
    },
    overview: {
      totalQueries: Math.floor(Math.random() * 10000) + 5000,
      uniqueUsers: Math.floor(Math.random() * 500) + 100,
      documentsProcessed: Math.floor(Math.random() * 2000) + 500,
      averageLatency: Math.random() * 1000 + 800,
      successRate: Math.random() * 10 + 85,
      userSatisfaction: Math.random() * 20 + 75,
    },
    performance: {
      latencyTrends: Array.from({ length: Math.min(days, 30) }, (_, i) => {
        const date = new Date(now.getTime() - (days - i) * 24 * 60 * 60 * 1000);
        return {
          date: date.toLocaleDateString(),
          avgLatency: Math.random() * 500 + 1000,
          p50Latency: Math.random() * 300 + 800,
          p95Latency: Math.random() * 800 + 1500,
          p99Latency: Math.random() * 1200 + 2000,
        };
      }),
      throughputTrends: Array.from({ length: Math.min(days, 30) }, (_, i) => {
        const date = new Date(now.getTime() - (days - i) * 24 * 60 * 60 * 1000);
        return {
          date: date.toLocaleDateString(),
          queriesPerMinute: Math.floor(Math.random() * 100) + 20,
          documentsPerHour: Math.floor(Math.random() * 50) + 10,
        };
      }),
      errorRates: Array.from({ length: Math.min(days, 30) }, (_, i): {
        date: string;
        errorRate: number;
        errorType: string;
        count: number;
      } => {
        const date = new Date(now.getTime() - (days - i) * 24 * 60 * 60 * 1000);
        const errorTypes: string[] = ['timeout', 'validation', 'processing', 'network'];
        return {
          date: date.toLocaleDateString(),
          errorRate: Math.random() * 5 + 1,
          errorType: errorTypes[Math.floor(Math.random() * errorTypes.length)] || 'timeout',
          count: Math.floor(Math.random() * 20) + 1,
        };
      }),
    },
    usage: {
      queryPatterns: Array.from({ length: 24 }, (_, i) => ({
        hour: i,
        queryCount: Math.floor(Math.random() * 500) + 50,
        uniqueUsers: Math.floor(Math.random() * 50) + 5,
      })),
      modalityDistribution: (() => {
        const items = [
          { modality: 'Text', count: Math.floor(Math.random() * 5000) + 3000, percentage: 0 },
          { modality: 'Image', count: Math.floor(Math.random() * 2000) + 1000, percentage: 0 },
          { modality: 'Audio', count: Math.floor(Math.random() * 1000) + 500, percentage: 0 },
          { modality: 'Video', count: Math.floor(Math.random() * 800) + 200, percentage: 0 },
        ];
        const total = items.reduce((sum, item) => sum + item.count, 0);
        return items.map(item => ({
          ...item,
          percentage: total > 0 ? (item.count / total) * 100 : 0,
        }));
      })(),
      fileTypeDistribution: [
        { fileType: 'PDF', count: Math.floor(Math.random() * 1000) + 500, sizeMB: Math.floor(Math.random() * 5000) + 2000 },
        { fileType: 'TXT', count: Math.floor(Math.random() * 500) + 200, sizeMB: Math.floor(Math.random() * 500) + 100 },
        { fileType: 'JPG', count: Math.floor(Math.random() * 800) + 300, sizeMB: Math.floor(Math.random() * 2000) + 500 },
        { fileType: 'PNG', count: Math.floor(Math.random() * 600) + 200, sizeMB: Math.floor(Math.random() * 1500) + 300 },
        { fileType: 'MP3', count: Math.floor(Math.random() * 200) + 50, sizeMB: Math.floor(Math.random() * 3000) + 1000 },
        { fileType: 'MP4', count: Math.floor(Math.random() * 150) + 30, sizeMB: Math.floor(Math.random() * 8000) + 2000 },
      ],
      userActivity: Array.from({ length: 10 }, (_, i) => ({
        userId: `user-${i + 1}`,
        userName: `User ${i + 1}`,
        queryCount: Math.floor(Math.random() * 100) + 10,
        documentsUploaded: Math.floor(Math.random() * 50) + 5,
        lastActive: new Date(now.getTime() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
      })),
    },
    quality: {
      ragTriadMetrics: Array.from({ length: Math.min(days, 30) }, (_, i) => {
        const date = new Date(now.getTime() - (days - i) * 24 * 60 * 60 * 1000);
        return {
          date: date.toLocaleDateString(),
          answerRelevancy: Math.random() * 20 + 70,
          faithfulness: Math.random() * 15 + 85,
          contextualRelevancy: Math.random() * 25 + 65,
        };
      }),
      qualityScores: [
        { metric: 'Answer Relevancy', current: 78.5, target: 70, trend: 'up' as const, status: 'good' as const },
        { metric: 'Faithfulness', current: 92.3, target: 90, trend: 'stable' as const, status: 'good' as const },
        { metric: 'Contextual Relevancy', current: 85.2, target: 70, trend: 'up' as const, status: 'good' as const },
        { metric: 'Response Latency', current: 1450, target: 2000, trend: 'down' as const, status: 'good' as const },
        { metric: 'Success Rate', current: 91.8, target: 90, trend: 'stable' as const, status: 'good' as const },
      ],
      hallucinationAnalysis: Array.from({ length: Math.min(days, 30) }, (_, i) => {
        const date = new Date(now.getTime() - (days - i) * 24 * 60 * 60 * 1000);
        return {
          date: date.toLocaleDateString(),
          hallucinationScore: Math.random() * 10 + 5,
          detectedCount: Math.floor(Math.random() * 10) + 1,
          correctedCount: Math.floor(Math.random() * 8) + 1,
        };
      }),
    },
    compliance: {
      securityMetrics: [
        { metric: 'Failed Login Attempts', value: 3, threshold: 10, status: 'compliant' as const },
        { metric: 'Data Access Violations', value: 0, threshold: 0, status: 'compliant' as const },
        { metric: 'Unauthorized API Calls', value: 1, threshold: 5, status: 'compliant' as const },
        { metric: 'Suspicious Activity Score', value: 2.5, threshold: 5.0, status: 'compliant' as const },
      ],
      auditLogs: Array.from({ length: 50 }, (_, i): {
        date: string;
        actionType: string;
        userId: string;
        result: 'success' | 'failure';
        risk: 'low' | 'medium' | 'high';
      } => {
        const actionTypes: string[] = ['login', 'document_upload', 'query', 'download', 'settings_change'];
        const riskLevels: ('low' | 'medium' | 'high')[] = ['low', 'medium', 'high'];
        return {
          date: new Date(now.getTime() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
          actionType: actionTypes[Math.floor(Math.random() * actionTypes.length)] || 'login',
          userId: `user-${Math.floor(Math.random() * 10) + 1}`,
          result: Math.random() > 0.1 ? 'success' as const : 'failure' as const,
          risk: riskLevels[Math.floor(Math.random() * riskLevels.length)] || 'low',
        };
      }),
    },
  };
};

const reportTemplates: ReportConfig[] = [
  {
    id: 'perf-weekly',
    name: 'Weekly Performance Report',
    description: 'Comprehensive performance metrics for the past week',
    category: 'performance',
    timeRange: '7d',
    filters: {},
    metrics: ['latency', 'throughput', 'errorRate', 'successRate'],
    visualizations: ['line', 'bar', 'area'],
    format: 'html',
    created: '2025-10-01T00:00:00Z',
    updated: '2025-10-15T12:00:00Z',
    createdBy: 'system',
  },
  {
    id: 'usage-monthly',
    name: 'Monthly Usage Analytics',
    description: 'User behavior and system usage patterns',
    category: 'usage',
    timeRange: '30d',
    filters: {},
    metrics: ['userActivity', 'queryPatterns', 'modalityDistribution', 'fileTypeDistribution'],
    visualizations: ['pie', 'bar', 'heatmap'],
    format: 'pdf',
    schedule: {
      enabled: true,
      frequency: 'monthly',
      recipients: ['admin@company.com'],
    },
    created: '2025-10-01T00:00:00Z',
    updated: '2025-10-15T12:00:00Z',
    createdBy: 'admin',
  },
  {
    id: 'quality-quarterly',
    name: 'Quarterly Quality Assessment',
    description: 'Deep dive into RAG quality and accuracy metrics',
    category: 'quality',
    timeRange: '90d',
    filters: {},
    metrics: ['ragTriad', 'hallucinationAnalysis', 'userFeedback'],
    visualizations: ['radar', 'line', 'scatter'],
    format: 'excel',
    schedule: {
      enabled: true,
      frequency: 'monthly',
      recipients: ['qa-team@company.com', 'management@company.com'],
    },
    created: '2025-10-01T00:00:00Z',
    updated: '2025-10-15T12:00:00Z',
    createdBy: 'qa-lead',
  },
];

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

const DetailedAnalyticsReports: React.FC<DetailedAnalyticsReportsProps> = ({
  onExportReport,
  onScheduleReport,
  onShareReport,
  className,
}) => {
  const [selectedTimeRange, setSelectedTimeRange] = useState('30d');
  const [selectedReport, setSelectedReport] = useState<ReportConfig | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData>(() => generateMockAnalyticsData(selectedTimeRange));
  const [activeTab, setActiveTab] = useState('overview');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['overview', 'performance']));

  // Update analytics data when time range changes
  React.useEffect(() => {
    setIsLoading(true);
    const timeoutId = setTimeout(() => {
      setAnalyticsData(generateMockAnalyticsData(selectedTimeRange));
      setIsLoading(false);
    }, 1000);

    return () => clearTimeout(timeoutId);
  }, [selectedTimeRange]);

  // Toggle section expansion
  const toggleSection = useCallback((section: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(section)) {
        newSet.delete(section);
      } else {
        newSet.add(section);
      }
      return newSet;
    });
  }, []);

  // Export report
  const exportReport = useCallback((format: string) => {
    const report = {
      timeRange: selectedTimeRange,
      data: analyticsData,
      reportConfig: selectedReport,
      generatedAt: new Date().toISOString(),
      format,
    };

    onExportReport?.(report);
  }, [selectedTimeRange, analyticsData, selectedReport, onExportReport]);

  // Get modality icon
  const getModalityIcon = (modality: string) => {
    switch (modality.toLowerCase()) {
      case 'text': return <FileText className="h-4 w-4" />;
      case 'image': return <Image className="h-4 w-4" />;
      case 'audio': return <Music className="h-4 w-4" />;
      case 'video': return <Video className="h-4 w-4" />;
      default: return <File className="h-4 w-4" />;
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good':
      case 'compliant':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'critical':
      case 'violation':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Info className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics Reports</h2>
          <p className="text-gray-600 dark:text-gray-400">Comprehensive analytics and reporting for your RAG system</p>
        </div>
        <div className="flex items-center space-x-2">
          <Select value={selectedTimeRange} onValueChange={setSelectedTimeRange}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1d">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
              <SelectItem value="1y">Last year</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAnalyticsData(generateMockAnalyticsData(selectedTimeRange))}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => exportReport('html')}
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Report Templates */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <FileText className="h-5 w-5 mr-2" />
            Report Templates
          </CardTitle>
          <CardDescription>Pre-configured reports for different analytics needs</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {reportTemplates.map(template => (
              <div
                key={template.id}
                className={`border rounded-lg p-4 cursor-pointer transition-all hover:shadow-md ${
                  selectedReport?.id === template.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : ''
                }`}
                onClick={() => setSelectedReport(template)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <Badge variant={template.category === 'performance' ? 'default' :
                                   template.category === 'usage' ? 'secondary' :
                                   template.category === 'quality' ? 'outline' : 'destructive'}>
                      {template.category}
                    </Badge>
                    {template.schedule?.enabled && (
                      <Badge variant="outline" className="text-xs">
                        <Clock className="h-3 w-3 mr-1" />
                        Scheduled
                      </Badge>
                    )}
                  </div>
                </div>
                <h4 className="font-medium mb-1">{template.name}</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">{template.description}</p>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Time range: {template.timeRange}</span>
                  <span>Format: {template.format.toUpperCase()}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Analytics Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center">
              <BarChart3 className="h-5 w-5 mr-2" />
              Analytics Overview
            </CardTitle>
            <div className="text-sm text-gray-500">
              {new Date(analyticsData.timeRange.start).toLocaleDateString()} - {new Date(analyticsData.timeRange.end).toLocaleDateString()}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
            <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {analyticsData.overview.totalQueries.toLocaleString()}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Total Queries</div>
            </div>
            <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {analyticsData.overview.uniqueUsers}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Unique Users</div>
            </div>
            <div className="text-center p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {analyticsData.overview.documentsProcessed}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Documents</div>
            </div>
            <div className="text-center p-4 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                {analyticsData.overview.averageLatency.toFixed(0)}ms
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Avg Latency</div>
            </div>
            <div className="text-center p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg">
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {analyticsData.overview.successRate.toFixed(1)}%
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Success Rate</div>
            </div>
            <div className="text-center p-4 bg-pink-50 dark:bg-pink-900/20 rounded-lg">
              <div className="text-2xl font-bold text-pink-600 dark:text-pink-400">
                {analyticsData.overview.userSatisfaction.toFixed(1)}%
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Satisfaction</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Analytics Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="usage">Usage</TabsTrigger>
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Overview</CardTitle>
              <CardDescription>High-level summary of your RAG system analytics</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                This dashboard provides comprehensive analytics across performance, usage, quality, and compliance metrics.
                Select a category above to dive deeper into specific analytics, or choose a pre-configured report template to get started.
              </p>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Activity className="h-4 w-4 text-blue-500" />
                    <span className="font-medium">Performance</span>
                  </div>
                  <span className="text-sm text-gray-500">Latency, throughput, and error rate metrics</span>
                </div>
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Users className="h-4 w-4 text-green-500" />
                    <span className="font-medium">Usage</span>
                  </div>
                  <span className="text-sm text-gray-500">Query patterns and user activity analysis</span>
                </div>
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <Target className="h-4 w-4 text-purple-500" />
                    <span className="font-medium">Quality</span>
                  </div>
                  <span className="text-sm text-gray-500">RAG Triad metrics and hallucination detection</span>
                </div>
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-orange-500" />
                    <span className="font-medium">Compliance</span>
                  </div>
                  <span className="text-sm text-gray-500">Security metrics and audit logs</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Latency Trends</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleSection('latency')}
                >
                  {expandedSections.has('latency') ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </Button>
              </div>
            </CardHeader>
            {expandedSections.has('latency') && (
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={analyticsData.performance.latencyTrends}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="avgLatency" stroke="#3b82f6" strokeWidth={2} name="Average" />
                      <Line type="monotone" dataKey="p95Latency" stroke="#f59e0b" strokeWidth={2} name="95th Percentile" />
                      <Line type="monotone" dataKey="p99Latency" stroke="#ef4444" strokeWidth={2} name="99th Percentile" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            )}
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Throughput Analysis</CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleSection('throughput')}
                >
                  {expandedSections.has('throughput') ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </Button>
              </div>
            </CardHeader>
            {expandedSections.has('throughput') && (
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={analyticsData.performance.throughputTrends}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Bar yAxisId="left" dataKey="documentsPerHour" fill="#10b981" name="Documents/Hour" />
                      <Line yAxisId="right" type="monotone" dataKey="queriesPerMinute" stroke="#3b82f6" strokeWidth={2} name="Queries/Minute" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            )}
          </Card>
        </TabsContent>

        {/* Usage Tab */}
        <TabsContent value="usage" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Query Patterns by Hour</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={analyticsData.usage.queryPatterns}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="hour" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Area type="monotone" dataKey="queryCount" stroke="#3b82f6" fill="#3b82f620" name="Query Count" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Modality Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={analyticsData.usage.modalityDistribution}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ modality, percentage }) => `${modality}: ${percentage.toFixed(1)}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="count"
                      >
                        {analyticsData.usage.modalityDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>File Type Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analyticsData.usage.fileTypeDistribution}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="fileType" tick={{ fontSize: 12 }} />
                    <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Bar yAxisId="left" dataKey="count" fill="#3b82f6" name="File Count" />
                    <Bar yAxisId="right" dataKey="sizeMB" fill="#10b981" name="Size (MB)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Top Users by Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analyticsData.usage.userActivity.slice(0, 5).map((user, index) => (
                  <div key={user.userId} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center">
                        <span className="text-sm font-medium">#{index + 1}</span>
                      </div>
                      <div>
                        <div className="font-medium">{user.userName}</div>
                        <div className="text-sm text-gray-500">
                          Last active: {new Date(user.lastActive).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">{user.queryCount} queries</div>
                      <div className="text-sm text-gray-500">{user.documentsUploaded} docs</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Quality Tab */}
        <TabsContent value="quality" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>RAG Triad Metrics</CardTitle>
              <CardDescription>Core quality metrics for Retrieval-Augmented Generation</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analyticsData.quality.ragTriadMetrics}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="answerRelevancy" stroke="#3b82f6" strokeWidth={2} name="Answer Relevancy" />
                    <Line type="monotone" dataKey="faithfulness" stroke="#10b981" strokeWidth={2} name="Faithfulness" />
                    <Line type="monotone" dataKey="contextualRelevancy" stroke="#f59e0b" strokeWidth={2} name="Contextual Relevancy" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quality Scores Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {analyticsData.quality.qualityScores.map(score => (
                  <div key={score.metric} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(score.status)}
                      <div>
                        <div className="font-medium">{score.metric}</div>
                        <div className="text-sm text-gray-500">Target: {score.target}</div>
                      </div>
                    </div>
                    <div className="flex items-center space-x-4">
                      <div className="text-right">
                        <div className="font-bold text-lg">{score.current.toFixed(1)}</div>
                        <div className="flex items-center space-x-1 text-sm">
                          {score.trend === 'up' ? <TrendingUp className="h-3 w-3 text-green-500" /> :
                           score.trend === 'down' ? <TrendingDown className="h-3 w-3 text-red-500" /> :
                           <div className="w-3 h-3 bg-gray-300 rounded-full" />}
                          <span>{score.trend}</span>
                        </div>
                      </div>
                      <div className="w-24">
                        <Progress value={(score.current / score.target) * 100} className="h-2" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Hallucination Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={analyticsData.quality.hallucinationAnalysis}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Line yAxisId="left" type="monotone" dataKey="hallucinationScore" stroke="#ef4444" strokeWidth={2} name="Hallucination Score" />
                    <Bar yAxisId="right" dataKey="detectedCount" fill="#f59e0b" name="Detected" />
                    <Bar yAxisId="right" dataKey="correctedCount" fill="#10b981" name="Corrected" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Compliance Tab */}
        <TabsContent value="compliance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Security Compliance Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {analyticsData.compliance.securityMetrics.map(metric => (
                  <div key={metric.metric} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(metric.status)}
                      <div>
                        <div className="font-medium">{metric.metric}</div>
                        <div className="text-sm text-gray-500">Threshold: {metric.threshold}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-lg">{metric.value}</div>
                      <Badge variant={metric.status === 'compliant' ? 'default' :
                                     metric.status === 'warning' ? 'secondary' : 'destructive'}>
                        {metric.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Audit Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {analyticsData.compliance.auditLogs.slice(0, 10).map((log, index) => (
                  <div key={index} className="flex items-center justify-between p-3 border rounded">
                    <div className="flex items-center space-x-3">
                      <Badge variant={log.result === 'success' ? 'default' : 'destructive'}>
                        {log.result}
                      </Badge>
                      <div>
                        <div className="font-medium">{log.actionType.replace('_', ' ')}</div>
                        <div className="text-sm text-gray-500">
                          {log.userId} • {new Date(log.date).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <Badge variant={log.risk === 'low' ? 'secondary' :
                                   log.risk === 'medium' ? 'default' : 'destructive'}>
                      {log.risk}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export interface ReportExport {
  timeRange: string;
  data: AnalyticsData;
  reportConfig: ReportConfig | null;
  generatedAt: string;
  format: string;
}

interface DetailedAnalyticsReportsProps {
  onExportReport?: (report: ReportExport) => void;
  onScheduleReport?: (config: ReportConfig) => void;
  onShareReport?: (report: ReportExport) => void;
  className?: string;
}

export default DetailedAnalyticsReports;