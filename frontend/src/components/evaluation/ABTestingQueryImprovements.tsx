import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  FlaskConical,
  TrendingUp,
  Users,
  BarChart3,
  Clock,
  CheckCircle,
  AlertTriangle,
  Play,
  Pause,
  Square,
  RotateCcw,
  Target,
  Zap,
  Database,
  Search,
  Filter,
  Settings,
  FileText,
  ChevronRight,
  Info,
  ArrowUp,
  ArrowDown,
  Minus,
  Eye,
  EyeOff,
  Download,
  Upload,
  Calendar,
  Gauge,
} from 'lucide-react';

interface ABTest {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'running' | 'paused' | 'completed' | 'cancelled';
  type:
    | 'query_algorithm'
    | 'ranking_model'
    | 'retrieval_strategy'
    | 'response_generation'
    | 'ui_interface';
  hypothesis: string;
  variants: {
    control: {
      name: string;
      description: string;
      config: Record<string, any>;
    };
    treatment: {
      name: string;
      description: string;
      config: Record<string, any>;
    };
  };
  targeting: {
    userSegments: string[];
    queryTypes: string[];
    trafficSplit: number;
    sampleSize: number;
  };
  metrics: {
    primary: string;
    secondary: string[];
    thresholds: {
      minimumDetectableEffect: number;
      statisticalSignificance: number;
      power: number;
    };
  };
  duration: {
    startDate: string;
    endDate: string;
    estimatedDuration: string;
  };
  results?: {
    sampleSize: number;
    controlMetrics: Record<string, number>;
    treatmentMetrics: Record<string, number>;
    statisticalSignificance: Record<string, number>;
    confidence: number;
    winner: 'control' | 'treatment' | 'inconclusive';
    recommendation: string;
  };
  createdAt: string;
  updatedAt: string;
  createdBy: string;
}

interface TestMetric {
  name: string;
  current: number;
  target: number;
  unit: string;
  description: string;
}

interface TestSegment {
  id: string;
  name: string;
  description: string;
  size: number;
  criteria: Record<string, any>;
}

const mockTests: ABTest[] = [
  {
    id: 'test-001',
    name: 'Hybrid Search vs Vector Search',
    description:
      'Compare hybrid search performance against pure vector search for complex queries',
    status: 'running',
    type: 'retrieval_strategy',
    hypothesis:
      'Hybrid search combining vector and keyword search will improve answer relevancy by 10% for complex queries',
    variants: {
      control: {
        name: 'Pure Vector Search',
        description: 'Current implementation using only vector similarity',
        config: {
          algorithm: 'cosine_similarity',
          topK: 10,
          reranking: false,
        },
      },
      treatment: {
        name: 'Hybrid Search',
        description: 'Combined vector + keyword search with reranking',
        config: {
          algorithm: 'hybrid_alpha_beta',
          vectorWeight: 0.7,
          keywordWeight: 0.3,
          reranking: true,
          topK: 15,
        },
      },
    },
    targeting: {
      userSegments: ['power_users', 'enterprise'],
      queryTypes: ['complex', 'multi_hop', 'reasoning'],
      trafficSplit: 50,
      sampleSize: 5000,
    },
    metrics: {
      primary: 'answer_relevancy',
      secondary: ['response_time', 'user_satisfaction', 'context_precision'],
      thresholds: {
        minimumDetectableEffect: 5,
        statisticalSignificance: 95,
        power: 80,
      },
    },
    duration: {
      startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      endDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      estimatedDuration: '2 weeks',
    },
    createdAt: '2025-01-14T10:30:00Z',
    updatedAt: '2025-01-18T14:20:00Z',
    createdBy: 'Search Team',
  },
  {
    id: 'test-002',
    name: 'GPT-4 vs Claude for Response Generation',
    description:
      'Evaluate different LLM models for final response generation quality',
    status: 'completed',
    type: 'response_generation',
    hypothesis:
      'Claude will provide more accurate and contextually relevant responses compared to GPT-4',
    variants: {
      control: {
        name: 'GPT-4 Turbo',
        description: 'Current GPT-4 Turbo model with temperature 0.3',
        config: {
          model: 'gpt-4-turbo',
          temperature: 0.3,
          maxTokens: 2000,
          systemPrompt: 'current_system_prompt',
        },
      },
      treatment: {
        name: 'Claude 3.5 Sonnet',
        description: 'Claude 3.5 Sonnet with temperature 0.2',
        config: {
          model: 'claude-3-5-sonnet',
          temperature: 0.2,
          maxTokens: 2000,
          systemPrompt: 'current_system_prompt',
        },
      },
    },
    targeting: {
      userSegments: ['all_users'],
      queryTypes: ['factual', 'explanatory', 'procedural'],
      trafficSplit: 50,
      sampleSize: 3000,
    },
    metrics: {
      primary: 'answer_relevancy',
      secondary: ['faithfulness', 'response_time', 'user_rating'],
      thresholds: {
        minimumDetectableEffect: 3,
        statisticalSignificance: 95,
        power: 80,
      },
    },
    duration: {
      startDate: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
      endDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      estimatedDuration: '1 week',
    },
    results: {
      sampleSize: 3247,
      controlMetrics: {
        answer_relevancy: 71.2,
        faithfulness: 86.5,
        response_time: 1850,
        user_rating: 3.8,
      },
      treatmentMetrics: {
        answer_relevancy: 75.8,
        faithfulness: 89.2,
        response_time: 1720,
        user_rating: 4.1,
      },
      statisticalSignificance: {
        answer_relevancy: 97.3,
        faithfulness: 94.1,
        response_time: 88.7,
        user_rating: 91.5,
      },
      confidence: 95,
      winner: 'treatment',
      recommendation:
        'Claude 3.5 Sonnet shows statistically significant improvement across all metrics. Recommend full rollout.',
    },
    createdAt: '2025-01-07T09:15:00Z',
    updatedAt: '2025-01-16T11:30:00Z',
    createdBy: 'ML Team',
  },
  {
    id: 'test-003',
    name: 'Query Rewriting Enhancement',
    description:
      'Test AI-powered query rewriting to improve search understanding',
    status: 'draft',
    type: 'query_algorithm',
    hypothesis:
      'AI-powered query rewriting will improve contextual relevancy by 8% for ambiguous queries',
    variants: {
      control: {
        name: 'Direct Query',
        description: 'Current direct query processing',
        config: {
          rewriting: false,
          expansion: false,
        },
      },
      treatment: {
        name: 'AI Rewritten Query',
        description: 'GPT-3.5 powered query rewriting and expansion',
        config: {
          rewriting: true,
          expansion: true,
          model: 'gpt-3.5-turbo',
          temperature: 0.1,
        },
      },
    },
    targeting: {
      userSegments: ['all_users'],
      queryTypes: ['ambiguous', 'short', 'conversational'],
      trafficSplit: 50,
      sampleSize: 4000,
    },
    metrics: {
      primary: 'contextual_relevancy',
      secondary: [
        'answer_relevancy',
        'query_success_rate',
        'user_satisfaction',
      ],
      thresholds: {
        minimumDetectableEffect: 5,
        statisticalSignificance: 95,
        power: 80,
      },
    },
    duration: {
      startDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      endDate: new Date(Date.now() + 21 * 24 * 60 * 60 * 1000).toISOString(),
      estimatedDuration: '2 weeks',
    },
    createdAt: '2025-01-18T16:45:00Z',
    updatedAt: '2025-01-18T16:45:00Z',
    createdBy: 'Search Team',
  },
];

const mockMetrics: TestMetric[] = [
  {
    name: 'answer_relevancy',
    current: 71.2,
    target: 75.0,
    unit: '%',
    description: 'Relevance of generated answers to user queries',
  },
  {
    name: 'faithfulness',
    current: 86.5,
    target: 90.0,
    unit: '%',
    description: 'Factual accuracy of responses based on source material',
  },
  {
    name: 'response_time',
    current: 1850,
    target: 1500,
    unit: 'ms',
    description: 'Average time to generate complete response',
  },
  {
    name: 'user_satisfaction',
    current: 3.8,
    target: 4.2,
    unit: 'rating',
    description: 'Average user satisfaction rating (1-5 scale)',
  },
];

const mockSegments: TestSegment[] = [
  {
    id: 'seg-001',
    name: 'Power Users',
    description: 'Users with >50 queries per month',
    size: 1250,
    criteria: { queryFrequency: '>50', userType: 'registered' },
  },
  {
    id: 'seg-002',
    name: 'Enterprise',
    description: 'Enterprise plan users',
    size: 850,
    criteria: { plan: 'enterprise', companySize: '>100' },
  },
  {
    id: 'seg-003',
    name: 'New Users',
    description: 'Users registered within last 30 days',
    size: 2100,
    criteria: { registrationDate: '<30_days', usageLevel: 'low' },
  },
];

export default function ABTestingQueryImprovements() {
  const [tests, setTests] = useState<ABTest[]>(mockTests);
  const [selectedTest, setSelectedTest] = useState<ABTest | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [metrics] = useState<TestMetric[]>(mockMetrics);
  const [segments] = useState<TestSegment[]>(mockSegments);

  const statusColors = {
    draft: 'bg-gray-100 text-foreground',
    running: 'bg-blue-100 text-blue-700',
    paused: 'bg-yellow-100 text-yellow-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-red-100 text-red-700',
  };

  const typeColors = {
    query_algorithm: 'bg-purple-100 text-purple-700',
    ranking_model: 'bg-blue-100 text-blue-700',
    retrieval_strategy: 'bg-green-100 text-green-700',
    response_generation: 'bg-orange-100 text-orange-700',
    ui_interface: 'bg-pink-100 text-pink-700',
  };

  const getProgressPercentage = (test: ABTest) => {
    if (test.status === 'completed') return 100;
    if (test.status === 'draft') return 0;
    if (test.status === 'cancelled') return 0;

    const start = new Date(test.duration.startDate).getTime();
    const end = new Date(test.duration.endDate).getTime();
    const now = Date.now();

    if (now < start) return 0;
    if (now > end) return 100;

    return Math.round(((now - start) / (end - start)) * 100);
  };

  const getTestWinner = (test: ABTest) => {
    if (!test.results) return null;
    if (test.results.winner === 'treatment')
      return test.variants.treatment.name;
    if (test.results.winner === 'control') return test.variants.control.name;
    return 'Inconclusive';
  };

  const getMetricChange = (control: number, treatment: number) => {
    // Guard against divide-by-zero
    if (control === 0 || !Number.isFinite(control)) {
      return {
        value: 'N/A',
        isPositive: false,
        isNeutral: true,
      };
    }

    const change = ((treatment - control) / control) * 100;

    if (!Number.isFinite(change)) {
      return {
        value: 'N/A',
        isPositive: false,
        isNeutral: true,
      };
    }

    return {
      value: change.toFixed(1),
      isPositive: change > 0,
      isNeutral: change === 0,
    };
  };

  const stats = {
    total: tests.length,
    running: tests.filter((t) => t.status === 'running').length,
    completed: tests.filter((t) => t.status === 'completed').length,
    draft: tests.filter((t) => t.status === 'draft').length,
    avgDuration: '2.1 weeks',
    totalParticipants: tests.reduce(
      (acc, t) => acc + (t.results?.sampleSize || t.targeting.sampleSize),
      0
    ),
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            A/B Testing for Query Improvements
          </h1>
          <p className="text-foreground">
            Controlled experiments for optimizing search and response quality
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export Results
          </Button>
          <Button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2"
          >
            <FlaskConical className="h-4 w-4" />
            New Test
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{stats.total}</p>
                <p className="text-xs text-foreground">Total Tests</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Play className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{stats.running}</p>
                <p className="text-xs text-foreground">Running</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-purple-500" />
              <div>
                <p className="text-2xl font-bold">{stats.completed}</p>
                <p className="text-xs text-foreground">Completed</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{stats.draft}</p>
                <p className="text-xs text-foreground">Draft</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-orange-500" />
              <div>
                <p className="text-2xl font-bold">{stats.avgDuration}</p>
                <p className="text-xs text-foreground">Avg Duration</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-500" />
              <div>
                <p className="text-2xl font-bold">
                  {stats.totalParticipants.toLocaleString()}
                </p>
                <p className="text-xs text-foreground">Participants</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-4"
      >
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="active">Active Tests</TabsTrigger>
          <TabsTrigger value="results">Results Analysis</TabsTrigger>
          <TabsTrigger value="segments">Segments</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Recent Tests */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent A/B Tests</CardTitle>
              <CardDescription>
                Latest experiments and their current status
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {tests.map((test) => (
                  <div key={test.id} className="p-4 border rounded-lg">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <CardTitle className="text-base">
                            {test.name}
                          </CardTitle>
                          <Badge className={statusColors[test.status]}>
                            {test.status.toUpperCase()}
                          </Badge>
                          <Badge className={typeColors[test.type]}>
                            {test.type.replace(/_/g, ' ').toUpperCase()}
                          </Badge>
                        </div>
                        <CardDescription className="text-sm">
                          {test.description}
                        </CardDescription>
                        <div className="text-sm text-foreground">
                          <strong>Hypothesis:</strong> {test.hypothesis}
                        </div>
                        <div className="flex flex-wrap gap-4 text-sm text-foreground">
                          <div>
                            <strong>Duration:</strong>{' '}
                            {test.duration.estimatedDuration}
                          </div>
                          <div>
                            <strong>Sample Size:</strong>{' '}
                            {test.targeting.sampleSize.toLocaleString()}
                          </div>
                          <div>
                            <strong>Traffic Split:</strong>{' '}
                            {test.targeting.trafficSplit}/
                            {100 - test.targeting.trafficSplit}
                          </div>
                        </div>
                      </div>
                      <div className="text-right space-y-2">
                        {test.status === 'running' && (
                          <div>
                            <Progress
                              value={getProgressPercentage(test)}
                              className="w-20 h-2"
                            />
                            <div className="text-xs text-foreground mt-1">
                              {getProgressPercentage(test)}% complete
                            </div>
                          </div>
                        )}
                        {test.results && (
                          <div className="text-sm">
                            <div className="font-medium text-green-600">
                              Winner: {getTestWinner(test)}
                            </div>
                            <div className="text-foreground">
                              {test.results.confidence}% confidence
                            </div>
                          </div>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedTest(test)}
                        >
                          View Details
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="active" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Active Tests</CardTitle>
              <CardDescription>
                Tests currently running and collecting data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {tests
                  .filter((t) => t.status === 'running')
                  .map((test) => (
                    <Card
                      key={test.id}
                      className="border border-[var(--nous-sol)]/40"
                    >
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <div>
                            <CardTitle className="text-base">
                              {test.name}
                            </CardTitle>
                            <CardDescription>
                              {test.description}
                            </CardDescription>
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm">
                              <Pause className="h-4 w-4" />
                            </Button>
                            <Button variant="outline" size="sm">
                              <Square className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <h4 className="font-medium mb-2">
                              Control Variant
                            </h4>
                            <div className="text-sm space-y-1">
                              <div>
                                <strong>Name:</strong>{' '}
                                {test.variants.control.name}
                              </div>
                              <div>
                                <strong>Description:</strong>{' '}
                                {test.variants.control.description}
                              </div>
                            </div>
                          </div>
                          <div>
                            <h4 className="font-medium mb-2">
                              Treatment Variant
                            </h4>
                            <div className="text-sm space-y-1">
                              <div>
                                <strong>Name:</strong>{' '}
                                {test.variants.treatment.name}
                              </div>
                              <div>
                                <strong>Description:</strong>{' '}
                                {test.variants.treatment.description}
                              </div>
                            </div>
                          </div>
                        </div>
                        <div className="mt-4 p-3 bg-blue-50 rounded">
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="font-medium">Test Progress</div>
                              <div className="text-sm text-foreground">
                                Started:{' '}
                                {new Date(
                                  test.duration.startDate
                                ).toLocaleDateString()}
                              </div>
                            </div>
                            <div className="text-right">
                              <Progress
                                value={getProgressPercentage(test)}
                                className="w-24 h-2"
                              />
                              <div className="text-sm text-foreground mt-1">
                                {getProgressPercentage(test)}% complete
                              </div>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="results" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Test Results Analysis</CardTitle>
              <CardDescription>
                Statistical analysis and insights from completed tests
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {tests
                  .filter((t) => t.status === 'completed' && t.results)
                  .map((test) => (
                    <div key={test.id} className="p-4 border rounded-lg">
                      <div className="mb-4">
                        <div className="flex items-center justify-between">
                          <h3 className="text-lg font-medium">{test.name}</h3>
                          <div className="text-right">
                            <Badge className="bg-green-100 text-green-700">
                              {getTestWinner(test)}
                            </Badge>
                            <div className="text-sm text-foreground mt-1">
                              {test.results!.confidence}% confidence
                            </div>
                          </div>
                        </div>
                        <p className="text-foreground">{test.description}</p>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                        <div className="p-3 bg-gray-50 rounded">
                          <h4 className="font-medium mb-2">
                            Control: {test.variants.control.name}
                          </h4>
                          <div className="space-y-2">
                            {Object.entries(test.results!.controlMetrics).map(
                              ([metric, value]) => (
                                <div
                                  key={metric}
                                  className="flex justify-between text-sm"
                                >
                                  <span>{metric.replace(/_/g, ' ')}:</span>
                                  <span className="font-medium">
                                    {metric.includes('time')
                                      ? `${value}ms`
                                      : metric.includes('rating')
                                        ? value.toFixed(1)
                                        : `${value}%`}
                                  </span>
                                </div>
                              )
                            )}
                          </div>
                        </div>
                        <div className="p-3 bg-blue-50 rounded">
                          <h4 className="font-medium mb-2">
                            Treatment: {test.variants.treatment.name}
                          </h4>
                          <div className="space-y-2">
                            {Object.entries(test.results!.treatmentMetrics).map(
                              ([metric, value]) => {
                                const control =
                                  test.results!.controlMetrics[metric];
                                const change = getMetricChange(
                                  control ?? 0,
                                  value
                                );
                                return (
                                  <div
                                    key={metric}
                                    className="flex justify-between text-sm"
                                  >
                                    <span>{metric.replace(/_/g, ' ')}:</span>
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium">
                                        {metric.includes('time')
                                          ? `${value}ms`
                                          : metric.includes('rating')
                                            ? value.toFixed(1)
                                            : `${value}%`}
                                      </span>
                                      {change.isPositive && (
                                        <ArrowUp className="h-3 w-3 text-green-500" />
                                      )}
                                      {change.isNeutral && (
                                        <Minus className="h-3 w-3 text-muted-foreground" />
                                      )}
                                      {!change.isPositive &&
                                        !change.isNeutral && (
                                          <ArrowDown className="h-3 w-3 text-red-500" />
                                        )}
                                      <span
                                        className={`text-xs ${change.isPositive ? 'text-green-600' : change.isNeutral ? 'text-foreground' : 'text-red-600'}`}
                                      >
                                        {change.value}%
                                      </span>
                                    </div>
                                  </div>
                                );
                              }
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="p-3 bg-green-50 rounded">
                        <h4 className="font-medium mb-1">Recommendation</h4>
                        <p className="text-sm text-green-800">
                          {test.results!.recommendation}
                        </p>
                      </div>

                      <div className="mt-4 pt-4 border-t">
                        <div className="flex items-center justify-between text-sm text-foreground">
                          <div>
                            Sample Size:{' '}
                            {test.results!.sampleSize.toLocaleString()}
                          </div>
                          <div>
                            Test Duration: {test.duration.estimatedDuration}
                          </div>
                          <div>
                            Statistical Significance:{' '}
                            {test.metrics.thresholds.statisticalSignificance}%
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="segments" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Test Segments</CardTitle>
              <CardDescription>
                User segments and query types for targeted testing
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {segments.map((segment) => (
                  <Card key={segment.id}>
                    <CardHeader>
                      <CardTitle className="text-base">
                        {segment.name}
                      </CardTitle>
                      <CardDescription>{segment.description}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm text-foreground">Size:</span>
                          <span className="font-medium">
                            {segment.size.toLocaleString()} users
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          <div>Criteria:</div>
                          {Object.entries(segment.criteria).map(
                            ([key, value]) => (
                              <div key={key}>
                                • {key}: {value}
                              </div>
                            )
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Available Metrics</CardTitle>
              <CardDescription>
                Metrics that can be used as primary or secondary test objectives
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {metrics.map((metric) => (
                  <div key={metric.name} className="p-3 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium">
                        {metric.name.replace(/_/g, ' ')}
                      </h4>
                      <Badge variant="outline">{metric.unit}</Badge>
                    </div>
                    <p className="text-sm text-foreground mt-1">
                      {metric.description}
                    </p>
                    <div className="flex justify-between mt-2 text-sm">
                      <span>
                        Current: {metric.current}
                        {metric.unit.includes('%')
                          ? '%'
                          : metric.unit.includes('ms')
                            ? 'ms'
                            : metric.unit.includes('rating')
                              ? ''
                              : ''}
                      </span>
                      <span>
                        Target: {metric.target}
                        {metric.unit.includes('%')
                          ? '%'
                          : metric.unit.includes('ms')
                            ? 'ms'
                            : metric.unit.includes('rating')
                              ? ''
                              : ''}
                      </span>
                    </div>
                    <Progress
                      value={(() => {
                        const isLowerBetter =
                          metric.unit.includes('ms') ||
                          metric.name.includes('response_time');
                        const target = metric.target === 0 ? 1 : metric.target;
                        const current = metric.current;

                        // Guard against zero current value
                        if (current === 0) {
                          return isLowerBetter ? 100 : 0;
                        }

                        const rawProgress = isLowerBetter
                          ? (target / current) * 100
                          : (current / target) * 100;
                        return Math.max(0, Math.min(100, rawProgress));
                      })()}
                      className="mt-2 h-2"
                    />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Test Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <CardTitle>Create New A/B Test</CardTitle>
              <CardDescription>
                Set up a new controlled experiment
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="testName">Test Name</Label>
                <Input id="testName" placeholder="Enter test name" />
              </div>
              <div>
                <Label htmlFor="testDescription">Description</Label>
                <Textarea
                  id="testDescription"
                  placeholder="Describe the test purpose"
                />
              </div>
              <div>
                <Label htmlFor="testType">Test Type</Label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select test type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="query_algorithm">
                      Query Algorithm
                    </SelectItem>
                    <SelectItem value="ranking_model">Ranking Model</SelectItem>
                    <SelectItem value="retrieval_strategy">
                      Retrieval Strategy
                    </SelectItem>
                    <SelectItem value="response_generation">
                      Response Generation
                    </SelectItem>
                    <SelectItem value="ui_interface">UI Interface</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="hypothesis">Hypothesis</Label>
                <Textarea
                  id="hypothesis"
                  placeholder="State your test hypothesis"
                />
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setShowCreateForm(false)}
                >
                  Cancel
                </Button>
                <Button onClick={() => setShowCreateForm(false)}>
                  Create Test
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
