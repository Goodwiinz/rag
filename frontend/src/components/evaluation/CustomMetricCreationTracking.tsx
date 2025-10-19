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
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ScatterChart,
  Scatter,
} from 'recharts';
import {
  Plus,
  Edit,
  Trash2,
  Save,
  Eye,
  TrendingUp,
  TrendingDown,
  Target,
  Settings,
  Calculator,
  BarChart3,
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
 Zap,
 Brain,
 Database,
  Filter,
  Download,
  Upload,
  Copy,
  Play,
  Pause,
  RefreshCw,
  Info,
} from 'lucide-react';

// Component Props Interfaces
interface CustomMetricCreationTrackingProps {
  onMetricCreate?: (metric: CustomMetric) => void;
  onMetricUpdate?: (metric: CustomMetric) => void;
  onMetricDelete?: (metricId: string) => void;
  className?: string;
}

interface MetricFormProps {
  metric?: CustomMetric | null;
  onSubmit: (metric: Partial<CustomMetric>) => void;
  onCancel: () => void;
}

// Types
interface CustomMetric {
  id: string;
  name: string;
  description: string;
  category: 'performance' | 'quality' | 'usage' | 'business' | 'technical';
  type: 'simple' | 'composite' | 'derived' | 'calculated';
  formula: string;
  dataSource: string[];
  aggregation: 'sum' | 'average' | 'min' | 'max' | 'count' | 'percentile' | 'custom';
  unit: string;
  target?: {
    value: number;
    operator: 'gte' | 'lte' | 'eq' | 'gt' | 'lt';
    color: string;
  };
  thresholds?: {
    warning: number;
    critical: number;
  };
  tags: string[];
  isActive: boolean;
  schedule?: {
    frequency: 'realtime' | 'hourly' | 'daily' | 'weekly';
    enabled: boolean;
  };
  permissions: {
    view: string[];
    edit: string[];
  };
  created: string;
  updated: string;
  createdBy: string;
  lastCalculated?: string;
}

interface MetricDataPoint {
  timestamp: string;
  value: number;
  metadata?: Record<string, any>;
}

interface MetricCalculation {
  id: string;
  metricId: string;
  timestamp: string;
  value: number;
  formula: string;
  inputs: Record<string, number>;
  executionTime: number;
  status: 'success' | 'error' | 'pending';
  errorMessage?: string;
}

interface MetricTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  formula: string;
  dataSources: string[];
  aggregation: string;
  unit: string;
}

// Mock data
const mockCustomMetrics: CustomMetric[] = [
  {
    id: 'metric-001',
    name: 'Response Quality Index',
    description: 'Composite metric combining answer relevancy, faithfulness, and user satisfaction',
    category: 'quality',
    type: 'composite',
    formula: '(answer_relevancy * 0.4) + (faithfulness * 0.4) + (user_satisfaction * 0.2)',
    dataSource: ['answer_relevancy', 'faithfulness', 'user_satisfaction'],
    aggregation: 'average',
    unit: 'score',
    target: {
      value: 80,
      operator: 'gte',
      color: '#10b981',
    },
    thresholds: {
      warning: 70,
      critical: 60,
    },
    tags: ['quality', 'composite', 'user-experience'],
    isActive: true,
    schedule: {
      frequency: 'realtime',
      enabled: true,
    },
    permissions: {
      view: ['team-a', 'team-b'],
      edit: ['team-a'],
    },
    created: '2025-10-01T10:00:00Z',
    updated: '2025-10-15T14:30:00Z',
    createdBy: 'john.doe',
    lastCalculated: '2025-10-17T12:00:00Z',
  },
  {
    id: 'metric-002',
    name: 'System Efficiency Ratio',
    description: 'Ratio of successful queries to total resource consumption',
    category: 'performance',
    type: 'derived',
    formula: '(successful_queries / total_queries) / (avg_cpu_usage + avg_memory_usage)',
    dataSource: ['successful_queries', 'total_queries', 'avg_cpu_usage', 'avg_memory_usage'],
    aggregation: 'average',
    unit: 'ratio',
    target: {
      value: 0.75,
      operator: 'gte',
      color: '#3b82f6',
    },
    thresholds: {
      warning: 0.6,
      critical: 0.4,
    },
    tags: ['performance', 'efficiency', 'resources'],
    isActive: true,
    schedule: {
      frequency: 'hourly',
      enabled: true,
    },
    permissions: {
      view: ['team-a', 'ops-team'],
      edit: ['ops-team'],
    },
    created: '2025-10-05T09:15:00Z',
    updated: '2025-10-14T16:45:00Z',
    createdBy: 'ops-admin',
    lastCalculated: '2025-10-17T11:00:00Z',
  },
  {
    id: 'metric-003',
    name: 'Knowledge Graph Coverage',
    description: 'Percentage of queries that utilize knowledge graph entities',
    category: 'technical',
    type: 'calculated',
    formula: '(queries_with_entities / total_queries) * 100',
    dataSource: ['queries_with_entities', 'total_queries'],
    aggregation: 'percentile',
    unit: '%',
    target: {
      value: 60,
      operator: 'gte',
      color: '#8b5cf6',
    },
    tags: ['knowledge-graph', 'entities', 'coverage'],
    isActive: false,
    permissions: {
      view: ['team-a'],
      edit: ['team-a'],
    },
    created: '2025-10-10T13:20:00Z',
    updated: '2025-10-12T10:30:00Z',
    createdBy: 'data-scientist',
  },
];

const metricTemplates: MetricTemplate[] = [
  {
    id: 'template-001',
    name: 'User Engagement Score',
    description: 'Measures user engagement based on query frequency and feedback',
    category: 'usage',
    formula: '(queries_per_session * 0.6) + (avg_session_duration * 0.4)',
    dataSources: ['queries_per_session', 'avg_session_duration'],
    aggregation: 'average',
    unit: 'score',
  },
  {
    id: 'template-002',
    name: 'Cost Per Query',
    description: 'Calculates the operational cost per individual query',
    category: 'business',
    formula: 'total_operational_cost / total_queries',
    dataSources: ['total_operational_cost', 'total_queries'],
    aggregation: 'average',
    unit: 'USD',
  },
  {
    id: 'template-003',
    name: 'Data Freshness Index',
    description: 'Measures how recent the data used in responses is',
    category: 'quality',
    formula: 'avg_document_age / max_acceptable_age',
    dataSources: ['avg_document_age', 'max_acceptable_age'],
    aggregation: 'average',
    unit: 'ratio',
  },
];

const availableDataSources = [
  { id: 'answer_relevancy', name: 'Answer Relevancy', type: 'quality', unit: '%' },
  { id: 'faithfulness', name: 'Faithfulness', type: 'quality', unit: '%' },
  { id: 'contextual_relevancy', name: 'Contextual Relevancy', type: 'quality', unit: '%' },
  { id: 'user_satisfaction', name: 'User Satisfaction', type: 'usage', unit: '%' },
  { id: 'response_latency', name: 'Response Latency', type: 'performance', unit: 'ms' },
  { id: 'success_rate', name: 'Success Rate', type: 'performance', unit: '%' },
  { id: 'queries_per_minute', name: 'Queries Per Minute', type: 'usage', unit: 'qpm' },
  { id: 'documents_processed', name: 'Documents Processed', type: 'usage', unit: 'count' },
  { id: 'cpu_usage', name: 'CPU Usage', type: 'technical', unit: '%' },
  { id: 'memory_usage', name: 'Memory Usage', type: 'technical', unit: '%' },
  { id: 'error_rate', name: 'Error Rate', type: 'performance', unit: '%' },
  { id: 'cache_hit_rate', name: 'Cache Hit Rate', type: 'performance', unit: '%' },
];

const CustomMetricCreationTracking: React.FC<CustomMetricCreationTrackingProps> = ({
  onMetricCreate,
  onMetricUpdate,
  onMetricDelete,
  className,
}) => {
  const [metrics, setMetrics] = useState<CustomMetric[]>(mockCustomMetrics);
  const [selectedMetric, setSelectedMetric] = useState<CustomMetric | null>(null);
  const [activeTab, setActiveTab] = useState('metrics');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<CustomMetric | null>(null);
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Filter metrics
  const filteredMetrics = useMemo(() => {
    return metrics.filter(metric => {
      const matchesSearch = metric.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           metric.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = filterCategory === 'all' || metric.category === filterCategory;
      const matchesStatus = filterStatus === 'all' ||
                           (filterStatus === 'active' && metric.isActive) ||
                           (filterStatus === 'inactive' && !metric.isActive);
      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [metrics, searchTerm, filterCategory, filterStatus]);

  // Generate mock metric data
  const generateMetricData = useCallback((metricId: string, days: number = 30): MetricDataPoint[] => {
    const metric = metrics.find(m => m.id === metricId);
    if (!metric) return [];

    const data: MetricDataPoint[] = [];
    const now = new Date();

    for (let i = days; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);

      let value = 75 + Math.random() * 20; // Base value with variation

      // Add trend based on metric type
      if (metric.category === 'quality') {
        value += (days - i) * 0.2; // Slight improvement trend
      } else if (metric.category === 'performance') {
        value += Math.sin((days - i) / 7 * Math.PI * 2) * 5; // Weekly pattern
      }

      // Add some outliers
      if (Math.random() < 0.05) {
        value += (Math.random() - 0.5) * 30;
      }

      // Clamp values
      value = Math.max(0, Math.min(100, value));

      data.push({
        timestamp: date.toISOString(),
        value: Math.round(value * 100) / 100,
      });
    }

    return data;
  }, [metrics]);

  // Safe arithmetic expression evaluator
  const safeEvaluate = (expression: string): number => {
    // Remove any whitespace
    const cleanExpr = expression.replace(/\s/g, '');

    // Validate the expression contains only numbers, operators, and parentheses
    if (!/^[\d\.\+\-\*\/\(\)]+$/.test(cleanExpr)) {
      throw new Error('Invalid characters in expression');
    }

    // Use a safe evaluation approach - parse and calculate step by step
    // This is a simple recursive descent parser for arithmetic expressions
    let pos = 0;

    const parseNumber = (): number => {
      let numStr = '';
      while (pos < cleanExpr.length && (cleanExpr[pos]?.match(/[\d\.]/) || cleanExpr[pos] === '-')) {
        numStr += cleanExpr[pos];
        pos++;
      }
      return parseFloat(numStr);
    };

    const parseFactor = (): number => {
      if (cleanExpr[pos] === '(') {
        pos++; // skip '('
        const result = parseExpression();
        pos++; // skip ')'
        return result;
      }
      return parseNumber();
    };

    const parseTerm = (): number => {
      let result = parseFactor();
      while (pos < cleanExpr.length && (cleanExpr[pos] === '*' || cleanExpr[pos] === '/')) {
        const op = cleanExpr[pos];
        pos++;
        const right = parseFactor();
        result = op === '*' ? result * right : result / right;
      }
      return result;
    };

    const parseExpression = (): number => {
      let result = parseTerm();
      while (pos < cleanExpr.length && (cleanExpr[pos] === '+' || cleanExpr[pos] === '-')) {
        const op = cleanExpr[pos];
        pos++;
        const right = parseTerm();
        result = op === '+' ? result + right : result - right;
      }
      return result;
    };

    return parseExpression();
  };

  // Calculate metric value
  const calculateMetricValue = useCallback((metric: CustomMetric): number => {
    // This is a mock calculation - in real implementation this would query actual data sources
    const mockValues: Record<string, number> = {
      answer_relevancy: 78.5,
      faithfulness: 92.3,
      contextual_relevancy: 85.2,
      user_satisfaction: 83.5,
      successful_queries: 920,
      total_queries: 1000,
      avg_cpu_usage: 45,
      avg_memory_usage: 60,
      queries_with_entities: 580,
    };

    try {
      // Replace variable names with their values
      let formula = metric.formula;
      Object.entries(mockValues).forEach(([key, value]) => {
        formula = formula.replace(new RegExp(key, 'g'), value.toString());
      });

      // Use safe evaluator instead of Function constructor
      const result = safeEvaluate(formula);
      return Math.round(result * 100) / 100;
    } catch (error) {
      console.error('Error calculating metric:', error);
      return 0;
    }
  }, []);

  // Get category icon
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'performance': return <Zap className="h-4 w-4" />;
      case 'quality': return <Target className="h-4 w-4" />;
      case 'usage': return <Activity className="h-4 w-4" />;
      case 'business': return <Calculator className="h-4 w-4" />;
      case 'technical': return <Database className="h-4 w-4" />;
      default: return <BarChart3 className="h-4 w-4" />;
    }
  };

  // Get status color
  const getStatusColor = (metric: CustomMetric) => {
    if (!metric.isActive) return 'bg-gray-100 text-gray-800 border-gray-200';

    const currentValue = calculateMetricValue(metric);
    if (metric.thresholds) {
      if (currentValue <= metric.thresholds.critical) return 'bg-red-100 text-red-800 border-red-200';
      if (currentValue <= metric.thresholds.warning) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    }
    return 'bg-green-100 text-green-800 border-green-200';
  };

  // Create or update metric
  const handleSaveMetric = useCallback((metricData: Partial<CustomMetric>) => {
    if (editingMetric) {
      // Update existing metric
      setMetrics(prev => prev.map(m =>
        m.id === editingMetric.id
          ? { ...m, ...metricData, updated: new Date().toISOString() }
          : m
      ));
      setEditingMetric(null);
    } else {
      // Create new metric
      const newMetric: CustomMetric = {
        id: `metric-${Date.now()}`,
        name: metricData.name || 'New Metric',
        description: metricData.description || '',
        category: metricData.category || 'performance',
        type: metricData.type || 'simple',
        formula: metricData.formula || '',
        dataSource: metricData.dataSource || [],
        aggregation: metricData.aggregation || 'average',
        unit: metricData.unit || '',
        target: metricData.target,
        thresholds: metricData.thresholds,
        tags: metricData.tags || [],
        isActive: metricData.isActive ?? true,
        schedule: metricData.schedule,
        permissions: {
          view: ['team-a'],
          edit: ['team-a'],
        },
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        createdBy: 'current-user',
      };
      setMetrics(prev => [...prev, newMetric]);
      onMetricCreate?.(newMetric);
    }
    setIsCreateDialogOpen(false);
  }, [editingMetric, onMetricCreate]);

  // Delete metric
  const handleDeleteMetric = useCallback((metricId: string) => {
    setMetrics(prev => prev.filter(m => m.id !== metricId));
    onMetricDelete?.(metricId);
  }, [onMetricDelete]);

  // Toggle metric active status
  const toggleMetricStatus = useCallback((metricId: string) => {
    setMetrics(prev => prev.map(m =>
      m.id === metricId
        ? { ...m, isActive: !m.isActive, updated: new Date().toISOString() }
        : m
    ));
  }, []);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Custom Metrics</h2>
          <p className="text-gray-600 dark:text-gray-400">Create and track custom metrics for your RAG system</p>
        </div>
        <div className="flex items-center space-x-2">
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Metric
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>{editingMetric ? 'Edit Metric' : 'Create Custom Metric'}</DialogTitle>
                <DialogDescription>
                  Define a custom metric to track specific aspects of your RAG system performance
                </DialogDescription>
              </DialogHeader>
              <MetricForm
                metric={editingMetric}
                onSubmit={handleSaveMetric}
                onCancel={() => {
                  setIsCreateDialogOpen(false);
                  setEditingMetric(null);
                }}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center space-x-4">
            <div className="flex-1">
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search metrics..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="performance">Performance</SelectItem>
                <SelectItem value="quality">Quality</SelectItem>
                <SelectItem value="usage">Usage</SelectItem>
                <SelectItem value="business">Business</SelectItem>
                <SelectItem value="technical">Technical</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="metrics" className="flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Metrics</span>
          </TabsTrigger>
          <TabsTrigger value="templates" className="flex items-center space-x-2">
            <Copy className="h-4 w-4" />
            <span>Templates</span>
          </TabsTrigger>
          <TabsTrigger value="tracking" className="flex items-center space-x-2">
            <Activity className="h-4 w-4" />
            <span>Tracking</span>
          </TabsTrigger>
          <TabsTrigger value="analysis" className="flex items-center space-x-2">
            <TrendingUp className="h-4 w-4" />
            <span>Analysis</span>
          </TabsTrigger>
        </TabsList>

        {/* Metrics Tab */}
        <TabsContent value="metrics" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredMetrics.map(metric => (
              <Card key={metric.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      {getCategoryIcon(metric.category)}
                      <div>
                        <CardTitle className="text-lg">{metric.name}</CardTitle>
                        <CardDescription className="mt-1">{metric.description}</CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge className={getStatusColor(metric)}>
                        {metric.isActive ? 'Active' : 'Inactive'}
                      </Badge>
                      <Switch
                        checked={metric.isActive}
                        onCheckedChange={() => toggleMetricStatus(metric.id)}
                      />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Badge variant="outline">{metric.category}</Badge>
                      <Badge variant="secondary">{metric.type}</Badge>
                      {metric.schedule?.enabled && (
                        <Badge variant="outline" className="text-xs">
                          <Clock className="h-3 w-3 mr-1" />
                          {metric.schedule.frequency}
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm text-gray-500">
                      {metric.unit}
                    </div>
                  </div>

                  {metric.isActive && (
                    <div>
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span>Current Value</span>
                        <span className="font-bold text-lg">{calculateMetricValue(metric).toFixed(2)}</span>
                      </div>
                      {metric.target && (
                        <div className="flex items-center justify-between text-sm text-gray-500">
                          <span>Target</span>
                          <span>{metric.target.value} {metric.unit}</span>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="space-y-2">
                    <div className="text-sm font-medium">Formula:</div>
                    <div className="p-2 bg-gray-50 dark:bg-gray-800 rounded text-sm font-mono">
                      {metric.formula}
                    </div>
                  </div>

                  {metric.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {metric.tags.map(tag => (
                        <Badge key={tag} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-2">
                    <div className="text-xs text-gray-500">
                      Last updated: {new Date(metric.updated).toLocaleDateString()}
                    </div>
                    <div className="flex items-center space-x-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedMetric(metric)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingMetric(metric);
                          setIsCreateDialogOpen(true);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteMetric(metric.id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {metricTemplates.map(template => (
              <Card key={template.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{template.name}</CardTitle>
                  <CardDescription>{template.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">{template.category}</Badge>
                    <div className="text-sm text-gray-500">{template.unit}</div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-medium">Formula:</div>
                    <div className="p-2 bg-gray-50 dark:bg-gray-800 rounded text-sm font-mono">
                      {template.formula}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-medium">Data Sources:</div>
                    <div className="flex flex-wrap gap-1">
                      {template.dataSources.map(source => (
                        <Badge key={source} variant="outline" className="text-xs">
                          {source}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => {
                        const newMetric: Partial<CustomMetric> = {
                          name: template.name,
                          description: template.description,
                          category: template.category as any,
                          formula: template.formula,
                          dataSource: template.dataSources,
                          aggregation: template.aggregation as any,
                          unit: template.unit,
                        };
                        setEditingMetric(newMetric as CustomMetric);
                        setIsCreateDialogOpen(true);
                      }}
                    >
                      <Copy className="h-4 w-4 mr-2" />
                      Use Template
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Eye className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tracking Tab */}
        <TabsContent value="tracking" className="space-y-4">
          {selectedMetric ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center space-x-2">
                    {getCategoryIcon(selectedMetric.category)}
                    <span>{selectedMetric.name} - Historical Data</span>
                  </CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedMetric(null)}
                  >
                    Back to Metrics
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-96">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={generateMetricData(selectedMetric.id)}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="timestamp"
                        tickFormatter={(value) => new Date(value).toLocaleDateString()}
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip
                        labelFormatter={(value) => new Date(value as string).toLocaleString()}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={false}
                        name={selectedMetric.name}
                      />
                      {selectedMetric.target && (
                        <ReferenceLine
                          y={selectedMetric.target.value}
                          stroke={selectedMetric.target.color}
                          strokeDasharray="5 5"
                          label={`Target: ${selectedMetric.target.value}`}
                        />
                      )}
                      {selectedMetric.thresholds && (
                        <>
                          <ReferenceLine
                            y={selectedMetric.thresholds.warning}
                            stroke="#f59e0b"
                            strokeDasharray="3 3"
                            label="Warning"
                          />
                          <ReferenceLine
                            y={selectedMetric.thresholds.critical}
                            stroke="#ef4444"
                            strokeDasharray="3 3"
                            label="Critical"
                          />
                        </>
                      )}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center py-8 text-gray-500">
                  <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Select a metric to view its tracking data</p>
                  <p className="text-sm">Choose a metric from the Metrics tab to see historical trends</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Analysis Tab */}
        <TabsContent value="analysis" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Metrics Overview</CardTitle>
              <CardDescription>Analysis of all active custom metrics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {metrics.filter(m => m.isActive).map(metric => {
                  const currentValue = calculateMetricValue(metric);
                  const data = generateMetricData(metric.id, 7); // Last 7 days
                  const firstDataPoint = data[0];
              const lastDataPoint = data[data.length - 1];
              const trend = data.length > 1 && firstDataPoint?.value !== undefined && lastDataPoint?.value !== undefined && firstDataPoint.value !== 0 ?
                    (lastDataPoint.value - firstDataPoint.value) / firstDataPoint.value * 100 : 0;

                  return (
                    <div key={metric.id} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center space-x-3">
                          {getCategoryIcon(metric.category)}
                          <div>
                            <h4 className="font-medium">{metric.name}</h4>
                            <p className="text-sm text-gray-500">{metric.description}</p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Badge variant="outline">{metric.category}</Badge>
                          <div className="flex items-center space-x-1">
                            {trend > 0 ? <TrendingUp className="h-4 w-4 text-green-500" /> :
                             trend < 0 ? <TrendingDown className="h-4 w-4 text-red-500" /> :
                             <div className="w-4 h-4 bg-gray-300 rounded-full" />}
                            <span className="text-sm">{trend > 0 ? '+' : ''}{trend.toFixed(1)}%</span>
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
                          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                            {currentValue.toFixed(2)}
                          </div>
                          <div className="text-sm text-gray-600 dark:text-gray-400">Current Value</div>
                        </div>
                        {metric.target && (
                          <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded">
                            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                              {metric.target.value}
                            </div>
                            <div className="text-sm text-gray-600 dark:text-gray-400">Target</div>
                          </div>
                        )}
                        <div className="text-center p-3 bg-purple-50 dark:bg-purple-900/20 rounded">
                          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                            {metric.dataSource.length}
                          </div>
                          <div className="text-sm text-gray-600 dark:text-gray-400">Data Sources</div>
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="text-sm font-medium mb-2">Mini Chart (Last 7 days)</div>
                        <div className="h-20">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data}>
                              <Area
                                type="monotone"
                                dataKey="value"
                                stroke="#3b82f6"
                                fill="#3b82f620"
                              />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Metric Form Component
const MetricForm: React.FC<MetricFormProps> = ({ metric, onSubmit, onCancel }) => {
  const [formData, setFormData] = useState({
    name: metric?.name || '',
    description: metric?.description || '',
    category: metric?.category || 'performance',
    type: metric?.type || 'simple',
    formula: metric?.formula || '',
    aggregation: metric?.aggregation || 'average',
    unit: metric?.unit || '',
    targetValue: metric?.target?.value || '',
    targetOperator: metric?.target?.operator || 'gte',
    warningThreshold: metric?.thresholds?.warning || '',
    criticalThreshold: metric?.thresholds?.critical || '',
    scheduleEnabled: metric?.schedule?.enabled || false,
    scheduleFrequency: metric?.schedule?.frequency || 'daily',
    selectedDataSources: metric?.dataSource || [],
    tags: metric?.tags?.join(', ') || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const metricData: Partial<CustomMetric> = {
      name: formData.name,
      description: formData.description,
      category: formData.category as any,
      type: formData.type as any,
      formula: formData.formula,
      aggregation: formData.aggregation as any,
      unit: formData.unit,
      dataSource: formData.selectedDataSources,
      tags: formData.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      schedule: formData.scheduleEnabled ? {
        enabled: true,
        frequency: formData.scheduleFrequency as any,
      } : undefined,
    };

    if (formData.targetValue) {
      metricData.target = {
        value: parseFloat(formData.targetValue.toString()),
        operator: formData.targetOperator as any,
        color: '#10b981',
      };
    }

    if (formData.warningThreshold || formData.criticalThreshold) {
      const thresholds: { warning?: number; critical?: number } = {};
      if (formData.warningThreshold) {
        thresholds.warning = parseFloat(formData.warningThreshold.toString());
      }
      if (formData.criticalThreshold) {
        thresholds.critical = parseFloat(formData.criticalThreshold.toString());
      }
      if (thresholds.warning || thresholds.critical) {
        metricData.thresholds = thresholds as any;
      }
    }

    onSubmit(metricData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="metric-name">Name *</Label>
          <Input
            id="metric-name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Enter metric name"
            required
          />
        </div>
        <div>
          <Label htmlFor="metric-category">Category *</Label>
          <Select value={formData.category} onValueChange={(value) => setFormData(prev => ({ ...prev, category: value as any }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="performance">Performance</SelectItem>
              <SelectItem value="quality">Quality</SelectItem>
              <SelectItem value="usage">Usage</SelectItem>
              <SelectItem value="business">Business</SelectItem>
              <SelectItem value="technical">Technical</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="metric-description">Description</Label>
        <Textarea
          id="metric-description"
          value={formData.description}
          onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
          placeholder="Describe what this metric measures"
          rows={3}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="metric-type">Type</Label>
          <Select value={formData.type} onValueChange={(value) => setFormData(prev => ({ ...prev, type: value as any }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="simple">Simple</SelectItem>
              <SelectItem value="composite">Composite</SelectItem>
              <SelectItem value="derived">Derived</SelectItem>
              <SelectItem value="calculated">Calculated</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="metric-aggregation">Aggregation</Label>
          <Select value={formData.aggregation} onValueChange={(value) => setFormData(prev => ({ ...prev, aggregation: value as any }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sum">Sum</SelectItem>
              <SelectItem value="average">Average</SelectItem>
              <SelectItem value="min">Minimum</SelectItem>
              <SelectItem value="max">Maximum</SelectItem>
              <SelectItem value="count">Count</SelectItem>
              <SelectItem value="percentile">Percentile</SelectItem>
              <SelectItem value="custom">Custom</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="metric-formula">Formula *</Label>
        <Textarea
          id="metric-formula"
          value={formData.formula}
          onChange={(e) => setFormData(prev => ({ ...prev, formula: e.target.value }))}
          placeholder="e.g., (answer_relevancy * 0.6) + (faithfulness * 0.4)"
          rows={3}
          required
        />
        <p className="text-xs text-gray-500 mt-1">
          Use data source names in your formula. Available operators: +, -, *, /, (, )
        </p>
      </div>

      <div>
        <Label htmlFor="metric-unit">Unit</Label>
        <Input
          id="metric-unit"
          value={formData.unit}
          onChange={(e) => setFormData(prev => ({ ...prev, unit: e.target.value }))}
          placeholder="e.g., %, ms, score, ratio"
        />
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Target & Thresholds</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="target-value">Target Value</Label>
            <Input
              id="target-value"
              type="number"
              value={formData.targetValue}
              onChange={(e) => setFormData(prev => ({ ...prev, targetValue: e.target.value }))}
              placeholder="e.g., 80"
            />
          </div>
          <div>
            <Label htmlFor="target-operator">Operator</Label>
            <Select value={formData.targetOperator} onValueChange={(value) => setFormData(prev => ({ ...prev, targetOperator: value as any }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gte">Greater than or equal</SelectItem>
                <SelectItem value="lte">Less than or equal</SelectItem>
                <SelectItem value="eq">Equal to</SelectItem>
                <SelectItem value="gt">Greater than</SelectItem>
                <SelectItem value="lt">Less than</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <Label htmlFor="warning-threshold">Warning Threshold</Label>
            <Input
              id="warning-threshold"
              type="number"
              value={formData.warningThreshold}
              onChange={(e) => setFormData(prev => ({ ...prev, warningThreshold: e.target.value }))}
              placeholder="e.g., 70"
            />
          </div>
          <div>
            <Label htmlFor="critical-threshold">Critical Threshold</Label>
            <Input
              id="critical-threshold"
              type="number"
              value={formData.criticalThreshold}
              onChange={(e) => setFormData(prev => ({ ...prev, criticalThreshold: e.target.value }))}
              placeholder="e.g., 60"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="schedule-enabled"
          checked={formData.scheduleEnabled}
          onCheckedChange={(checked) => setFormData(prev => ({ ...prev, scheduleEnabled: checked }))}
        />
        <Label htmlFor="schedule-enabled">Enable scheduled calculation</Label>
      </div>

      {formData.scheduleEnabled && (
        <div>
          <Label htmlFor="schedule-frequency">Frequency</Label>
          <Select value={formData.scheduleFrequency} onValueChange={(value) => setFormData(prev => ({ ...prev, scheduleFrequency: value as any }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="realtime">Real-time</SelectItem>
              <SelectItem value="hourly">Hourly</SelectItem>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      <div>
        <Label htmlFor="metric-tags">Tags</Label>
        <Input
          id="metric-tags"
          value={formData.tags}
          onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
          placeholder="e.g., quality, user-experience, important (comma-separated)"
        />
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Save className="h-4 w-4 mr-2" />
          {metric ? 'Update Metric' : 'Create Metric'}
        </Button>
      </div>
    </form>
  );
};

export default CustomMetricCreationTracking;