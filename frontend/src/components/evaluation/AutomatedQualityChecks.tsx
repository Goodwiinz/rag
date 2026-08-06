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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
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
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Play,
  Pause,
  RefreshCw,
  Settings,
  Plus,
  Edit,
  Trash2,
  Eye,
  Filter,
  Search,
  Info,
  Shield,
  Zap,
  Target,
  Activity,
  TrendingUp,
  TrendingDown,
  FileCheck,
  Code,
  Bug,
  Database,
  Globe,
  Lock,
  UserCheck,
  ChevronDown,
  ChevronUp,
  Calendar,
  BarChart3,
} from 'lucide-react';

// Component Props Interfaces
interface AutomatedQualityChecksProps {
  onCheckCreate?: (check: QualityCheck) => void;
  onCheckUpdate?: (check: QualityCheck) => void;
  onCheckDelete?: (checkId: string) => void;
  onCheckRun?: (checkId: string) => void;
  className?: string;
}

interface QualityCheckFormProps {
  check?: QualityCheck | null;
  onSubmit: (check: Partial<QualityCheck>) => void;
  onCancel: () => void;
}

// Types
interface QualityCheck {
  id: string;
  name: string;
  description: string;
  category:
    | 'functional'
    | 'performance'
    | 'security'
    | 'accessibility'
    | 'usability'
    | 'compliance';
  type: 'automated' | 'manual' | 'hybrid';
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'active' | 'inactive' | 'deprecated';
  schedule: {
    enabled: boolean;
    frequency: 'on_demand' | 'hourly' | 'daily' | 'weekly' | 'continuous';
    timezone: string;
  };
  rules: {
    conditions: QualityCondition[];
    passThreshold: number; // percentage
    failThreshold: number; // percentage
    maxExecutionTime: number; // seconds
  };
  scope: {
    components: string[];
    userFlows: string[];
    environments: string[];
  };
  notifications: {
    onPass: boolean;
    onFail: boolean;
    onWarning: boolean;
    recipients: string[];
    channels: ('email' | 'slack' | 'webhook' | 'in_app')[];
  };
  integration: {
    tools: string[];
    apis: string[];
    scripts: string[];
  };
  metadata: {
    created: string;
    updated: string;
    createdBy: string;
    lastRun?: string;
    version: string;
    tags: string[];
  };
}

interface QualityCondition {
  id: string;
  name: string;
  type:
    | 'metric_threshold'
    | 'pattern_match'
    | 'code_analysis'
    | 'security_scan'
    | 'accessibility_test'
    | 'performance_test';
  operator:
    | 'eq'
    | 'ne'
    | 'gt'
    | 'gte'
    | 'lt'
    | 'lte'
    | 'contains'
    | 'not_contains'
    | 'matches';
  target: any;
  weight: number; // 0-1
  enabled: boolean;
}

interface QualityCheckResult {
  id: string;
  checkId: string;
  checkName: string;
  category: QualityCheck['category'];
  status: 'passed' | 'failed' | 'warning' | 'error' | 'skipped';
  score: number; // 0-100
  duration: number; // seconds
  timestamp: string;
  environment: string;
  version: string;
  results: {
    totalConditions: number;
    passedConditions: number;
    failedConditions: number;
    warningConditions: number;
    details: ConditionResult[];
  };
  metrics: {
    [key: string]: number;
  };
  artifacts: {
    reports: string[];
    screenshots: string[];
    logs: string[];
  };
  issues: QualityIssue[];
  recommendations: QualityRecommendation[];
}

interface ConditionResult {
  conditionId: string;
  conditionName: string;
  status: 'passed' | 'failed' | 'warning' | 'error';
  score: number;
  actualValue: any;
  expectedValue: any;
  message: string;
  details?: any;
}

interface QualityIssue {
  id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  category: string;
  component?: string;
  file?: string;
  line?: number;
  recommendation?: string;
  status: 'open' | 'in_progress' | 'resolved' | 'dismissed';
  createdAt: string;
  resolvedAt?: string;
  resolvedBy?: string;
}

interface QualityRecommendation {
  id: string;
  type: 'improvement' | 'fix' | 'optimization' | 'refactor';
  priority: 'low' | 'medium' | 'high';
  title: string;
  description: string;
  impact: string;
  effort: 'low' | 'medium' | 'high';
  category: string;
  resources: {
    documentation: string[];
    examples: string[];
    tools: string[];
  };
}

interface QualityDashboard {
  timeRange: '1d' | '7d' | '30d' | '90d';
  summary: {
    totalChecks: number;
    passedChecks: number;
    failedChecks: number;
    warningChecks: number;
    averageScore: number;
    totalIssues: number;
    criticalIssues: number;
  };
  trends: {
    scoresByTime: Array<{
      timestamp: string;
      functional: number;
      performance: number;
      security: number;
      accessibility: number;
      usability: number;
      compliance: number;
    }>;
    issuesByCategory: Array<{
      category: string;
      count: number;
      severity: string;
    }>;
    checkPerformance: Array<{
      checkName: string;
      averageScore: number;
      lastRun: string;
      trend: 'improving' | 'stable' | 'declining';
    }>;
  };
  compliance: {
    overallCompliance: number;
    categoryCompliance: {
      [category: string]: number;
    };
    standardsMet: string[];
    standardsViolated: string[];
  };
}

// Mock data
const mockQualityChecks: QualityCheck[] = [
  {
    id: 'qc-001',
    name: 'API Response Validation',
    description:
      'Validates API response schemas, data types, and required fields',
    category: 'functional',
    type: 'automated',
    severity: 'high',
    status: 'active',
    schedule: {
      enabled: true,
      frequency: 'continuous',
      timezone: 'UTC',
    },
    rules: {
      conditions: [
        {
          id: 'cond-001',
          name: 'Response Schema Validation',
          type: 'pattern_match',
          operator: 'matches',
          target: 'api-response-schema',
          weight: 1.0,
          enabled: true,
        },
        {
          id: 'cond-002',
          name: 'Required Fields Check',
          type: 'code_analysis',
          operator: 'eq',
          target: 0,
          weight: 0.8,
          enabled: true,
        },
      ],
      passThreshold: 95,
      failThreshold: 70,
      maxExecutionTime: 30,
    },
    scope: {
      components: ['api-gateway', 'search-service', 'rag-service'],
      userFlows: ['query', 'upload', 'download'],
      environments: ['production', 'staging'],
    },
    notifications: {
      onPass: false,
      onFail: true,
      onWarning: true,
      recipients: ['dev-team@company.com'],
      channels: ['email', 'slack'],
    },
    integration: {
      tools: ['jest', 'postman'],
      apis: ['validation-api'],
      scripts: ['api-schema-validator.js'],
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-15T14:30:00Z',
      createdBy: 'qa-lead',
      lastRun: '2025-10-17T12:00:00Z',
      version: '1.2.0',
      tags: ['api', 'validation', 'schema'],
    },
  },
  {
    id: 'qc-002',
    name: 'Performance Metrics Check',
    description:
      'Monitors response times, throughput, and resource utilization',
    category: 'performance',
    type: 'automated',
    severity: 'medium',
    status: 'active',
    schedule: {
      enabled: true,
      frequency: 'continuous',
      timezone: 'UTC',
    },
    rules: {
      conditions: [
        {
          id: 'cond-003',
          name: 'Response Time Check',
          type: 'metric_threshold',
          operator: 'lte',
          target: 2000,
          weight: 0.7,
          enabled: true,
        },
        {
          id: 'cond-004',
          name: 'Memory Usage Check',
          type: 'metric_threshold',
          operator: 'lte',
          target: 80,
          weight: 0.5,
          enabled: true,
        },
      ],
      passThreshold: 90,
      failThreshold: 75,
      maxExecutionTime: 60,
    },
    scope: {
      components: ['api-gateway', 'search-service'],
      userFlows: ['query', 'search'],
      environments: ['production', 'staging', 'development'],
    },
    notifications: {
      onPass: false,
      onFail: true,
      onWarning: true,
      recipients: ['ops-team@company.com', 'dev-team@company.com'],
      channels: ['email', 'slack', 'webhook'],
    },
    integration: {
      tools: ['k6', 'lighthouse'],
      apis: ['monitoring-api'],
      scripts: ['performance-monitor.js'],
    },
    metadata: {
      created: '2025-10-05T09:00:00Z',
      updated: '2025-10-14T16:45:00Z',
      createdBy: 'perf-engineer',
      lastRun: '2025-10-17T11:30:00Z',
      version: '1.1.0',
      tags: ['performance', 'metrics', 'monitoring'],
    },
  },
  {
    id: 'qc-003',
    name: 'Security Vulnerability Scan',
    description:
      'Scans for security vulnerabilities, OWASP compliance, and data leaks',
    category: 'security',
    type: 'automated',
    severity: 'critical',
    status: 'active',
    schedule: {
      enabled: true,
      frequency: 'daily',
      timezone: 'UTC',
    },
    rules: {
      conditions: [
        {
          id: 'cond-005',
          name: 'OWASP Top 10 Check',
          type: 'security_scan',
          operator: 'eq',
          target: 0,
          weight: 1.0,
          enabled: true,
        },
        {
          id: 'cond-006',
          name: 'Dependency Vulnerability Check',
          type: 'code_analysis',
          operator: 'eq',
          target: 0,
          weight: 0.9,
          enabled: true,
        },
      ],
      passThreshold: 100,
      failThreshold: 95,
      maxExecutionTime: 120,
    },
    scope: {
      components: ['frontend', 'backend', 'database'],
      userFlows: ['all'],
      environments: ['production', 'staging'],
    },
    notifications: {
      onPass: false,
      onFail: true,
      onWarning: true,
      recipients: ['security-team@company.com', 'cto@company.com'],
      channels: ['email', 'slack', 'webhook'],
    },
    integration: {
      tools: ['snyk', 'owasp-zap', 'eslint-plugin-security'],
      apis: ['security-api'],
      scripts: ['security-scan.sh'],
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-16T10:30:00Z',
      createdBy: 'security-lead',
      lastRun: '2025-10-17T03:00:00Z',
      version: '2.0.0',
      tags: ['security', 'vulnerability', 'owasp'],
    },
  },
  {
    id: 'qc-004',
    name: 'Accessibility Compliance',
    description: 'WCAG 2.1 AA accessibility compliance checks',
    category: 'accessibility',
    type: 'automated',
    severity: 'medium',
    status: 'active',
    schedule: {
      enabled: true,
      frequency: 'on_demand',
      timezone: 'UTC',
    },
    rules: {
      conditions: [
        {
          id: 'cond-007',
          name: 'WCAG 2.1 AA Compliance',
          type: 'accessibility_test',
          operator: 'eq',
          target: 100,
          weight: 1.0,
          enabled: true,
        },
      ],
      passThreshold: 95,
      failThreshold: 80,
      maxExecutionTime: 90,
    },
    scope: {
      components: ['frontend'],
      userFlows: ['navigation', 'search', 'query'],
      environments: ['production', 'staging'],
    },
    notifications: {
      onPass: false,
      onFail: true,
      onWarning: true,
      recipients: ['ux-team@company.com', 'dev-team@company.com'],
      channels: ['email', 'slack'],
    },
    integration: {
      tools: ['axe', 'lighthouse'],
      apis: [],
      scripts: ['accessibility-check.js'],
    },
    metadata: {
      created: '2025-10-10T13:20:00Z',
      updated: '2025-10-15T12:15:00Z',
      createdBy: 'ux-lead',
      lastRun: '2025-10-16T16:45:00Z',
      version: '1.0.0',
      tags: ['accessibility', 'wcag', 'ux'],
    },
  },
];

const mockCheckResults: QualityCheckResult[] = [
  {
    id: 'result-001',
    checkId: 'qc-001',
    checkName: 'API Response Validation',
    category: 'functional',
    status: 'passed',
    score: 98.5,
    duration: 15.2,
    timestamp: '2025-10-17T12:00:00Z',
    environment: 'production',
    version: '1.2.0',
    results: {
      totalConditions: 2,
      passedConditions: 2,
      failedConditions: 0,
      warningConditions: 0,
      details: [
        {
          conditionId: 'cond-001',
          conditionName: 'Response Schema Validation',
          status: 'passed',
          score: 100,
          actualValue: 'valid',
          expectedValue: 'valid',
          message: 'All API responses conform to schema',
        },
        {
          conditionId: 'cond-002',
          conditionName: 'Required Fields Check',
          status: 'passed',
          score: 95,
          actualValue: 0,
          expectedValue: 0,
          message: 'No missing required fields detected',
        },
      ],
    },
    metrics: {
      responseTime: 450,
      requestCount: 1250,
      errorRate: 0.2,
    },
    artifacts: {
      reports: ['api-validation-report-2025-10-17.pdf'],
      screenshots: [],
      logs: ['api-validation-2025-10-17.log'],
    },
    issues: [],
    recommendations: [
      {
        id: 'rec-001',
        type: 'optimization',
        priority: 'low',
        title: 'Optimize Response Size',
        description:
          'Some API responses could be optimized to reduce payload size',
        impact: 'Improved performance and reduced bandwidth usage',
        effort: 'medium',
        category: 'performance',
        resources: {
          documentation: ['api-optimization-guide.md'],
          examples: ['response-compression-example.js'],
          tools: ['json-optimizer'],
        },
      },
    ],
  },
  {
    id: 'result-002',
    checkId: 'qc-002',
    checkName: 'Performance Metrics Check',
    category: 'performance',
    status: 'warning',
    score: 82.3,
    duration: 45.8,
    timestamp: '2025-10-17T11:30:00Z',
    environment: 'production',
    version: '1.1.0',
    results: {
      totalConditions: 2,
      passedConditions: 1,
      failedConditions: 0,
      warningConditions: 1,
      details: [
        {
          conditionId: 'cond-003',
          conditionName: 'Response Time Check',
          status: 'warning',
          score: 75,
          actualValue: 2100,
          expectedValue: 2000,
          message: 'Response time exceeds threshold by 100ms',
        },
        {
          conditionId: 'cond-004',
          conditionName: 'Memory Usage Check',
          status: 'passed',
          score: 90,
          actualValue: 65,
          expectedValue: 80,
          message: 'Memory usage within acceptable limits',
        },
      ],
    },
    metrics: {
      avgResponseTime: 1850,
      p95ResponseTime: 2100,
      memoryUsage: 65,
      cpuUsage: 45,
    },
    artifacts: {
      reports: ['performance-report-2025-10-17.pdf'],
      screenshots: ['performance-dashboard-2025-10-17.png'],
      logs: ['performance-monitor-2025-10-17.log'],
    },
    issues: [
      {
        id: 'issue-001',
        severity: 'medium',
        title: 'Response Time Degradation',
        description:
          'API response times are approaching the maximum acceptable threshold',
        category: 'performance',
        component: 'search-service',
        recommendation:
          'Consider implementing response caching or query optimization',
        status: 'open',
        createdAt: '2025-10-17T11:30:00Z',
      },
    ],
    recommendations: [
      {
        id: 'rec-002',
        type: 'improvement',
        priority: 'high',
        title: 'Implement Response Caching',
        description:
          'Add caching layer to reduce response times for frequently accessed data',
        impact: 'Reduced response times and improved user experience',
        effort: 'high',
        category: 'performance',
        resources: {
          documentation: ['caching-strategy-guide.md'],
          examples: ['redis-implementation-example.js'],
          tools: ['redis', 'memcached'],
        },
      },
    ],
  },
  {
    id: 'result-003',
    checkId: 'qc-003',
    checkName: 'Security Vulnerability Scan',
    category: 'security',
    status: 'failed',
    score: 95.0,
    duration: 110.5,
    timestamp: '2025-10-17T03:00:00Z',
    environment: 'production',
    version: '2.0.0',
    results: {
      totalConditions: 2,
      passedConditions: 1,
      failedConditions: 1,
      warningConditions: 0,
      details: [
        {
          conditionId: 'cond-005',
          conditionName: 'OWASP Top 10 Check',
          status: 'passed',
          score: 100,
          actualValue: 0,
          expectedValue: 0,
          message: 'No OWASP Top 10 vulnerabilities detected',
        },
        {
          conditionId: 'cond-006',
          conditionName: 'Dependency Vulnerability Check',
          status: 'failed',
          score: 90,
          actualValue: 2,
          expectedValue: 0,
          message: '2 high-severity dependencies with known vulnerabilities',
        },
      ],
    },
    metrics: {
      vulnerabilitiesFound: 2,
      criticalVulnerabilities: 0,
      highVulnerabilities: 2,
      mediumVulnerabilities: 0,
      lowVulnerabilities: 0,
    },
    artifacts: {
      reports: ['security-scan-report-2025-10-17.pdf'],
      screenshots: [],
      logs: ['security-scan-2025-10-17.log'],
    },
    issues: [
      {
        id: 'issue-002',
        severity: 'high',
        title: 'Outdated Dependencies with Vulnerabilities',
        description: 'Found 2 dependencies with known security vulnerabilities',
        category: 'security',
        component: 'backend',
        file: 'package.json',
        recommendation: 'Update dependencies to latest secure versions',
        status: 'open',
        createdAt: '2025-10-17T03:00:00Z',
      },
    ],
    recommendations: [
      {
        id: 'rec-003',
        type: 'fix',
        priority: 'high',
        title: 'Update Vulnerable Dependencies',
        description: 'Update dependencies to resolve security vulnerabilities',
        impact:
          'Eliminates security risks and improves system security posture',
        effort: 'medium',
        category: 'security',
        resources: {
          documentation: ['dependency-update-guide.md'],
          examples: ['package-update-example.js'],
          tools: ['npm audit', 'yarn audit'],
        },
      },
    ],
  },
];

const generateMockDashboard = (timeRange: string): QualityDashboard => {
  const days =
    timeRange === '1d'
      ? 1
      : timeRange === '7d'
        ? 7
        : timeRange === '30d'
          ? 30
          : 90;
  const now = new Date();

  const trends = Array.from({ length: Math.min(days, 30) }, (_, i) => {
    const date = new Date(now.getTime() - (days - i) * 24 * 60 * 60 * 1000);
    return {
      timestamp: date.toLocaleDateString(),
      functional: 85 + Math.random() * 10,
      performance: 75 + Math.random() * 15,
      security: 90 + Math.random() * 8,
      accessibility: 80 + Math.random() * 12,
      usability: 82 + Math.random() * 11,
      compliance: 88 + Math.random() * 9,
    };
  });

  return {
    timeRange: timeRange as QualityDashboard['timeRange'],
    summary: {
      totalChecks: mockQualityChecks.length,
      passedChecks: mockCheckResults.filter((r) => r.status === 'passed')
        .length,
      failedChecks: mockCheckResults.filter((r) => r.status === 'failed')
        .length,
      warningChecks: mockCheckResults.filter((r) => r.status === 'warning')
        .length,
      averageScore:
        mockCheckResults.length > 0
          ? mockCheckResults.reduce((sum, r) => sum + r.score, 0) /
            mockCheckResults.length
          : 0,
      totalIssues: mockCheckResults.reduce(
        (sum, r) => sum + r.issues.length,
        0
      ),
      criticalIssues: mockCheckResults.reduce(
        (sum, r) =>
          sum + r.issues.filter((i) => i.severity === 'critical').length,
        0
      ),
    },
    trends: {
      scoresByTime: trends,
      issuesByCategory: [
        { category: 'Security', count: 2, severity: 'high' },
        { category: 'Performance', count: 3, severity: 'medium' },
        { category: 'Functional', count: 1, severity: 'low' },
        { category: 'Usability', count: 1, severity: 'medium' },
      ],
      checkPerformance: [
        {
          checkName: 'API Response Validation',
          averageScore: 98.5,
          lastRun: '2025-10-17T12:00:00Z',
          trend: 'stable' as const,
        },
        {
          checkName: 'Performance Metrics Check',
          averageScore: 82.3,
          lastRun: '2025-10-17T11:30:00Z',
          trend: 'declining' as const,
        },
        {
          checkName: 'Security Vulnerability Scan',
          averageScore: 95.0,
          lastRun: '2025-10-17T03:00:00Z',
          trend: 'improving' as const,
        },
        {
          checkName: 'Accessibility Compliance',
          averageScore: 92.0,
          lastRun: '2025-10-16T16:45:00Z',
          trend: 'stable' as const,
        },
      ],
    },
    compliance: {
      overallCompliance: 87.5,
      categoryCompliance: {
        functional: 95.0,
        performance: 82.3,
        security: 95.0,
        accessibility: 92.0,
        usability: 88.0,
        compliance: 87.5,
      },
      standardsMet: ['WCAG 2.1 AA', 'OWASP Top 10', 'SOC 2 Type II'],
      standardsViolated: ['GDPR Article 32', 'ISO 27001 Control A.12.2'],
    },
  };
};

const categories = [
  {
    id: 'functional',
    name: 'Functional',
    icon: <Target className="h-4 w-4" />,
    color: 'blue',
  },
  {
    id: 'performance',
    name: 'Performance',
    icon: <Zap className="h-4 w-4" />,
    color: 'orange',
  },
  {
    id: 'security',
    name: 'Security',
    icon: <Shield className="h-4 w-4" />,
    color: 'red',
  },
  {
    id: 'accessibility',
    name: 'Accessibility',
    icon: <UserCheck className="h-4 w-4" />,
    color: 'green',
  },
  {
    id: 'usability',
    name: 'Usability',
    icon: <FileCheck className="h-4 w-4" />,
    color: 'purple',
  },
  {
    id: 'compliance',
    name: 'Compliance',
    icon: <Globe className="h-4 w-4" />,
    color: 'indigo',
  },
];

const AutomatedQualityChecks: React.FC<AutomatedQualityChecksProps> = ({
  onCheckCreate,
  onCheckUpdate,
  onCheckDelete,
  onCheckRun,
  className,
}) => {
  const [qualityChecks, setQualityChecks] =
    useState<QualityCheck[]>(mockQualityChecks);
  const [checkResults, setCheckResults] =
    useState<QualityCheckResult[]>(mockCheckResults);
  const [dashboard, setDashboard] = useState<QualityDashboard>(() =>
    generateMockDashboard('7d')
  );
  const [selectedCheck, setSelectedCheck] = useState<QualityCheck | null>(null);
  const [selectedResult, setSelectedResult] =
    useState<QualityCheckResult | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [timeRange, setTimeRange] = useState('7d');
  const [isCreateCheckDialogOpen, setIsCreateCheckDialogOpen] = useState(false);
  const [editingCheck, setEditingCheck] = useState<QualityCheck | null>(null);
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedChecks, setExpandedChecks] = useState<Set<string>>(new Set());

  // Update dashboard when time range changes
  React.useEffect(() => {
    setDashboard(generateMockDashboard(timeRange));
  }, [timeRange]);

  // Filter checks
  const filteredChecks = useMemo(() => {
    return qualityChecks.filter((check) => {
      const matchesSearch =
        check.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        check.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory =
        filterCategory === 'all' || check.category === filterCategory;
      const matchesStatus =
        filterStatus === 'all' || check.status === filterStatus;
      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [qualityChecks, searchTerm, filterCategory, filterStatus]);

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'passed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'warning':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'error':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'skipped':
        return 'bg-gray-100 text-foreground border-border';
      default:
        return 'bg-gray-100 text-foreground border-border';
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'passed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'skipped':
        return <Clock className="h-4 w-4 text-muted-foreground" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  // Get severity color
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-foreground border-border';
    }
  };

  // Run quality check
  const runQualityCheck = useCallback(
    async (checkId: string) => {
      const check = qualityChecks.find((c) => c.id === checkId);
      if (!check) return;

      // Add running result
      const runningResult: QualityCheckResult = {
        id: `result-${Date.now()}`,
        checkId,
        checkName: check.name,
        category: check.category,
        status: 'warning',
        score: 0,
        duration: 0,
        timestamp: new Date().toISOString(),
        environment: 'production',
        version: check.metadata.version,
        results: {
          totalConditions: check.rules.conditions.length,
          passedConditions: 0,
          failedConditions: 0,
          warningConditions: 0,
          details: [],
        },
        metrics: {},
        artifacts: {
          reports: [],
          screenshots: [],
          logs: [],
        },
        issues: [],
        recommendations: [],
      };

      setCheckResults((prev) => [runningResult, ...prev]);

      // Simulate check execution
      setTimeout(
        () => {
          const mockResult = mockCheckResults.find(
            (r) => r.checkId === checkId
          );
          if (mockResult) {
            setCheckResults((prev) =>
              prev.map((r) =>
                r.id === runningResult.id
                  ? { ...mockResult, id: runningResult.id }
                  : r
              )
            );
          }
        },
        3000 + Math.random() * 5000
      );

      onCheckRun?.(checkId);
    },
    [qualityChecks, onCheckRun]
  );

  // Toggle check expansion
  const toggleCheckExpansion = useCallback((checkId: string) => {
    setExpandedChecks((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(checkId)) {
        newSet.delete(checkId);
      } else {
        newSet.add(checkId);
      }
      return newSet;
    });
  }, []);

  // Delete quality check
  const handleDeleteCheck = useCallback(
    (checkId: string) => {
      setQualityChecks((prev) => prev.filter((check) => check.id !== checkId));
      onCheckDelete?.(checkId);
    },
    [onCheckDelete]
  );

  // Save quality check
  const handleSaveCheck = useCallback(
    (checkData: Partial<QualityCheck>) => {
      if (editingCheck) {
        // Update existing check
        setQualityChecks((prev) =>
          prev.map((check) =>
            check.id === editingCheck.id
              ? {
                  ...check,
                  ...checkData,
                  metadata: {
                    ...check.metadata,
                    ...checkData.metadata,
                    updated: new Date().toISOString(),
                  },
                }
              : check
          )
        );
        setEditingCheck(null);
      } else {
        // Create new check
        const newCheck: QualityCheck = {
          id: `qc-${Date.now()}`,
          name: checkData.name || 'New Quality Check',
          description: checkData.description || '',
          category: checkData.category || 'functional',
          type: checkData.type || 'automated',
          severity: checkData.severity || 'medium',
          status: 'active',
          schedule: {
            enabled: true,
            frequency: 'daily',
            timezone: 'UTC',
          },
          rules: {
            conditions: [],
            passThreshold: 90,
            failThreshold: 70,
            maxExecutionTime: 60,
          },
          scope: {
            components: [],
            userFlows: [],
            environments: ['production', 'staging'],
          },
          notifications: {
            onPass: false,
            onFail: true,
            onWarning: true,
            recipients: [],
            channels: ['email'],
          },
          integration: {
            tools: [],
            apis: [],
            scripts: [],
          },
          metadata: {
            created: new Date().toISOString(),
            updated: new Date().toISOString(),
            createdBy: 'current-user',
            version: '1.0.0',
            tags: [],
          },
        };
        setQualityChecks((prev) => [...prev, newCheck]);
        onCheckCreate?.(newCheck);
      }
      setIsCreateCheckDialogOpen(false);
    },
    [editingCheck, onCheckCreate]
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Automated Quality Checks
          </h2>
          <p className="text-foreground">
            Monitor and maintain code quality automatically
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1d">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Dialog
            open={isCreateCheckDialogOpen}
            onOpenChange={setIsCreateCheckDialogOpen}
          >
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Check
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>
                  {editingCheck ? 'Edit Quality Check' : 'Create Quality Check'}
                </DialogTitle>
                <DialogDescription>
                  Configure automated quality checks for your application
                </DialogDescription>
              </DialogHeader>
              <QualityCheckForm
                check={editingCheck}
                onSubmit={handleSaveCheck}
                onCancel={() => {
                  setIsCreateCheckDialogOpen(false);
                  setEditingCheck(null);
                }}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Quality Overview */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <FileCheck className="h-5 w-5 text-blue-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.totalChecks}
                </div>
                <div className="text-sm text-foreground">Total Checks</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.passedChecks}
                </div>
                <div className="text-sm text-foreground">Passed</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <XCircle className="h-5 w-5 text-red-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.failedChecks}
                </div>
                <div className="text-sm text-foreground">Failed</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.warningChecks}
                </div>
                <div className="text-sm text-foreground">Warnings</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5 text-purple-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.averageScore.toFixed(1)}%
                </div>
                <div className="text-sm text-foreground">Avg Score</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Overview</span>
          </TabsTrigger>
          <TabsTrigger value="checks" className="flex items-center space-x-2">
            <FileCheck className="h-4 w-4" />
            <span>Quality Checks</span>
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center space-x-2">
            <Activity className="h-4 w-4" />
            <span>Results</span>
          </TabsTrigger>
          <TabsTrigger value="issues" className="flex items-center space-x-2">
            <Bug className="h-4 w-4" />
            <span>Issues</span>
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Quality Score Trends</CardTitle>
                <CardDescription>Quality metrics over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dashboard.trends.scoresByTime}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="functional"
                        stroke="#3b82f6"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="performance"
                        stroke="#f59e0b"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="security"
                        stroke="#ef4444"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="accessibility"
                        stroke="#10b981"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="usability"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="compliance"
                        stroke="#6366f1"
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Category Performance</CardTitle>
                <CardDescription>Quality scores by category</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart
                      data={Object.entries(
                        dashboard.compliance.categoryCompliance
                      ).map(([category, score]) => ({
                        category:
                          category.charAt(0).toUpperCase() + category.slice(1),
                        score,
                      }))}
                    >
                      <PolarGrid />
                      <PolarAngleAxis
                        dataKey="category"
                        tick={{ fontSize: 12 }}
                      />
                      <PolarRadiusAxis
                        angle={0}
                        domain={[0, 100]}
                        tick={{ fontSize: 10 }}
                      />
                      <Radar
                        name="Quality Score"
                        dataKey="score"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                        fillOpacity={0.3}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Recent Check Performance</CardTitle>
                <CardDescription>
                  Latest quality check results and trends
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {dashboard.trends.checkPerformance.map((perf, index) => (
                    <div
                      key={perf.checkName}
                      className="flex items-center justify-between p-3 border rounded-lg"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="text-sm font-medium">
                          {perf.checkName}
                        </div>
                        <div className="flex items-center space-x-1">
                          {perf.trend === 'improving' ? (
                            <TrendingUp className="h-3 w-3 text-green-500" />
                          ) : perf.trend === 'declining' ? (
                            <TrendingDown className="h-3 w-3 text-red-500" />
                          ) : (
                            <div className="w-3 h-3 bg-gray-300 rounded-full" />
                          )}
                          <span className="text-xs text-muted-foreground">
                            {perf.trend}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold">
                          {perf.averageScore.toFixed(1)}%
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(perf.lastRun).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Compliance Status</CardTitle>
                <CardDescription>
                  Compliance with industry standards
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        Overall Compliance
                      </span>
                      <span className="text-sm font-bold">
                        {dashboard.compliance.overallCompliance.toFixed(1)}%
                      </span>
                    </div>
                    <Progress
                      value={dashboard.compliance.overallCompliance}
                      className="h-2"
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Standards Met:</div>
                    <div className="flex flex-wrap gap-1">
                      {dashboard.compliance.standardsMet.map((standard) => (
                        <Badge
                          key={standard}
                          variant="outline"
                          className="text-xs"
                        >
                          {standard}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  {dashboard.compliance.standardsViolated.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm font-medium text-red-600">
                        Standards Violated:
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {dashboard.compliance.standardsViolated.map(
                          (standard) => (
                            <Badge
                              key={standard}
                              variant="destructive"
                              className="text-xs"
                            >
                              {standard}
                            </Badge>
                          )
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Quality Checks Tab */}
        <TabsContent value="checks" className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center space-x-4 mb-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search quality checks..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Select
                  value={filterCategory}
                  onValueChange={setFilterCategory}
                >
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Categories</SelectItem>
                    {categories.map((category) => (
                      <SelectItem key={category.id} value={category.id}>
                        {category.name}
                      </SelectItem>
                    ))}
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
                    <SelectItem value="deprecated">Deprecated</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3">
                {filteredChecks.map((check) => {
                  const lastResult = checkResults.find(
                    (r) => r.checkId === check.id
                  );
                  const categoryConfig = categories.find(
                    (c) => c.id === check.category
                  );

                  return (
                    <Card
                      key={check.id}
                      className="hover:shadow-md transition-shadow"
                    >
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-3">
                            {categoryConfig?.icon}
                            <div>
                              <CardTitle className="text-lg">
                                {check.name}
                              </CardTitle>
                              <CardDescription className="mt-1">
                                {check.description}
                              </CardDescription>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Badge className={getSeverityColor(check.severity)}>
                              {check.severity}
                            </Badge>
                            <Badge
                              variant={
                                check.status === 'active'
                                  ? 'default'
                                  : 'secondary'
                              }
                            >
                              {check.status}
                            </Badge>
                            <Switch
                              checked={check.schedule.enabled}
                              onCheckedChange={() => {
                                setQualityChecks((prev) =>
                                  prev.map((c) =>
                                    c.id === check.id
                                      ? {
                                          ...c,
                                          schedule: {
                                            ...c.schedule,
                                            enabled: !c.schedule.enabled,
                                          },
                                          metadata: {
                                            ...c.metadata,
                                            updated: new Date().toISOString(),
                                          },
                                        }
                                      : c
                                  )
                                );
                              }}
                            />
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <div className="text-sm font-medium text-foreground">
                              Type
                            </div>
                            <div className="text-sm capitalize">
                              {check.type}
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">
                              Schedule
                            </div>
                            <div className="text-sm">
                              {check.schedule.frequency}
                              {check.schedule.enabled &&
                                ` (${check.schedule.timezone})`}
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium text-foreground">
                              Last Run
                            </div>
                            <div className="text-sm">
                              {check.metadata.lastRun
                                ? new Date(
                                    check.metadata.lastRun
                                  ).toLocaleDateString()
                                : 'Never'}
                            </div>
                          </div>
                        </div>

                        {lastResult && (
                          <div className="border rounded-lg p-3 bg-gray-50 dark:bg-gray-800">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center space-x-2">
                                {getStatusIcon(lastResult.status)}
                                <span className="text-sm font-medium">
                                  Last Result
                                </span>
                              </div>
                              <div className="text-sm font-bold">
                                {lastResult.score.toFixed(1)}%
                              </div>
                            </div>
                            <div className="grid grid-cols-3 gap-2 text-xs">
                              <div>
                                <span className="text-muted-foreground">
                                  Passed:
                                </span>
                                <span className="font-medium">
                                  {lastResult.results.passedConditions}
                                </span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">
                                  Failed:
                                </span>
                                <span className="font-medium">
                                  {lastResult.results.failedConditions}
                                </span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">
                                  Duration:
                                </span>
                                <span className="font-medium">
                                  {lastResult.duration.toFixed(1)}s
                                </span>
                              </div>
                            </div>
                            {lastResult.issues.length > 0 && (
                              <div className="mt-2 text-xs text-red-600">
                                {lastResult.issues.length} issues found
                              </div>
                            )}
                          </div>
                        )}

                        <div className="flex items-center justify-between">
                          <div className="flex flex-wrap gap-1">
                            {check.metadata.tags.map((tag) => (
                              <Badge
                                key={tag}
                                variant="outline"
                                className="text-xs"
                              >
                                {tag}
                              </Badge>
                            ))}
                          </div>
                          <div className="flex items-center space-x-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => runQualityCheck(check.id)}
                            >
                              <Play className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleCheckExpansion(check.id)}
                            >
                              {expandedChecks.has(check.id) ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setEditingCheck(check);
                                setIsCreateCheckDialogOpen(true);
                              }}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteCheck(check.id)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>

                        {expandedChecks.has(check.id) && (
                          <div className="mt-4 p-4 border rounded-lg space-y-4">
                            <div>
                              <h5 className="font-medium mb-2">
                                Configuration
                              </h5>
                              <div className="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                  <span className="text-muted-foreground">
                                    Pass Threshold:
                                  </span>
                                  <span>{check.rules.passThreshold}%</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">
                                    Fail Threshold:
                                  </span>
                                  <span>{check.rules.failThreshold}%</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">
                                    Max Execution Time:
                                  </span>
                                  <span>{check.rules.maxExecutionTime}s</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">
                                    Conditions:
                                  </span>
                                  <span>{check.rules.conditions.length}</span>
                                </div>
                              </div>
                            </div>
                            <div>
                              <h5 className="font-medium mb-2">Scope</h5>
                              <div className="text-sm">
                                <div>
                                  Components:{' '}
                                  {check.scope.components.join(', ') || 'None'}
                                </div>
                                <div>
                                  Environments:{' '}
                                  {check.scope.environments.join(', ')}
                                </div>
                              </div>
                            </div>
                            <div>
                              <h5 className="font-medium mb-2">Integration</h5>
                              <div className="text-sm">
                                <div>
                                  Tools:{' '}
                                  {check.integration.tools.join(', ') || 'None'}
                                </div>
                                <div>
                                  Scripts:{' '}
                                  {check.integration.scripts.join(', ') ||
                                    'None'}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Results Tab */}
        <TabsContent value="results" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Quality Check Results</CardTitle>
              <CardDescription>
                Latest automated quality check executions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {checkResults.map((result) => {
                  const categoryConfig = categories.find(
                    (c) => c.id === result.category
                  );

                  return (
                    <div key={result.id} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start space-x-3">
                          {getStatusIcon(result.status)}
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-1">
                              <h4 className="font-medium">
                                {result.checkName}
                              </h4>
                              <Badge className={getStatusColor(result.status)}>
                                {result.status}
                              </Badge>
                              <Badge variant="outline">
                                {categoryConfig?.icon}
                                <span className="ml-1 capitalize">
                                  {result.category}
                                </span>
                              </Badge>
                            </div>
                            <div className="text-sm text-foreground mb-2">
                              Environment: {result.environment} • Version:{' '}
                              {result.version} • Duration:{' '}
                              {result.duration.toFixed(1)}s
                            </div>
                            <div className="text-xs text-muted-foreground">
                              Run at:{' '}
                              {new Date(result.timestamp).toLocaleString()}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedResult(result)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>

                      <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-800 rounded">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">
                            Score Breakdown
                          </span>
                          <span className="text-sm font-bold">
                            {result.score.toFixed(1)}%
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-4 text-xs">
                          <div>
                            <span className="text-muted-foreground">
                              Total:
                            </span>
                            <span className="font-medium">
                              {result.results.totalConditions}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Passed:
                            </span>
                            <span className="font-medium text-green-600">
                              {result.results.passedConditions}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Failed:
                            </span>
                            <span className="font-medium text-red-600">
                              {result.results.failedConditions}
                            </span>
                          </div>
                        </div>
                      </div>

                      {result.issues.length > 0 && (
                        <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 rounded">
                          <div className="text-sm font-medium text-red-600 mb-2">
                            Issues Found ({result.issues.length})
                          </div>
                          <div className="space-y-1">
                            {result.issues.slice(0, 3).map((issue) => (
                              <div key={issue.id} className="text-xs">
                                <div className="flex items-center space-x-2">
                                  <Badge
                                    className={getSeverityColor(issue.severity)}
                                    variant="outline"
                                  >
                                    {issue.severity}
                                  </Badge>
                                  <span>{issue.title}</span>
                                </div>
                              </div>
                            ))}
                            {result.issues.length > 3 && (
                              <div className="text-xs text-muted-foreground">
                                ...and {result.issues.length - 3} more
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {result.recommendations.length > 0 && (
                        <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
                          <div className="text-sm font-medium text-blue-600 mb-2">
                            Recommendations ({result.recommendations.length})
                          </div>
                          <div className="space-y-1">
                            {result.recommendations.slice(0, 2).map((rec) => (
                              <div key={rec.id} className="text-xs">
                                <div className="flex items-center space-x-2">
                                  <Badge variant="outline" className="text-xs">
                                    {rec.type}
                                  </Badge>
                                  <span>{rec.title}</span>
                                </div>
                              </div>
                            ))}
                            {result.recommendations.length > 2 && (
                              <div className="text-xs text-muted-foreground">
                                ...and {result.recommendations.length - 2} more
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Issues Tab */}
        <TabsContent value="issues" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Quality Issues</CardTitle>
              <CardDescription>
                Issues detected by automated quality checks
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {checkResults
                  .flatMap((result) => result.issues)
                  .map((issue) => (
                    <div key={issue.id} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start space-x-3">
                          <Badge className={getSeverityColor(issue.severity)}>
                            {issue.severity}
                          </Badge>
                          <div className="flex-1">
                            <h4 className="font-medium">{issue.title}</h4>
                            <p className="text-sm text-foreground mt-1">
                              {issue.description}
                            </p>
                            <div className="text-xs text-muted-foreground mt-2 space-y-1">
                              <div>Category: {issue.category}</div>
                              {issue.component && (
                                <div>Component: {issue.component}</div>
                              )}
                              {issue.file && <div>File: {issue.file}</div>}
                              <div>
                                Status: {issue.status} • Created:{' '}
                                {new Date(issue.createdAt).toLocaleDateString()}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
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

// Quality Check Form Component
const QualityCheckForm: React.FC<QualityCheckFormProps> = ({
  check,
  onSubmit,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    name: check?.name || '',
    description: check?.description || '',
    category: check?.category || 'functional',
    type: check?.type || 'automated',
    severity: check?.severity || 'medium',
    scheduleEnabled: check?.schedule.enabled ?? true,
    frequency: check?.schedule.frequency || 'daily',
    timezone: check?.schedule.timezone || 'UTC',
    passThreshold: check?.rules.passThreshold || 90,
    failThreshold: check?.rules.failThreshold || 70,
    maxExecutionTime: check?.rules.maxExecutionTime || 60,
    notifyOnPass: check?.notifications.onPass || false,
    notifyOnFail: check?.notifications.onFail ?? true,
    notifyOnWarning: check?.notifications.onWarning ?? true,
    recipients: check?.notifications.recipients?.join(', ') || '',
    isActive: check?.status === 'active',
    tags: check?.metadata.tags?.join(', ') || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const checkData: Partial<QualityCheck> = {
      name: formData.name,
      description: formData.description,
      category: formData.category as any,
      type: formData.type as any,
      severity: formData.severity as any,
      status: formData.isActive ? 'active' : 'inactive',
      schedule: {
        enabled: formData.scheduleEnabled,
        frequency: formData.frequency as any,
        timezone: formData.timezone,
      },
      rules: {
        conditions: [], // Would be populated by a condition builder
        passThreshold: formData.passThreshold,
        failThreshold: formData.failThreshold,
        maxExecutionTime: formData.maxExecutionTime,
      },
      notifications: {
        onPass: formData.notifyOnPass,
        onFail: formData.notifyOnFail,
        onWarning: formData.notifyOnWarning,
        recipients: formData.recipients
          .split(',')
          .map((r) => r.trim())
          .filter(Boolean),
        channels: ['email'], // Would be populated by a channel selector
      },
      metadata: {
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        createdBy: 'current-user',
        version: '1.0.0',
        tags: formData.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      },
    };

    onSubmit(checkData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="check-name">Check Name *</Label>
          <Input
            id="check-name"
            value={formData.name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, name: e.target.value }))
            }
            placeholder="Enter quality check name"
            required
          />
        </div>
        <div>
          <Label htmlFor="check-category">Category *</Label>
          <Select
            value={formData.category}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, category: value as any }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {categories.map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  <div className="flex items-center space-x-2">
                    {category.icon}
                    <span>{category.name}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="check-description">Description</Label>
        <Textarea
          id="check-description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Describe what this quality check validates"
          rows={3}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="check-type">Type *</Label>
          <Select
            value={formData.type}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, type: value as any }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="automated">Automated</SelectItem>
              <SelectItem value="manual">Manual</SelectItem>
              <SelectItem value="hybrid">Hybrid</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="check-severity">Severity *</Label>
          <Select
            value={formData.severity}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, severity: value as any }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Configuration</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="pass-threshold">Pass Threshold (%)</Label>
            <Input
              id="pass-threshold"
              type="number"
              min="0"
              max="100"
              value={formData.passThreshold}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  passThreshold: parseInt(e.target.value),
                }))
              }
            />
          </div>
          <div>
            <Label htmlFor="fail-threshold">Fail Threshold (%)</Label>
            <Input
              id="fail-threshold"
              type="number"
              min="0"
              max="100"
              value={formData.failThreshold}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  failThreshold: parseInt(e.target.value),
                }))
              }
            />
          </div>
          <div>
            <Label htmlFor="max-execution-time">
              Max Execution Time (seconds)
            </Label>
            <Input
              id="max-execution-time"
              type="number"
              min="1"
              value={formData.maxExecutionTime}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  maxExecutionTime: parseInt(e.target.value),
                }))
              }
            />
          </div>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Schedule</h4>
        <div className="flex items-center space-x-2 mb-4">
          <Switch
            id="schedule-enabled"
            checked={formData.scheduleEnabled}
            onCheckedChange={(checked) =>
              setFormData((prev) => ({ ...prev, scheduleEnabled: checked }))
            }
          />
          <Label htmlFor="schedule-enabled">Enable scheduling</Label>
        </div>
        {formData.scheduleEnabled && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="frequency">Frequency</Label>
              <Select
                value={formData.frequency}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, frequency: value as any }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="on_demand">On Demand</SelectItem>
                  <SelectItem value="hourly">Hourly</SelectItem>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="continuous">Continuous</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="timezone">Timezone</Label>
              <Select
                value={formData.timezone}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, timezone: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="UTC">UTC</SelectItem>
                  <SelectItem value="America/New_York">Eastern Time</SelectItem>
                  <SelectItem value="America/Los_Angeles">
                    Pacific Time
                  </SelectItem>
                  <SelectItem value="Europe/London">London</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Notifications</h4>
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <Switch
              id="notify-on-pass"
              checked={formData.notifyOnPass}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, notifyOnPass: checked }))
              }
            />
            <Label htmlFor="notify-on-pass">Notify on pass</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="notify-on-fail"
              checked={formData.notifyOnFail}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, notifyOnFail: checked }))
              }
            />
            <Label htmlFor="notify-on-fail">Notify on fail</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="notify-on-warning"
              checked={formData.notifyOnWarning}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, notifyOnWarning: checked }))
              }
            />
            <Label htmlFor="notify-on-warning">Notify on warning</Label>
          </div>
        </div>
        <div className="mt-4">
          <Label htmlFor="recipients">Recipients</Label>
          <Input
            id="recipients"
            value={formData.recipients}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, recipients: e.target.value }))
            }
            placeholder="email1@company.com, #slack-channel"
          />
        </div>
      </div>

      <div>
        <Label htmlFor="tags">Tags</Label>
        <Input
          id="tags"
          value={formData.tags}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, tags: e.target.value }))
          }
          placeholder="e.g., api, performance, security (comma-separated)"
        />
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="is-active"
          checked={formData.isActive}
          onCheckedChange={(checked) =>
            setFormData((prev) => ({ ...prev, isActive: checked }))
          }
        />
        <Label htmlFor="is-active">Activate check</Label>
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <FileCheck className="h-4 w-4 mr-2" />
          {check ? 'Update Check' : 'Create Check'}
        </Button>
      </div>
    </form>
  );
};

export default AutomatedQualityChecks;
