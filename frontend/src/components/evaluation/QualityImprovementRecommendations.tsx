/**
 * Quality Improvement Recommendations Component
 *
 * Provides intelligent recommendations for improving system quality based on
 * automated checks, human evaluation results, and performance metrics.
 * Uses AI-driven analysis to suggest specific improvements with priority scoring.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  LineChart,
  Line
} from 'recharts';
import {
  Lightbulb,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  Target,
  Brain,
  Zap,
  Shield,
  Users,
  Activity,
  BarChart3,
  Download,
  Play,
  Pause,
  RefreshCw,
  Filter,
  Search,
  ChevronRight,
  Info,
  ThumbsUp,
  ThumbsDown,
  Eye,
  GitBranch,
  Code,
  Database,
  Globe,
  Lock,
  MousePointer,
  Wrench
} from 'lucide-react';

// Types
interface QualityIssue {
  id: string;
  title: string;
  description: string;
  category: 'functional' | 'performance' | 'security' | 'accessibility' | 'usability' | 'compliance';
  severity: 'low' | 'medium' | 'high' | 'critical';
  impact: {
    users: number;
    business: number;
    technical: number;
  };
  detectedBy: 'automated' | 'human' | 'monitoring';
  detectedAt: string;
  source: string;
  frequency: number;
  relatedIssues: string[];
}

interface Recommendation {
  id: string;
  title: string;
  description: string;
  category: 'code' | 'architecture' | 'process' | 'tooling' | 'training' | 'infrastructure';
  priority: 'low' | 'medium' | 'high' | 'critical';
  effort: 'trivial' | 'small' | 'medium' | 'large' | 'xlarge';
  impact: {
    quality: number;
    performance: number;
    security: number;
    userExperience: number;
    business: number;
  };
  issues: string[];
  implementation: {
    steps: string[];
    estimatedHours: number;
    requiredSkills: string[];
    dependencies: string[];
    rollbackPlan: string;
  };
  validation: {
    successCriteria: string[];
    testingRequirements: string[];
    metrics: string[];
  };
  status: 'pending' | 'in_progress' | 'implemented' | 'validated' | 'rejected';
  assignedTo?: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  results?: {
    beforeMetrics: Record<string, number>;
    afterMetrics: Record<string, number>;
    improvement: number;
  };
}

interface QualityTrend {
  date: string;
  overall: number;
  functional: number;
  performance: number;
  security: number;
  accessibility: number;
  usability: number;
  compliance: number;
}

interface ImprovementMetric {
  category: string;
  before: number;
  after: number;
  improvement: number;
  target: number;
}

// Mock data generators
const generateQualityIssues = (): QualityIssue[] => [
  {
    id: 'issue-1',
    title: 'Slow search response times',
    description: 'Search queries are taking longer than 2 seconds on average, impacting user experience',
    category: 'performance',
    severity: 'high',
    impact: { users: 85, business: 70, technical: 60 },
    detectedBy: 'monitoring',
    detectedAt: '2025-01-18T09:15:00Z',
    source: 'performance-monitoring',
    frequency: 150,
    relatedIssues: ['issue-3', 'issue-7']
  },
  {
    id: 'issue-2',
    title: 'Missing alt text on images',
    description: 'Many uploaded images lack proper alternative text for screen readers',
    category: 'accessibility',
    severity: 'medium',
    impact: { users: 25, business: 40, technical: 30 },
    detectedBy: 'automated',
    detectedAt: '2025-01-18T08:30:00Z',
    source: 'accessibility-scanner',
    frequency: 45,
    relatedIssues: []
  },
  {
    id: 'issue-3',
    title: 'Inadequate input validation',
    description: 'API endpoints are not properly validating user input, potential security risk',
    category: 'security',
    severity: 'critical',
    impact: { users: 100, business: 95, technical: 90 },
    detectedBy: 'automated',
    detectedAt: '2025-01-18T07:45:00Z',
    source: 'security-scan',
    frequency: 12,
    relatedIssues: ['issue-8']
  },
  {
    id: 'issue-4',
    title: 'Inconsistent error messages',
    description: 'Error messages vary in format and clarity across the application',
    category: 'usability',
    severity: 'medium',
    impact: { users: 60, business: 35, technical: 40 },
    detectedBy: 'human',
    detectedAt: '2025-01-18T06:20:00Z',
    source: 'user-feedback',
    frequency: 28,
    relatedIssues: ['issue-6']
  },
  {
    id: 'issue-5',
    title: 'Database connection leaks',
    description: 'Database connections are not being properly closed, causing resource exhaustion',
    category: 'functional',
    severity: 'high',
    impact: { users: 70, business: 80, technical: 85 },
    detectedBy: 'monitoring',
    detectedAt: '2025-01-18T05:10:00Z',
    source: 'database-monitoring',
    frequency: 8,
    relatedIssues: []
  }
];

const generateRecommendations = (): Recommendation[] => [
  {
    id: 'rec-1',
    title: 'Implement search result caching',
    description: 'Add Redis-based caching for frequently accessed search results to improve response times',
    category: 'architecture',
    priority: 'high',
    effort: 'medium',
    impact: {
      quality: 70,
      performance: 90,
      security: 20,
      userExperience: 85,
      business: 75
    },
    issues: ['issue-1'],
    implementation: {
      steps: [
        'Set up Redis cluster for caching',
        'Implement cache-aside pattern in search service',
        'Add cache invalidation strategy',
        'Configure appropriate TTL values',
        'Add cache hit/miss metrics'
      ],
      estimatedHours: 24,
      requiredSkills: ['Redis', 'Node.js', 'System Design'],
      dependencies: ['Redis setup', 'Search service access'],
      rollbackPlan: 'Disable caching via feature flag, clear cache data'
    },
    validation: {
      successCriteria: [
        'Search response time < 500ms for cached queries',
        'Cache hit rate > 80%',
        'No stale data returned'
      ],
      testingRequirements: [
        'Load testing with cache enabled/disabled',
        'Cache invalidation testing',
        'Data consistency verification'
      ],
      metrics: ['response_time_p95', 'cache_hit_rate', 'error_rate']
    },
    status: 'pending',
    createdAt: '2025-01-18T10:00:00Z',
    updatedAt: '2025-01-18T10:00:00Z'
  },
  {
    id: 'rec-2',
    title: 'Add comprehensive input validation',
    description: 'Implement strict input validation across all API endpoints using a validation framework',
    category: 'code',
    priority: 'critical',
    effort: 'large',
    impact: {
      quality: 85,
      performance: 30,
      security: 95,
      userExperience: 60,
      business: 90
    },
    issues: ['issue-3'],
    implementation: {
      steps: [
        'Select and integrate validation library (Joi/Yup)',
        'Define validation schemas for all endpoints',
        'Implement validation middleware',
        'Add comprehensive error responses',
        'Update API documentation'
      ],
      estimatedHours: 40,
      requiredSkills: ['Node.js', 'Security', 'API Design'],
      dependencies: ['Validation library selection'],
      rollbackPlan: 'Remove validation middleware temporarily'
    },
    validation: {
      successCriteria: [
        'All inputs validated before processing',
        'Clear error messages for invalid inputs',
        'No security vulnerabilities from injection'
      ],
      testingRequirements: [
        'Security penetration testing',
        'Invalid input testing',
        'Error message clarity testing'
      ],
      metrics: ['security_score', 'input_validation_coverage', 'error_rate']
    },
    status: 'in_progress',
    assignedTo: 'security-team',
    createdAt: '2025-01-18T09:30:00Z',
    updatedAt: '2025-01-18T11:15:00Z'
  },
  {
    id: 'rec-3',
    title: 'Implement automatic alt text generation',
    description: 'Use AI to automatically generate alt text for images during upload',
    category: 'tooling',
    priority: 'medium',
    effort: 'small',
    impact: {
      quality: 60,
      performance: 40,
      security: 10,
      userExperience: 80,
      business: 50
    },
    issues: ['issue-2'],
    implementation: {
      steps: [
        'Integrate vision model API (GPT-4V/CLIP)',
        'Add alt text generation to upload pipeline',
        'Allow user review and editing of generated text',
        'Add fallback for generation failures'
      ],
      estimatedHours: 16,
      requiredSkills: ['AI/ML', 'API Integration', 'React'],
      dependencies: ['Vision model API access'],
      rollbackPlan: 'Disable automatic generation, keep manual input'
    },
    validation: {
      successCriteria: [
        '90% of images have alt text',
        'Generated text quality score > 7/10',
        'User satisfaction > 80%'
      ],
      testingRequirements: [
        'Alt text quality evaluation',
        'User acceptance testing',
        'Performance impact testing'
      ],
      metrics: ['alt_text_coverage', 'generation_quality_score', 'user_satisfaction']
    },
    status: 'pending',
    createdAt: '2025-01-18T11:00:00Z',
    updatedAt: '2025-01-18T11:00:00Z'
  }
];

const generateQualityTrends = (): QualityTrend[] => [
  { date: '2025-01-12', overall: 72, functional: 85, performance: 65, security: 78, accessibility: 60, usability: 75, compliance: 70 },
  { date: '2025-01-13', overall: 74, functional: 86, performance: 68, security: 80, accessibility: 62, usability: 76, compliance: 72 },
  { date: '2025-01-14', overall: 73, functional: 85, performance: 66, security: 79, accessibility: 64, usability: 77, compliance: 71 },
  { date: '2025-01-15', overall: 76, functional: 87, performance: 70, security: 82, accessibility: 67, usability: 79, compliance: 73 },
  { date: '2025-01-16', overall: 78, functional: 88, performance: 73, security: 84, accessibility: 69, usability: 81, compliance: 75 },
  { date: '2025-01-17', overall: 77, functional: 87, performance: 71, security: 83, accessibility: 70, usability: 80, compliance: 74 },
  { date: '2025-01-18', overall: 79, functional: 89, performance: 74, security: 85, accessibility: 72, usability: 82, compliance: 76 }
];

const generateImprovementMetrics = (): ImprovementMetric[] => [
  { category: 'Response Time', before: 2800, after: 450, improvement: 84, target: 500 },
  { category: 'Error Rate', before: 5.2, after: 1.1, improvement: 79, target: 1.0 },
  { category: 'Security Score', before: 65, after: 92, improvement: 42, target: 90 },
  { category: 'Accessibility', before: 45, after: 78, improvement: 73, target: 80 },
  { category: 'User Satisfaction', before: 3.2, after: 4.1, improvement: 28, target: 4.0 }
];

const QualityImprovementRecommendations: React.FC = () => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [issues, setIssues] = useState<QualityIssue[]>([]);
  const [trends, setTrends] = useState<QualityTrend[]>([]);
  const [improvements, setImprovements] = useState<ImprovementMetric[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState('recommendations');

  useEffect(() => {
    // Load data
    setRecommendations(generateRecommendations());
    setIssues(generateQualityIssues());
    setTrends(generateQualityTrends());
    setImprovements(generateImprovementMetrics());
  }, []);

  // Handler functions
  const handleGenerateRecommendations = () => {
    setIsGenerating(true);
    setTimeout(() => {
      // Simulate AI generation
      setRecommendations(generateRecommendations());
      setIsGenerating(false);
    }, 2000);
  };

  const handleUpdateStatus = (recId: string, newStatus: Recommendation['status']) => {
    setRecommendations(prev => prev.map(rec =>
      rec.id === recId
        ? { ...rec, status: newStatus, updatedAt: new Date().toISOString() }
        : rec
    ));
  };

  // Filter recommendations
  const filteredRecommendations = useMemo(() => {
    return recommendations.filter(rec => {
      const matchesCategory = selectedCategory === 'all' || rec.category === selectedCategory;
      const matchesPriority = selectedPriority === 'all' || rec.priority === selectedPriority;
      const matchesStatus = selectedStatus === 'all' || rec.status === selectedStatus;
      const matchesSearch = rec.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           rec.description.toLowerCase().includes(searchTerm.toLowerCase());

      return matchesCategory && matchesPriority && matchesStatus && matchesSearch;
    });
  }, [recommendations, selectedCategory, selectedPriority, selectedStatus, searchTerm]);

  // Calculate metrics
  const metrics = useMemo(() => {
    const total = recommendations.length;
    const byStatus = {
      pending: recommendations.filter(r => r.status === 'pending').length,
      inProgress: recommendations.filter(r => r.status === 'in_progress').length,
      implemented: recommendations.filter(r => r.status === 'implemented').length,
      validated: recommendations.filter(r => r.status === 'validated').length
    };

    const byPriority = {
      critical: recommendations.filter(r => r.priority === 'critical').length,
      high: recommendations.filter(r => r.priority === 'high').length,
      medium: recommendations.filter(r => r.priority === 'medium').length,
      low: recommendations.filter(r => r.priority === 'low').length
    };

    const avgImpactScore = recommendations.length > 0
      ? recommendations.reduce((sum, rec) => sum + (
          rec.impact.quality +
          rec.impact.performance +
          rec.impact.security +
          rec.impact.userExperience +
          rec.impact.business
        ) / 5, 0) / recommendations.length
      : 0;

    return {
      total,
      byStatus,
      byPriority,
      avgImpactScore: Math.round(avgImpactScore),
      implementationRate: total > 0 ? Math.round((byStatus.implemented + byStatus.validated) / total * 100) : 0
    };
  }, [recommendations]);

  // Priority colors
  const priorityColors = {
    critical: 'bg-red-500',
    high: 'bg-orange-500',
    medium: 'bg-yellow-500',
    low: 'bg-green-500'
  };

  const statusColors = {
    pending: 'bg-gray-500',
    in_progress: 'bg-blue-500',
    implemented: 'bg-purple-500',
    validated: 'bg-green-500',
    rejected: 'bg-red-500'
  };

  const categoryIcons = {
    code: Code,
    architecture: GitBranch,
    process: Wrench,
    tooling: Zap,
    training: Users,
    infrastructure: Database
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Quality Improvement Recommendations</h1>
          <p className="text-muted-foreground">
            AI-powered recommendations for system quality improvements
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleGenerateRecommendations}
            disabled={isGenerating}
            className="gap-2"
          >
            <Brain className="w-4 h-4" />
            {isGenerating ? 'Generating...' : 'Generate Recommendations'}
          </Button>
          <Button variant="outline" className="gap-2">
            <Download className="w-4 h-4" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Recommendations</CardTitle>
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total}</div>
            <p className="text-xs text-muted-foreground">
              {metrics.byStatus.pending} pending
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Implementation Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.implementationRate}%</div>
            <Progress value={metrics.implementationRate} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Critical Items</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{metrics.byPriority.critical}</div>
            <p className="text-xs text-muted-foreground">
              Require immediate attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Activity className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{metrics.byStatus.inProgress}</div>
            <p className="text-xs text-muted-foreground">
              Currently being implemented
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Impact Score</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.avgImpactScore}</div>
            <p className="text-xs text-muted-foreground">
              Out of 100
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
          <TabsTrigger value="trends">Quality Trends</TabsTrigger>
          <TabsTrigger value="improvements">Improvements</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="recommendations" className="space-y-4">
          {/* Filters */}
          <Card>
            <CardHeader>
              <CardTitle>Filters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-4">
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4" />
                  <input
                    type="text"
                    placeholder="Search recommendations..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="px-3 py-2 border rounded-md"
                  />
                </div>

                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="px-3 py-2 border rounded-md"
                >
                  <option value="all">All Categories</option>
                  <option value="code">Code</option>
                  <option value="architecture">Architecture</option>
                  <option value="process">Process</option>
                  <option value="tooling">Tooling</option>
                  <option value="training">Training</option>
                  <option value="infrastructure">Infrastructure</option>
                </select>

                <select
                  value={selectedPriority}
                  onChange={(e) => setSelectedPriority(e.target.value)}
                  className="px-3 py-2 border rounded-md"
                >
                  <option value="all">All Priorities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>

                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="px-3 py-2 border rounded-md"
                >
                  <option value="all">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="implemented">Implemented</option>
                  <option value="validated">Validated</option>
                </select>
              </div>
            </CardContent>
          </Card>

          {/* Recommendations List */}
          <div className="space-y-4">
            {filteredRecommendations.map((rec) => {
              const CategoryIcon = categoryIcons[rec.category];
              return (
                <Card key={rec.id} className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-blue-100 rounded-lg">
                        <CategoryIcon className="w-5 h-5 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-lg">{rec.title}</h3>
                        <p className="text-muted-foreground">{rec.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={`${priorityColors[rec.priority]} text-white`}>
                        {rec.priority}
                      </Badge>
                      <Badge className={`${statusColors[rec.status]} text-white`}>
                        {rec.status.replace('_', ' ')}
                      </Badge>
                    </div>
                  </div>

                  {/* Impact Scores */}
                  <div className="grid grid-cols-5 gap-4 mb-4">
                    <div className="text-center">
                      <div className="text-sm text-muted-foreground">Quality</div>
                      <div className="text-lg font-semibold">{rec.impact.quality}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-muted-foreground">Performance</div>
                      <div className="text-lg font-semibold">{rec.impact.performance}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-muted-foreground">Security</div>
                      <div className="text-lg font-semibold">{rec.impact.security}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-muted-foreground">User Exp</div>
                      <div className="text-lg font-semibold">{rec.impact.userExperience}</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm text-muted-foreground">Business</div>
                      <div className="text-lg font-semibold">{rec.impact.business}</div>
                    </div>
                  </div>

                  {/* Implementation Details */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div>
                      <h4 className="font-medium mb-2">Implementation</h4>
                      <div className="text-sm text-muted-foreground space-y-1">
                        <div>Effort: <span className="font-medium">{rec.effort}</span></div>
                        <div>Estimated Hours: <span className="font-medium">{rec.implementation.estimatedHours}h</span></div>
                        <div>Steps: <span className="font-medium">{rec.implementation.steps.length}</span></div>
                      </div>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2">Affected Issues</h4>
                      <div className="flex flex-wrap gap-1">
                        {rec.issues.map(issueId => (
                          <Badge key={issueId} variant="outline" className="text-xs">
                            {issueId}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-muted-foreground">
                      Created: {new Date(rec.createdAt).toLocaleDateString()}
                      {rec.assignedTo && ` • Assigned to: ${rec.assignedTo}`}
                    </div>
                    <div className="flex gap-2">
                      {rec.status === 'pending' && (
                        <Button
                          size="sm"
                          onClick={() => handleUpdateStatus(rec.id, 'in_progress')}
                        >
                          Start Implementation
                        </Button>
                      )}
                      {rec.status === 'in_progress' && (
                        <Button
                          size="sm"
                          onClick={() => handleUpdateStatus(rec.id, 'implemented')}
                        >
                          Mark Complete
                        </Button>
                      )}
                      {rec.status === 'implemented' && (
                        <Button
                          size="sm"
                          onClick={() => handleUpdateStatus(rec.id, 'validated')}
                        >
                          Validate Results
                        </Button>
                      )}
                      <Button size="sm" variant="outline">
                        View Details
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Quality Trend Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Quality Score Trends</CardTitle>
                <CardDescription>Overall quality metrics over time</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trends}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="overall" stroke="#8884d8" strokeWidth={2} />
                    <Line type="monotone" dataKey="functional" stroke="#82ca9d" />
                    <Line type="monotone" dataKey="performance" stroke="#ffc658" />
                    <Line type="monotone" dataKey="security" stroke="#ff7300" />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Category Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle>Current Quality Breakdown</CardTitle>
                <CardDescription>Quality scores by category</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={trends[trends.length - 1] ? [{
                    category: 'Functional',
                    value: trends[trends.length - 1]?.functional || 0,
                    fullMark: 100
                  }, {
                    category: 'Performance',
                    value: trends[trends.length - 1]?.performance || 0,
                    fullMark: 100
                  }, {
                    category: 'Security',
                    value: trends[trends.length - 1]?.security || 0,
                    fullMark: 100
                  }, {
                    category: 'Accessibility',
                    value: trends[trends.length - 1]?.accessibility || 0,
                    fullMark: 100
                  }, {
                    category: 'Usability',
                    value: trends[trends.length - 1]?.usability || 0,
                    fullMark: 100
                  }, {
                    category: 'Compliance',
                    value: trends[trends.length - 1]?.compliance || 0,
                    fullMark: 100
                  }] : []}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="category" />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} />
                    <Radar dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={0.6} />
                  </RadarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="improvements" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Improvement Metrics */}
            <Card>
              <CardHeader>
                <CardTitle>Improvement Metrics</CardTitle>
                <CardDescription>Before and after comparisons</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={improvements}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="category" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="before" fill="#ff7300" />
                    <Bar dataKey="after" fill="#82ca9d" />
                    <Bar dataKey="target" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Implementation Success */}
            <Card>
              <CardHeader>
                <CardTitle>Implementation Success Rate</CardTitle>
                <CardDescription>Completion rates by category</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'Validated', value: metrics.byStatus.validated, fill: '#82ca9d' },
                        { name: 'Implemented', value: metrics.byStatus.implemented, fill: '#8884d8' },
                        { name: 'In Progress', value: metrics.byStatus.inProgress, fill: '#ffc658' },
                        { name: 'Pending', value: metrics.byStatus.pending, fill: '#ff7300' }
                      ]}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label
                    />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Recent Improvements */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Improvements</CardTitle>
              <CardDescription>Latest implemented recommendations and their results</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {improvements.map((improvement, index) => (
                  <div key={index} className="flex items-center justify-between p-4 border rounded-lg">
                    <div>
                      <h4 className="font-medium">{improvement.category}</h4>
                      <div className="text-sm text-muted-foreground">
                        Before: {improvement.before} → After: {improvement.after}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-semibold text-green-600">
                        +{improvement.improvement}%
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Target: {improvement.target}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analysis" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Issue Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Issue Distribution</CardTitle>
                <CardDescription>Quality issues by category and severity</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {['functional', 'performance', 'security', 'accessibility', 'usability', 'compliance'].map(category => {
                    const categoryIssues = issues.filter(issue => issue.category === category);
                    const criticalCount = categoryIssues.filter(issue => issue.severity === 'critical').length;
                    const highCount = categoryIssues.filter(issue => issue.severity === 'high').length;

                    return (
                      <div key={category} className="space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="font-medium capitalize">{category}</span>
                          <span className="text-sm text-muted-foreground">
                            {categoryIssues.length} issues
                          </span>
                        </div>
                        <div className="flex gap-2">
                          <div className="flex-1">
                            <div className="h-2 bg-red-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-red-500"
                                style={{ width: `${(criticalCount / Math.max(categoryIssues.length, 1)) * 100}%` }}
                              />
                            </div>
                          </div>
                          <div className="flex-1">
                            <div className="h-2 bg-orange-100 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-orange-500"
                                style={{ width: `${(highCount / Math.max(categoryIssues.length, 1)) * 100}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Recommendations Analysis */}
            <Card>
              <CardHeader>
                <CardTitle>Recommendations Analysis</CardTitle>
                <CardDescription>AI insights and patterns</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Alert>
                    <Brain className="h-4 w-4" />
                    <AlertTitle>Pattern Detection</AlertTitle>
                    <AlertDescription>
                      Analysis shows 70% of performance issues are related to database query optimization.
                    </AlertDescription>
                  </Alert>

                  <Alert>
                    <Target className="h-4 w-4" />
                    <AlertTitle>High Impact Opportunities</AlertTitle>
                    <AlertDescription>
                      Security improvements show the highest business impact with moderate implementation effort.
                    </AlertDescription>
                  </Alert>

                  <Alert>
                    <TrendingUp className="h-4 w-4" />
                    <AlertTitle>Trending Improvements</AlertTitle>
                    <AlertDescription>
                      Accessibility improvements have increased by 40% following automated alt-text generation.
                    </AlertDescription>
                  </Alert>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default QualityImprovementRecommendations;