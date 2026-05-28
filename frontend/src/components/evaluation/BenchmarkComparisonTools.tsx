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
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Scatter,
  ScatterChart,
  Cell,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Award,
  Target,
  BarChart3,
  Users,
  Clock,
  Zap,
  Brain,
  Eye,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Download,
  RefreshCw,
  Filter,
  Info,
  ChevronUp,
  ChevronDown,
  ChevronRight,
  Settings,
  Star,
  Globe,
  Database,
  Cpu,
} from 'lucide-react';

// Types
interface BenchmarkCategory {
  id: string;
  name: string;
  description: string;
  metrics: string[];
  weight: number;
}

interface BenchmarkData {
  id: string;
  name: string;
  category: string;
  description: string;
  source: string;
  date: string;
  metrics: {
    [key: string]: {
      value: number;
      unit: string;
      rank?: number;
      percentile?: number;
    };
  };
  metadata: {
    systemType: string;
    industry: string;
    scale: string;
    notes?: string;
  };
}

interface CompetitorData {
  id: string;
  name: string;
  type: 'competitor' | 'industry' | 'academic';
  description: string;
  lastUpdated: string;
  metrics: {
    [key: string]: {
      value: number;
      confidence: number;
      source: string;
    };
  };
}

interface ComparisonResult {
  metric: string;
  yourValue: number;
  benchmarkValue: number;
  difference: number;
  differencePercent: number;
  rank: number;
  totalCompetitors: number;
  percentile: number;
  status: 'leading' | 'competitive' | 'lagging';
  recommendations: string[];
}

interface IndustryStandard {
  name: string;
  description: string;
  source: string;
  year: number;
  metrics: {
    [key: string]: {
      min: number;
      average: number;
      topQuartile: number;
      best: number;
    };
  };
}

// Mock data generation
const mockBenchmarkData: BenchmarkData[] = [
  {
    id: 'bmd-001',
    name: 'RAG System Performance Survey 2024',
    category: 'industry',
    description: 'Comprehensive survey of RAG systems across enterprises',
    source: 'AI Research Institute',
    date: '2024-09-01',
    metrics: {
      answerRelevancy: { value: 72.5, unit: '%', percentile: 65 },
      faithfulness: { value: 88.3, unit: '%', percentile: 70 },
      contextualRelevancy: { value: 75.2, unit: '%', percentile: 60 },
      latency: { value: 2100, unit: 'ms', percentile: 55 },
      throughput: { value: 42, unit: 'qpm', percentile: 60 },
      successRate: { value: 87.0, unit: '%', percentile: 65 },
    },
    metadata: {
      systemType: 'Enterprise RAG',
      industry: 'Technology',
      scale: 'Large (1000+ docs)',
      notes: 'Based on 150 enterprise systems',
    },
  },
  {
    id: 'bmd-002',
    name: 'Academic RAG Benchmark',
    category: 'academic',
    description: 'Academic benchmark for RAG system evaluation',
    source: 'Stanford AI Lab',
    date: '2024-08-15',
    metrics: {
      answerRelevancy: { value: 78.3, unit: '%', percentile: 80 },
      faithfulness: { value: 91.7, unit: '%', percentile: 85 },
      contextualRelevancy: { value: 82.1, unit: '%', percentile: 75 },
      latency: { value: 1850, unit: 'ms', percentile: 70 },
      throughput: { value: 55, unit: 'qpm', percentile: 75 },
      successRate: { value: 91.2, unit: '%', percentile: 80 },
    },
    metadata: {
      systemType: 'Research Prototype',
      industry: 'Academic',
      scale: 'Medium (100-1000 docs)',
    },
  },
];

const mockCompetitorData: CompetitorData[] = [
  {
    id: 'comp-001',
    name: 'Competitor A',
    type: 'competitor',
    description: 'Leading enterprise RAG solution',
    lastUpdated: '2024-10-10',
    metrics: {
      answerRelevancy: {
        value: 75.2,
        confidence: 0.8,
        source: 'Public reports',
      },
      faithfulness: { value: 89.5, confidence: 0.7, source: 'Public reports' },
      contextualRelevancy: {
        value: 72.8,
        confidence: 0.6,
        source: 'Public reports',
      },
      latency: { value: 1950, confidence: 0.8, source: 'User testing' },
      throughput: { value: 48, confidence: 0.7, source: 'Public reports' },
      successRate: { value: 88.3, confidence: 0.8, source: 'Public reports' },
    },
  },
  {
    id: 'comp-002',
    name: 'Competitor B',
    type: 'competitor',
    description: 'AI-powered search platform',
    lastUpdated: '2024-10-08',
    metrics: {
      answerRelevancy: {
        value: 71.8,
        confidence: 0.7,
        source: 'Industry analysis',
      },
      faithfulness: {
        value: 86.2,
        confidence: 0.6,
        source: 'Industry analysis',
      },
      contextualRelevancy: {
        value: 69.5,
        confidence: 0.7,
        source: 'Industry analysis',
      },
      latency: { value: 1680, confidence: 0.8, source: 'User testing' },
      throughput: { value: 52, confidence: 0.8, source: 'User testing' },
      successRate: {
        value: 85.7,
        confidence: 0.7,
        source: 'Industry analysis',
      },
    },
  },
];

const industryStandards: IndustryStandard[] = [
  {
    name: 'Enterprise RAG Standards 2024',
    description: 'Industry standards for enterprise-grade RAG systems',
    source: 'Enterprise AI Alliance',
    year: 2024,
    metrics: {
      answerRelevancy: { min: 60, average: 72, topQuartile: 82, best: 90 },
      faithfulness: { min: 75, average: 87, topQuartile: 93, best: 98 },
      contextualRelevancy: { min: 65, average: 75, topQuartile: 85, best: 92 },
      latency: { min: 500, average: 2000, topQuartile: 1200, best: 800 },
      throughput: { min: 20, average: 45, topQuartile: 65, best: 85 },
      successRate: { min: 70, average: 85, topQuartile: 92, best: 97 },
    },
  },
];

const benchmarkCategories: BenchmarkCategory[] = [
  {
    id: 'quality',
    name: 'Quality Metrics',
    description: 'Answer quality and accuracy metrics',
    metrics: ['answerRelevancy', 'faithfulness', 'contextualRelevancy'],
    weight: 0.4,
  },
  {
    id: 'performance',
    name: 'Performance Metrics',
    description: 'System performance and efficiency',
    metrics: ['latency', 'throughput', 'successRate'],
    weight: 0.3,
  },
  {
    id: 'user',
    name: 'User Experience',
    description: 'User satisfaction and experience metrics',
    metrics: ['userSatisfaction', 'taskCompletion', 'errorRate'],
    weight: 0.3,
  },
];

interface BenchmarkComparisonToolsProps {
  yourSystemData?: {
    answerRelevancy: number;
    faithfulness: number;
    contextualRelevancy: number;
    latency: number;
    throughput: number;
    successRate: number;
    userSatisfaction?: number;
  };
  onExportReport?: (report: any) => void;
  onSettingsClick?: () => void;
  className?: string;
}

const BenchmarkComparisonTools: React.FC<BenchmarkComparisonToolsProps> = ({
  yourSystemData,
  onExportReport,
  onSettingsClick,
  className,
}) => {
  const [selectedBenchmark, setSelectedBenchmark] = useState<string>('bmd-001');
  const [selectedCompetitors, setSelectedCompetitors] = useState<string[]>([
    'comp-001',
    'comp-002',
  ]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showPercentiles, setShowPercentiles] = useState(true);
  const [showTrends, setShowTrends] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [isLoading, setIsLoading] = useState(false);

  // Your system data (mock if not provided)
  const yourData = useMemo(() => {
    return (
      yourSystemData || {
        answerRelevancy: 78.5,
        faithfulness: 92.3,
        contextualRelevancy: 85.2,
        latency: 1650,
        throughput: 58,
        successRate: 91.8,
        userSatisfaction: 83.5,
      }
    );
  }, [yourSystemData]);

  // Get selected benchmark
  const selectedBenchmarkData = useMemo(() => {
    return mockBenchmarkData.find((b) => b.id === selectedBenchmark);
  }, [selectedBenchmark]);

  const primaryIndustryStandard = industryStandards[0];

  // Calculate comparisons
  const comparisons = useMemo((): ComparisonResult[] => {
    if (!selectedBenchmarkData) return [];

    return Object.entries(yourData)
      .map(([metric, value]) => {
        const benchmarkValue = selectedBenchmarkData.metrics[metric]?.value;
        if (!benchmarkValue) return null;

        const difference = value - benchmarkValue;
        const differencePercent = (difference / benchmarkValue) * 100;

        // Calculate percentile ranking
        // For metrics like latency, lower is better, so reverse the sort
        const isLowerBetter = metric.includes('latency');
        const allValues = [
          benchmarkValue,
          ...mockCompetitorData
            .map((c) => c.metrics[metric]?.value || 0)
            .filter((v) => v > 0),
          value,
        ].sort((a, b) => (isLowerBetter ? a - b : b - a));

        const rank = allValues.indexOf(value) + 1;
        const percentile = ((allValues.length - rank) / allValues.length) * 100;

        let status: 'leading' | 'competitive' | 'lagging' = 'competitive';
        if (differencePercent > 10) status = 'leading';
        else if (differencePercent < -10) status = 'lagging';

        const recommendations = [];
        if (status === 'lagging') {
          if (metric.includes('latency')) {
            recommendations.push('Consider optimizing your retrieval pipeline');
            recommendations.push('Implement caching for frequent queries');
          } else if (metric.includes('Relevancy')) {
            recommendations.push('Improve document chunking strategy');
            recommendations.push('Enhance embedding models');
          } else if (metric.includes('throughput')) {
            recommendations.push('Scale your infrastructure');
            recommendations.push('Optimize parallel processing');
          }
        }

        return {
          metric,
          yourValue: value,
          benchmarkValue,
          difference,
          differencePercent,
          rank,
          totalCompetitors: allValues.length,
          percentile,
          status,
          recommendations,
        };
      })
      .filter(Boolean) as ComparisonResult[];
  }, [yourData, selectedBenchmarkData]);

  // Radar chart data
  const radarData = useMemo(() => {
    const metrics = Object.keys(yourData).filter(
      (key) =>
        selectedCategory === 'all' ||
        benchmarkCategories
          .find((cat) => cat.id === selectedCategory)
          ?.metrics.includes(key)
    );

    return metrics.map((metric) => {
      const benchmark = selectedBenchmarkData?.metrics[metric]?.value || 0;
      const standard = industryStandards[0]?.metrics[metric];

      // Normalize metrics to 0-100 scale
      const isLowerBetter = metric.includes('latency');
      const yourValue = yourData[metric as keyof typeof yourData] as number;
      const min = standard?.min || Math.min(yourValue, benchmark) * 0.5;
      const max = standard?.best || Math.max(yourValue, benchmark) * 1.5;
      const range = max - min;

      const normalize = (value: number) => {
        if (!Number.isFinite(range) || Math.abs(range) < Number.EPSILON) {
          return 50;
        }
        if (isLowerBetter) {
          // For lower-is-better metrics, invert the scale
          return Math.max(0, Math.min(100, ((max - value) / range) * 100));
        }
        return Math.max(0, Math.min(100, ((value - min) / range) * 100));
      };

      return {
        metric: metric
          .replace(/([A-Z])/g, ' $1')
          .trim()
          .replace(/\b\w/g, (l) => l.toUpperCase()),
        yourSystem: normalize(yourValue),
        benchmark: normalize(benchmark),
        industryAvg: normalize(standard?.average || benchmark),
        topQuartile: normalize(standard?.topQuartile || benchmark * 1.1),
      };
    });
  }, [yourData, selectedBenchmarkData, selectedCategory]);

  // Performance comparison chart data
  const performanceData = useMemo(() => {
    const competitors = mockCompetitorData.filter((c) =>
      selectedCompetitors.includes(c.id)
    );

    return Object.keys(yourData).map((metric) => {
      const dataPoint: any = {
        metric: metric.replace(/([A-Z])/g, ' $1').trim(),
        'Your System': yourData[metric as keyof typeof yourData],
      };

      competitors.forEach((competitor) => {
        dataPoint[competitor.name] = competitor.metrics[metric]?.value || 0;
      });

      if (selectedBenchmarkData) {
        dataPoint['Benchmark'] =
          selectedBenchmarkData.metrics[metric]?.value || 0;
      }

      return dataPoint;
    });
  }, [yourData, selectedCompetitors, selectedBenchmarkData]);

  // Get metric icon
  const getMetricIcon = (metric: string) => {
    if (metric.includes('Relevancy')) return <Brain className="h-4 w-4" />;
    if (metric.includes('latency')) return <Clock className="h-4 w-4" />;
    if (metric.includes('throughput')) return <Zap className="h-4 w-4" />;
    if (metric.includes('success')) return <CheckCircle className="h-4 w-4" />;
    return <Target className="h-4 w-4" />;
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'leading':
        return 'text-green-600 bg-green-100 border-green-200';
      case 'competitive':
        return 'text-blue-600 bg-blue-100 border-blue-200';
      case 'lagging':
        return 'text-red-600 bg-red-100 border-red-200';
      default:
        return 'text-foreground bg-gray-100 border-border';
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'leading':
        return <TrendingUp className="h-4 w-4" />;
      case 'competitive':
        return <Target className="h-4 w-4" />;
      case 'lagging':
        return <TrendingDown className="h-4 w-4" />;
      default:
        return <AlertTriangle className="h-4 w-4" />;
    }
  };

  // Refresh data
  const refreshData = useCallback(() => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
    }, 2000);
  }, []);

  // Export report
  const exportReport = useCallback(() => {
    const report = {
      timestamp: new Date().toISOString(),
      yourSystem: yourData,
      benchmark: selectedBenchmarkData,
      comparisons,
      competitors: mockCompetitorData.filter((c) =>
        selectedCompetitors.includes(c.id)
      ),
      industryStandards,
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `benchmark-comparison-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);

    onExportReport?.(report);
  }, [
    yourData,
    selectedBenchmarkData,
    comparisons,
    selectedCompetitors,
    onExportReport,
  ]);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Benchmark Comparison
          </h2>
          <p className="text-foreground">
            Compare your RAG system against industry benchmarks and competitors
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`}
            />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={exportReport}>
            <Download className="h-4 w-4 mr-2" />
            Export Report
          </Button>
          <Button variant="outline" size="sm" onClick={onSettingsClick}>
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <BarChart3 className="h-5 w-5 mr-2" />
            Comparison Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <Label>Benchmark Source</Label>
              <Select
                value={selectedBenchmark}
                onValueChange={setSelectedBenchmark}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {mockBenchmarkData.map((benchmark) => (
                    <SelectItem key={benchmark.id} value={benchmark.id}>
                      {benchmark.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Category Focus</Label>
              <Select
                value={selectedCategory}
                onValueChange={setSelectedCategory}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {benchmarkCategories.map((category) => (
                    <SelectItem key={category.id} value={category.id}>
                      {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="show-percentiles"
                checked={showPercentiles}
                onCheckedChange={setShowPercentiles}
              />
              <Label htmlFor="show-percentiles">Show Percentiles</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="show-trends"
                checked={showTrends}
                onCheckedChange={setShowTrends}
              />
              <Label htmlFor="show-trends">Show Trends</Label>
            </div>
          </div>

          {/* Competitor Selection */}
          <div>
            <Label>Compare Against</Label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
              {mockCompetitorData.map((competitor) => (
                <div
                  key={competitor.id}
                  className="flex items-center space-x-2"
                >
                  <Switch
                    id={`comp-${competitor.id}`}
                    checked={selectedCompetitors.includes(competitor.id)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        setSelectedCompetitors((prev) => [
                          ...prev,
                          competitor.id,
                        ]);
                      } else {
                        setSelectedCompetitors((prev) =>
                          prev.filter((id) => id !== competitor.id)
                        );
                      }
                    }}
                  />
                  <Label htmlFor={`comp-${competitor.id}`} className="text-sm">
                    {competitor.name}
                  </Label>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Overview</span>
          </TabsTrigger>
          <TabsTrigger value="detailed" className="flex items-center space-x-2">
            <Target className="h-4 w-4" />
            <span>Detailed Analysis</span>
          </TabsTrigger>
          <TabsTrigger value="radar" className="flex items-center space-x-2">
            <Globe className="h-4 w-4" />
            <span>Radar View</span>
          </TabsTrigger>
          <TabsTrigger value="insights" className="flex items-center space-x-2">
            <Star className="h-4 w-4" />
            <span>Insights</span>
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center">
                  <Award className="h-5 w-5 mr-2 text-green-500" />
                  Your Ranking
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {comparisons.slice(0, 3).map((comparison) => (
                    <div
                      key={comparison.metric}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-2">
                        {getMetricIcon(comparison.metric)}
                        <span className="text-sm">
                          {comparison.metric.replace(/([A-Z])/g, ' $1').trim()}
                        </span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge className={getStatusColor(comparison.status)}>
                          #{comparison.rank}/{comparison.totalCompetitors}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {comparison.percentile.toFixed(0)}th
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center">
                  <TrendingUp className="h-5 w-5 mr-2 text-blue-500" />
                  Key Improvements
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {comparisons
                    .filter((c) => c.status === 'leading')
                    .slice(0, 3)
                    .map((comparison) => (
                      <div key={comparison.metric} className="text-sm">
                        <div className="font-medium">
                          {comparison.metric.replace(/([A-Z])/g, ' $1').trim()}
                        </div>
                        <div className="text-green-600">
                          +{comparison.differencePercent.toFixed(1)}% vs
                          benchmark
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center">
                  <AlertTriangle className="h-5 w-5 mr-2 text-yellow-500" />
                  Areas to Improve
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {comparisons
                    .filter((c) => c.status === 'lagging')
                    .slice(0, 3)
                    .map((comparison) => (
                      <div key={comparison.metric} className="text-sm">
                        <div className="font-medium">
                          {comparison.metric.replace(/([A-Z])/g, ' $1').trim()}
                        </div>
                        <div className="text-red-600">
                          {comparison.differencePercent.toFixed(1)}% below
                          benchmark
                        </div>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Performance Comparison Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Performance Comparison</CardTitle>
              <CardDescription>
                Compare your system against selected benchmarks and competitors
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={performanceData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="metric" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                      }}
                    />
                    <Legend />
                    <Bar dataKey="Your System" fill="#3b82f6" />
                    <Bar dataKey="Benchmark" fill="#10b981" />
                    {mockCompetitorData
                      .filter((c) => selectedCompetitors.includes(c.id))
                      .map((competitor, index) => (
                        <Bar
                          key={competitor.id}
                          dataKey={competitor.name}
                          fill={`hsl(${index * 60}, 70%, 50%)`}
                        />
                      ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Detailed Analysis Tab */}
        <TabsContent value="detailed" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Metric-by-Metric Analysis</CardTitle>
              <CardDescription>
                Detailed comparison for each performance metric
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {comparisons.map((comparison) => (
                  <div
                    key={comparison.metric}
                    className="border rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-3">
                        {getMetricIcon(comparison.metric)}
                        <div>
                          <h4 className="font-medium">
                            {comparison.metric
                              .replace(/([A-Z])/g, ' $1')
                              .trim()}
                          </h4>
                          <p className="text-sm text-foreground">
                            Rank #{comparison.rank} of{' '}
                            {comparison.totalCompetitors}
                          </p>
                        </div>
                      </div>
                      <Badge className={getStatusColor(comparison.status)}>
                        <div className="flex items-center space-x-1">
                          {getStatusIcon(comparison.status)}
                          <span>{comparison.status}</span>
                        </div>
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
                      <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
                        <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                          {comparison.yourValue.toFixed(1)}
                        </div>
                        <div className="text-sm text-foreground">
                          Your System
                        </div>
                      </div>
                      <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded">
                        <div className="text-2xl font-bold text-foreground">
                          {comparison.benchmarkValue.toFixed(1)}
                        </div>
                        <div className="text-sm text-foreground">Benchmark</div>
                      </div>
                      <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded">
                        <div
                          className={`text-2xl font-bold ${
                            comparison.differencePercent >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                          }`}
                        >
                          {comparison.differencePercent >= 0 ? '+' : ''}
                          {comparison.differencePercent.toFixed(1)}%
                        </div>
                        <div className="text-sm text-foreground">
                          Difference
                        </div>
                      </div>
                    </div>

                    {showPercentiles && (
                      <div className="mb-3">
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span>Percentile Ranking</span>
                          <span>{comparison.percentile.toFixed(0)}th</span>
                        </div>
                        <Progress
                          value={comparison.percentile}
                          className="h-2"
                        />
                      </div>
                    )}

                    {comparison.recommendations.length > 0 && (
                      <div>
                        <h5 className="font-medium text-sm mb-2">
                          Recommendations:
                        </h5>
                        <ul className="text-sm text-foreground space-y-1">
                          {comparison.recommendations.map((rec, index) => (
                            <li
                              key={index}
                              className="flex items-start space-x-2"
                            >
                              <ChevronRight className="h-4 w-4 mt-0.5 text-muted-foreground" />
                              <span>{rec}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Radar View Tab */}
        <TabsContent value="radar" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Multi-Dimensional Comparison</CardTitle>
              <CardDescription>
                Radar chart showing performance across all metrics
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 12 }} />
                    <PolarRadiusAxis
                      angle={90}
                      domain={[0, 100]}
                      tick={{ fontSize: 10 }}
                    />
                    <Radar
                      name="Your System"
                      dataKey="yourSystem"
                      stroke="#3b82f6"
                      fill="#3b82f6"
                      fillOpacity={0.3}
                      strokeWidth={2}
                    />
                    <Radar
                      name="Industry Average"
                      dataKey="industryAvg"
                      stroke="#10b981"
                      fill="#10b981"
                      fillOpacity={0.1}
                      strokeWidth={1}
                      strokeDasharray="5 5"
                    />
                    <Radar
                      name="Top Quartile"
                      dataKey="topQuartile"
                      stroke="#f59e0b"
                      fill="#f59e0b"
                      fillOpacity={0.1}
                      strokeWidth={1}
                      strokeDasharray="3 3"
                    />
                    <Legend />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Insights Tab */}
        <TabsContent value="insights" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Star className="h-5 w-5 mr-2" />
                  Strengths
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {comparisons
                    .filter((c) => c.status === 'leading')
                    .map((comparison) => (
                      <div
                        key={comparison.metric}
                        className="flex items-start space-x-3"
                      >
                        <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
                        <div>
                          <h5 className="font-medium">
                            {comparison.metric
                              .replace(/([A-Z])/g, ' $1')
                              .trim()}
                          </h5>
                          <p className="text-sm text-foreground">
                            Outperforms {comparison.percentile.toFixed(0)}% of
                            comparable systems
                          </p>
                        </div>
                      </div>
                    ))}
                  {comparisons.filter((c) => c.status === 'leading').length ===
                    0 && (
                    <p className="text-sm text-muted-foreground">
                      No metrics are currently leading compared to benchmarks
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Target className="h-5 w-5 mr-2" />
                  Improvement Opportunities
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {comparisons
                    .filter((c) => c.status === 'lagging')
                    .map((comparison) => (
                      <div
                        key={comparison.metric}
                        className="flex items-start space-x-3"
                      >
                        <XCircle className="h-5 w-5 text-red-500 mt-0.5" />
                        <div>
                          <h5 className="font-medium">
                            {comparison.metric
                              .replace(/([A-Z])/g, ' $1')
                              .trim()}
                          </h5>
                          <p className="text-sm text-foreground">
                            {Math.abs(comparison.differencePercent).toFixed(1)}%
                            below benchmark average
                          </p>
                          <div className="mt-1">
                            <p className="text-xs text-muted-foreground">
                              Priority recommendations:
                            </p>
                            <ul className="text-xs text-foreground ml-2">
                              {comparison.recommendations
                                .slice(0, 2)
                                .map((rec, index) => (
                                  <li key={index}>• {rec}</li>
                                ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ))}
                  {comparisons.filter((c) => c.status === 'lagging').length ===
                    0 && (
                    <p className="text-sm text-muted-foreground">
                      All metrics are competitive with industry benchmarks
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Industry Standards Comparison */}
          <Card>
            <CardHeader>
              <CardTitle>Industry Standards Compliance</CardTitle>
              <CardDescription>
                How your system compares to established industry standards
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {primaryIndustryStandard &&
                  Object.entries(primaryIndustryStandard.metrics).map(
                    ([metric, standards]) => {
                      const yourValue = yourData[
                        metric as keyof typeof yourData
                      ] as number;
                      const percentile =
                        ((yourValue - standards.min) /
                          (standards.best - standards.min)) *
                        100;

                      let status = 'below-average';
                      if (yourValue >= standards.topQuartile)
                        status = 'excellent';
                      else if (yourValue >= standards.average) status = 'good';
                      else if (yourValue >= standards.min)
                        status = 'acceptable';

                      return (
                        <div key={metric} className="border rounded-lg p-4">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center space-x-2">
                              {getMetricIcon(metric)}
                              <span className="font-medium">
                                {metric.replace(/([A-Z])/g, ' $1').trim()}
                              </span>
                            </div>
                            <Badge
                              variant={
                                status === 'excellent'
                                  ? 'default'
                                  : status === 'good'
                                    ? 'secondary'
                                    : status === 'acceptable'
                                      ? 'outline'
                                      : 'destructive'
                              }
                            >
                              {status}
                            </Badge>
                          </div>

                          <div className="grid grid-cols-5 gap-2 text-xs">
                            <div className="text-center">
                              <div className="text-muted-foreground">Min</div>
                              <div className="font-medium">{standards.min}</div>
                            </div>
                            <div className="text-center">
                              <div className="text-muted-foreground">
                                Average
                              </div>
                              <div className="font-medium">
                                {standards.average}
                              </div>
                            </div>
                            <div className="text-center">
                              <div className="text-muted-foreground">
                                Top Quartile
                              </div>
                              <div className="font-medium">
                                {standards.topQuartile}
                              </div>
                            </div>
                            <div className="text-center">
                              <div className="text-muted-foreground">Best</div>
                              <div className="font-medium">
                                {standards.best}
                              </div>
                            </div>
                            <div className="text-center">
                              <div className="text-muted-foreground">You</div>
                              <div className="font-bold text-blue-600">
                                {yourValue}
                              </div>
                            </div>
                          </div>

                          <div className="mt-2">
                            <Progress
                              value={Math.max(0, Math.min(100, percentile))}
                              className="h-2"
                            />
                          </div>
                        </div>
                      );
                    }
                  )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default BenchmarkComparisonTools;
