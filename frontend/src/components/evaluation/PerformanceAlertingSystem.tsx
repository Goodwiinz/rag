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
  ScatterChart,
  Scatter,
} from 'recharts';
import {
  Bell,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  TrendingUp,
  TrendingDown,
  Settings,
  Plus,
  Edit,
  Trash2,
  Eye,
  Pause,
  Play,
  RefreshCw,
  Volume2,
  VolumeX,
  Mail,
  MessageSquare,
  Smartphone,
  Webhook,
  Filter,
  Search,
  Info,
  ChevronDown,
  ChevronUp,
  Activity,
  Target,
  AlertCircle,
  Users,
  Calendar,
} from 'lucide-react';

// Types
interface AlertRule {
  id: string;
  name: string;
  description: string;
  category:
    | 'performance'
    | 'quality'
    | 'availability'
    | 'security'
    | 'business';
  severity: 'low' | 'medium' | 'high' | 'critical';
  isActive: boolean;
  condition: {
    metric: string;
    operator:
      | 'gt'
      | 'gte'
      | 'lt'
      | 'lte'
      | 'eq'
      | 'ne'
      | 'contains'
      | 'not_contains';
    threshold: number | string;
    duration?: number; // minutes
    aggregation?: 'avg' | 'min' | 'max' | 'sum' | 'count';
    evaluationWindow?: number; // minutes
  };
  filters: {
    timeRange?: {
      start?: string; // HH:MM
      end?: string; // HH:MM
    };
    daysOfWeek?: number[]; // 0-6
    tags?: string[];
    userGroups?: string[];
  };
  notifications: {
    channels: ('email' | 'slack' | 'sms' | 'webhook' | 'in_app')[];
    recipients: string[];
    cooldownPeriod: number; // minutes
    escalationPolicy?: {
      enabled: boolean;
      levels: Array<{
        delay: number; // minutes
        severity: 'medium' | 'high' | 'critical';
        additionalRecipients?: string[];
      }>;
    };
  };
  actions?: {
    type:
      | 'auto_remediation'
      | 'run_playbook'
      | 'scale_resources'
      | 'notify_on_call';
    config: Record<string, any>;
  };
  metadata: {
    created: string;
    updated: string;
    createdBy: string;
    lastTriggered?: string;
    triggerCount: number;
    resolutionCount: number;
    averageResolutionTime?: number; // minutes
  };
}

interface Alert {
  id: string;
  ruleId: string;
  ruleName: string;
  severity: AlertRule['severity'];
  status: 'firing' | 'resolved' | 'suppressed' | 'acknowledged';
  startedAt: string;
  resolvedAt?: string;
  acknowledgedAt?: string;
  acknowledgedBy?: string;
  duration?: number; // minutes
  message: string;
  details: {
    metric: string;
    currentValue: number | string;
    threshold: number | string;
    condition: string;
  };
  context: {
    affectedEntities?: string[];
    relatedAlerts?: string[];
    incidentId?: string;
  };
  notifications: Array<{
    channel: string;
    recipient: string;
    sentAt: string;
    status: 'sent' | 'failed' | 'pending';
  }>;
  resolution?: {
    method: 'auto' | 'manual';
    resolvedBy?: string;
    notes?: string;
  };
}

interface AlertDashboard {
  timeRange: '1h' | '6h' | '24h' | '7d' | '30d';
  summary: {
    totalAlerts: number;
    activeAlerts: number;
    resolvedAlerts: number;
    suppressedAlerts: number;
    criticalAlerts: number;
    mttr: number; // Mean Time To Resolution
  };
  trends: {
    alertsByTime: Array<{
      timestamp: string;
      critical: number;
      high: number;
      medium: number;
      low: number;
    }>;
    alertsByCategory: Array<{
      category: string;
      count: number;
    }>;
    topAlertRules: Array<{
      ruleName: string;
      count: number;
    }>;
  };
  performance: {
    alertLatency: number; // Average time from condition to alert
    notificationSuccess: number; // Percentage
    falsePositiveRate: number; // Percentage
  };
}

// Mock data
const mockAlertRules: AlertRule[] = [
  {
    id: 'rule-001',
    name: 'High Response Latency',
    description:
      'Alert when average response latency exceeds 2000ms for 5 minutes',
    category: 'performance',
    severity: 'high',
    isActive: true,
    condition: {
      metric: 'response_latency',
      operator: 'gt',
      threshold: 2000,
      duration: 5,
      aggregation: 'avg',
      evaluationWindow: 5,
    },
    filters: {
      timeRange: { start: '09:00', end: '17:00' },
      daysOfWeek: [1, 2, 3, 4, 5], // Weekdays
    },
    notifications: {
      channels: ['email', 'slack'],
      recipients: ['ops-team@company.com', 'on-call@company.com'],
      cooldownPeriod: 15,
      escalationPolicy: {
        enabled: true,
        levels: [
          {
            delay: 10,
            severity: 'high',
            additionalRecipients: ['manager@company.com'],
          },
          {
            delay: 30,
            severity: 'critical',
            additionalRecipients: ['cto@company.com'],
          },
        ],
      },
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-15T14:30:00Z',
      createdBy: 'ops-admin',
      lastTriggered: '2025-10-17T11:30:00Z',
      triggerCount: 12,
      resolutionCount: 11,
      averageResolutionTime: 8.5,
    },
  },
  {
    id: 'rule-002',
    name: 'Low Answer Relevancy',
    description: 'Alert when answer relevancy drops below 70%',
    category: 'quality',
    severity: 'medium',
    isActive: true,
    condition: {
      metric: 'answer_relevancy',
      operator: 'lt',
      threshold: 70,
      duration: 10,
      aggregation: 'avg',
      evaluationWindow: 10,
    },
    filters: {},
    notifications: {
      channels: ['email', 'slack'],
      recipients: ['qa-team@company.com'],
      cooldownPeriod: 30,
    },
    metadata: {
      created: '2025-10-05T09:00:00Z',
      updated: '2025-10-14T16:45:00Z',
      createdBy: 'qa-lead',
      lastTriggered: '2025-10-16T14:20:00Z',
      triggerCount: 5,
      resolutionCount: 4,
      averageResolutionTime: 15.2,
    },
  },
  {
    id: 'rule-003',
    name: 'System Health Check Failure',
    description: 'Critical alert when system health check fails',
    category: 'availability',
    severity: 'critical',
    isActive: true,
    condition: {
      metric: 'system_health',
      operator: 'eq',
      threshold: 'unhealthy',
      duration: 1,
      evaluationWindow: 1,
    },
    filters: {},
    notifications: {
      channels: ['email', 'slack', 'sms', 'webhook'],
      recipients: [
        'ops-team@company.com',
        'on-call@company.com',
        'emergency@company.com',
      ],
      cooldownPeriod: 5,
      escalationPolicy: {
        enabled: true,
        levels: [
          {
            delay: 5,
            severity: 'critical',
            additionalRecipients: ['cto@company.com'],
          },
        ],
      },
    },
    actions: {
      type: 'run_playbook',
      config: {
        playbookId: 'incident-response',
        autoExecute: true,
      },
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-10T11:20:00Z',
      createdBy: 'ops-admin',
      lastTriggered: '2025-10-12T03:45:00Z',
      triggerCount: 2,
      resolutionCount: 2,
      averageResolutionTime: 25.0,
    },
  },
  {
    id: 'rule-004',
    name: 'High Error Rate',
    description: 'Alert when error rate exceeds 10%',
    category: 'performance',
    severity: 'high',
    isActive: false,
    condition: {
      metric: 'error_rate',
      operator: 'gt',
      threshold: 10,
      duration: 3,
      aggregation: 'avg',
      evaluationWindow: 5,
    },
    filters: {},
    notifications: {
      channels: ['email'],
      recipients: ['dev-team@company.com'],
      cooldownPeriod: 20,
    },
    metadata: {
      created: '2025-10-08T13:15:00Z',
      updated: '2025-10-16T09:30:00Z',
      createdBy: 'dev-lead',
      lastTriggered: '2025-10-14T16:50:00Z',
      triggerCount: 3,
      resolutionCount: 3,
      averageResolutionTime: 12.0,
    },
  },
];

const mockAlerts: Alert[] = [
  {
    id: 'alert-001',
    ruleId: 'rule-001',
    ruleName: 'High Response Latency',
    severity: 'high',
    status: 'firing',
    startedAt: '2025-10-17T11:30:00Z',
    duration: 45,
    message:
      'Average response latency is 2450ms, exceeding threshold of 2000ms',
    details: {
      metric: 'response_latency',
      currentValue: 2450,
      threshold: 2000,
      condition: 'avg(response_latency) > 2000 for 5m',
    },
    context: {
      affectedEntities: ['api-gateway', 'search-service'],
      incidentId: 'INC-2025-001',
    },
    notifications: [
      {
        channel: 'email',
        recipient: 'ops-team@company.com',
        sentAt: '2025-10-17T11:30:30Z',
        status: 'sent',
      },
      {
        channel: 'slack',
        recipient: '#ops-alerts',
        sentAt: '2025-10-17T11:30:35Z',
        status: 'sent',
      },
    ],
  },
  {
    id: 'alert-002',
    ruleId: 'rule-002',
    ruleName: 'Low Answer Relevancy',
    severity: 'medium',
    status: 'acknowledged',
    startedAt: '2025-10-16T14:20:00Z',
    acknowledgedAt: '2025-10-16T14:35:00Z',
    acknowledgedBy: 'qa-lead',
    duration: 180,
    message: 'Answer relevancy dropped to 65%, below threshold of 70%',
    details: {
      metric: 'answer_relevancy',
      currentValue: 65,
      threshold: 70,
      condition: 'avg(answer_relevancy) < 70 for 10m',
    },
    context: {
      affectedEntities: ['rag-service'],
    },
    notifications: [
      {
        channel: 'email',
        recipient: 'qa-team@company.com',
        sentAt: '2025-10-16T14:20:30Z',
        status: 'sent',
      },
    ],
  },
  {
    id: 'alert-003',
    ruleId: 'rule-003',
    ruleName: 'System Health Check Failure',
    severity: 'critical',
    status: 'resolved',
    startedAt: '2025-10-12T03:45:00Z',
    resolvedAt: '2025-10-12T04:10:00Z',
    duration: 25,
    message: 'System health check failed: Database connection timeout',
    details: {
      metric: 'system_health',
      currentValue: 'unhealthy',
      threshold: 'unhealthy',
      condition: 'system_health == unhealthy',
    },
    context: {
      affectedEntities: ['database', 'cache-service'],
      incidentId: 'INC-2025-002',
    },
    notifications: [
      {
        channel: 'email',
        recipient: 'ops-team@company.com',
        sentAt: '2025-10-12T03:45:15Z',
        status: 'sent',
      },
      {
        channel: 'sms',
        recipient: '+1234567890',
        sentAt: '2025-10-12T03:45:20Z',
        status: 'sent',
      },
      {
        channel: 'webhook',
        recipient: 'incident-management',
        sentAt: '2025-10-12T03:45:25Z',
        status: 'sent',
      },
    ],
    resolution: {
      method: 'auto',
      notes: 'Automatic failover to backup database completed successfully',
    },
  },
];

const generateMockDashboard = (timeRange: string): AlertDashboard => {
  const hours =
    timeRange === '1h'
      ? 1
      : timeRange === '6h'
        ? 6
        : timeRange === '24h'
          ? 24
          : timeRange === '7d'
            ? 168
            : 720;
  const now = new Date();

  const alertsByTime = Array.from({ length: Math.min(hours, 24) }, (_, i) => {
    const timestamp = new Date(now.getTime() - (hours - i) * 60 * 60 * 1000);
    return {
      timestamp: timestamp.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      critical: Math.floor(Math.random() * 3),
      high: Math.floor(Math.random() * 5),
      medium: Math.floor(Math.random() * 8),
      low: Math.floor(Math.random() * 10),
    };
  });

  return {
    timeRange: timeRange as AlertDashboard['timeRange'],
    summary: {
      totalAlerts: mockAlerts.length + Math.floor(Math.random() * 20),
      activeAlerts: mockAlerts.filter((a) => a.status === 'firing').length,
      resolvedAlerts: mockAlerts.filter((a) => a.status === 'resolved').length,
      suppressedAlerts: Math.floor(Math.random() * 3),
      criticalAlerts: mockAlerts.filter(
        (a) => a.severity === 'critical' && a.status === 'firing'
      ).length,
      mttr: 12.5,
    },
    trends: {
      alertsByTime,
      alertsByCategory: [
        { category: 'Performance', count: Math.floor(Math.random() * 15) + 5 },
        { category: 'Quality', count: Math.floor(Math.random() * 10) + 3 },
        { category: 'Availability', count: Math.floor(Math.random() * 8) + 2 },
        { category: 'Security', count: Math.floor(Math.random() * 5) + 1 },
        { category: 'Business', count: Math.floor(Math.random() * 3) + 1 },
      ],
      topAlertRules: [
        { ruleName: 'High Response Latency', count: 12 },
        { ruleName: 'Low Answer Relevancy', count: 8 },
        { ruleName: 'System Health Check Failure', count: 5 },
        { ruleName: 'High Error Rate', count: 4 },
      ],
    },
    performance: {
      alertLatency: 1.2,
      notificationSuccess: 98.5,
      falsePositiveRate: 3.2,
    },
  };
};

const availableMetrics = [
  {
    id: 'response_latency',
    name: 'Response Latency',
    unit: 'ms',
    category: 'performance',
  },
  { id: 'error_rate', name: 'Error Rate', unit: '%', category: 'performance' },
  {
    id: 'throughput',
    name: 'Throughput',
    unit: 'req/s',
    category: 'performance',
  },
  {
    id: 'answer_relevancy',
    name: 'Answer Relevancy',
    unit: '%',
    category: 'quality',
  },
  { id: 'faithfulness', name: 'Faithfulness', unit: '%', category: 'quality' },
  {
    id: 'contextual_relevancy',
    name: 'Contextual Relevancy',
    unit: '%',
    category: 'quality',
  },
  {
    id: 'system_health',
    name: 'System Health',
    unit: 'status',
    category: 'availability',
  },
  {
    id: 'success_rate',
    name: 'Success Rate',
    unit: '%',
    category: 'availability',
  },
  {
    id: 'cache_hit_rate',
    name: 'Cache Hit Rate',
    unit: '%',
    category: 'performance',
  },
  { id: 'cpu_usage', name: 'CPU Usage', unit: '%', category: 'performance' },
  {
    id: 'memory_usage',
    name: 'Memory Usage',
    unit: '%',
    category: 'performance',
  },
  { id: 'disk_usage', name: 'Disk Usage', unit: '%', category: 'performance' },
];

const notificationChannels = [
  { id: 'email', name: 'Email', icon: <Mail className="h-4 w-4" /> },
  { id: 'slack', name: 'Slack', icon: <MessageSquare className="h-4 w-4" /> },
  { id: 'sms', name: 'SMS', icon: <Smartphone className="h-4 w-4" /> },
  { id: 'webhook', name: 'Webhook', icon: <Webhook className="h-4 w-4" /> },
  { id: 'in_app', name: 'In-App', icon: <Bell className="h-4 w-4" /> },
];

const PerformanceAlertingSystem: React.FC<PerformanceAlertingSystemProps> = ({
  onAlertRuleCreate,
  onAlertRuleUpdate,
  onAlertRuleDelete,
  onAlertAcknowledge,
  onAlertResolve,
  className,
}) => {
  const [alertRules, setAlertRules] = useState<AlertRule[]>(mockAlertRules);
  const [alerts, setAlerts] = useState<Alert[]>(mockAlerts);
  const [dashboard, setDashboard] = useState<AlertDashboard>(() =>
    generateMockDashboard('24h')
  );
  const [selectedRule, setSelectedRule] = useState<AlertRule | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [timeRange, setTimeRange] = useState('24h');
  const [isCreateRuleDialogOpen, setIsCreateRuleDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | null>(null);
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Update dashboard when time range changes
  React.useEffect(() => {
    setDashboard(generateMockDashboard(timeRange));
  }, [timeRange]);

  // Filter alerts
  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      const matchesSearch =
        alert.ruleName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        alert.message.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesSeverity =
        filterSeverity === 'all' || alert.severity === filterSeverity;
      const matchesStatus =
        filterStatus === 'all' || alert.status === filterStatus;
      return matchesSearch && matchesSeverity && matchesStatus;
    });
  }, [alerts, searchTerm, filterSeverity, filterStatus]);

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

  // Get severity icon
  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertCircle className="h-4 w-4" />;
      case 'high':
        return <AlertTriangle className="h-4 w-4" />;
      case 'medium':
        return <AlertTriangle className="h-4 w-4" />;
      case 'low':
        return <Info className="h-4 w-4" />;
      default:
        return <Bell className="h-4 w-4" />;
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'firing':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'resolved':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'acknowledged':
        return <Eye className="h-4 w-4 text-blue-500" />;
      case 'suppressed':
        return <VolumeX className="h-4 w-4 text-muted-foreground" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  // Get category icon
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'performance':
        return <Zap className="h-4 w-4" />;
      case 'quality':
        return <Target className="h-4 w-4" />;
      case 'availability':
        return <CheckCircle className="h-4 w-4" />;
      case 'security':
        return <AlertTriangle className="h-4 w-4" />;
      case 'business':
        return <TrendingUp className="h-4 w-4" />;
      default:
        return <Activity className="h-4 w-4" />;
    }
  };

  // Toggle rule status
  const toggleRuleStatus = useCallback((ruleId: string) => {
    setAlertRules((prev) =>
      prev.map((rule) =>
        rule.id === ruleId
          ? {
              ...rule,
              isActive: !rule.isActive,
              metadata: { ...rule.metadata, updated: new Date().toISOString() },
            }
          : rule
      )
    );
  }, []);

  // Acknowledge alert
  const acknowledgeAlert = useCallback(
    (alertId: string) => {
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === alertId
            ? {
                ...alert,
                status: 'acknowledged',
                acknowledgedAt: new Date().toISOString(),
                acknowledgedBy: 'current-user',
              }
            : alert
        )
      );
      onAlertAcknowledge?.(alertId);
    },
    [onAlertAcknowledge]
  );

  // Resolve alert
  const resolveAlert = useCallback(
    (alertId: string, notes?: string) => {
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === alertId
            ? {
                ...alert,
                status: 'resolved',
                resolvedAt: new Date().toISOString(),
                resolution: {
                  method: 'manual',
                  resolvedBy: 'current-user',
                  notes,
                },
              }
            : alert
        )
      );
      onAlertResolve?.(alertId, notes);
    },
    [onAlertResolve]
  );

  // Delete rule
  const handleDeleteRule = useCallback(
    (ruleId: string) => {
      setAlertRules((prev) => prev.filter((r) => r.id !== ruleId));
      onAlertRuleDelete?.(ruleId);
    },
    [onAlertRuleDelete]
  );

  // Save rule
  const handleSaveRule = useCallback(
    (ruleData: Partial<AlertRule>) => {
      if (editingRule) {
        // Update existing rule
        const updatedRule = {
          ...editingRule,
          ...ruleData,
          metadata: {
            ...editingRule.metadata,
            ...ruleData.metadata,
            updated: new Date().toISOString(),
          },
        };
        setAlertRules((prev) =>
          prev.map((r) => (r.id === editingRule.id ? updatedRule : r))
        );
        onAlertRuleUpdate?.(updatedRule);
        setEditingRule(null);
      } else {
        // Create new rule
        const newRule: AlertRule = {
          id: `rule-${Date.now()}`,
          name: ruleData.name || 'New Alert Rule',
          description: ruleData.description || '',
          category: ruleData.category || 'performance',
          severity: ruleData.severity || 'medium',
          isActive: ruleData.isActive ?? true,
          condition: ruleData.condition || {
            metric: 'response_latency',
            operator: 'gt',
            threshold: 2000,
          },
          filters: ruleData.filters || {},
          notifications: ruleData.notifications || {
            channels: ['email'],
            recipients: [],
            cooldownPeriod: 15,
          },
          metadata: {
            created: new Date().toISOString(),
            updated: new Date().toISOString(),
            createdBy: 'current-user',
            triggerCount: 0,
            resolutionCount: 0,
          },
        };
        setAlertRules((prev) => [...prev, newRule]);
        onAlertRuleCreate?.(newRule);
      }
      setIsCreateRuleDialogOpen(false);
    },
    [editingRule, onAlertRuleCreate]
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Performance Alerting
          </h2>
          <p className="text-foreground">
            Monitor system performance and get notified about issues
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last hour</SelectItem>
              <SelectItem value="6h">Last 6 hours</SelectItem>
              <SelectItem value="24h">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
            </SelectContent>
          </Select>
          <Dialog
            open={isCreateRuleDialogOpen}
            onOpenChange={setIsCreateRuleDialogOpen}
          >
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Alert Rule
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>
                  {editingRule ? 'Edit Alert Rule' : 'Create Alert Rule'}
                </DialogTitle>
                <DialogDescription>
                  Define conditions for triggering automated alerts
                </DialogDescription>
              </DialogHeader>
              <AlertRuleForm
                rule={editingRule}
                onSubmit={handleSaveRule}
                onCancel={() => {
                  setIsCreateRuleDialogOpen(false);
                  setEditingRule(null);
                }}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Bell className="h-5 w-5 text-blue-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.totalAlerts}
                </div>
                <div className="text-sm text-foreground">Total Alerts</div>
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
                  {dashboard.summary.activeAlerts}
                </div>
                <div className="text-sm text-foreground">Active</div>
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
                  {dashboard.summary.resolvedAlerts}
                </div>
                <div className="text-sm text-foreground">Resolved</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.criticalAlerts}
                </div>
                <div className="text-sm text-foreground">Critical</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Clock className="h-5 w-5 text-purple-500" />
              <div>
                <div className="text-2xl font-bold">
                  {dashboard.summary.mttr}m
                </div>
                <div className="text-sm text-foreground">MTTR</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger
            value="dashboard"
            className="flex items-center space-x-2"
          >
            <Activity className="h-4 w-4" />
            <span>Dashboard</span>
          </TabsTrigger>
          <TabsTrigger value="alerts" className="flex items-center space-x-2">
            <Bell className="h-4 w-4" />
            <span>Alerts</span>
          </TabsTrigger>
          <TabsTrigger value="rules" className="flex items-center space-x-2">
            <Settings className="h-4 w-4" />
            <span>Rules</span>
          </TabsTrigger>
          <TabsTrigger
            value="performance"
            className="flex items-center space-x-2"
          >
            <TrendingUp className="h-4 w-4" />
            <span>Performance</span>
          </TabsTrigger>
        </TabsList>

        {/* Dashboard Tab */}
        <TabsContent value="dashboard" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Alert Trends</CardTitle>
                <CardDescription>Alert volume over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={dashboard.trends.alertsByTime}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="timestamp" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="critical"
                        stackId="1"
                        stroke="#ef4444"
                        fill="#ef4444"
                      />
                      <Area
                        type="monotone"
                        dataKey="high"
                        stackId="1"
                        stroke="#f59e0b"
                        fill="#f59e0b"
                      />
                      <Area
                        type="monotone"
                        dataKey="medium"
                        stackId="1"
                        stroke="#eab308"
                        fill="#eab308"
                      />
                      <Area
                        type="monotone"
                        dataKey="low"
                        stackId="1"
                        stroke="#3b82f6"
                        fill="#3b82f6"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Alerts by Category</CardTitle>
                <CardDescription>
                  Distribution across different categories
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboard.trends.alertsByCategory}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="category" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Top Alert Rules</CardTitle>
                <CardDescription>
                  Most frequently triggered rules
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {dashboard.trends.topAlertRules.map((rule, index) => (
                    <div
                      key={rule.ruleName}
                      className="flex items-center justify-between p-3 border rounded-lg"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/20 rounded-full flex items-center justify-center">
                          <span className="text-sm font-medium">
                            #{index + 1}
                          </span>
                        </div>
                        <span className="font-medium">{rule.ruleName}</span>
                      </div>
                      <Badge variant="outline">{rule.count} alerts</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Notification Performance</CardTitle>
                <CardDescription>
                  Alert system performance metrics
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Alert Latency</span>
                      <span className="text-sm">
                        {dashboard.performance.alertLatency}s
                      </span>
                    </div>
                    <Progress
                      value={(dashboard.performance.alertLatency / 5) * 100}
                      className="h-2"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        Notification Success
                      </span>
                      <span className="text-sm">
                        {dashboard.performance.notificationSuccess}%
                      </span>
                    </div>
                    <Progress
                      value={dashboard.performance.notificationSuccess}
                      className="h-2"
                    />
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        False Positive Rate
                      </span>
                      <span className="text-sm">
                        {dashboard.performance.falsePositiveRate}%
                      </span>
                    </div>
                    <Progress
                      value={dashboard.performance.falsePositiveRate}
                      className="h-2"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center space-x-4 mb-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search alerts..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Select
                  value={filterSeverity}
                  onValueChange={setFilterSeverity}
                >
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Severity" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Severities</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="firing">Firing</SelectItem>
                    <SelectItem value="acknowledged">Acknowledged</SelectItem>
                    <SelectItem value="resolved">Resolved</SelectItem>
                    <SelectItem value="suppressed">Suppressed</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3">
                {filteredAlerts.map((alert) => (
                  <div key={alert.id} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        {getSeverityIcon(alert.severity)}
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <h4 className="font-medium">{alert.ruleName}</h4>
                            <Badge className={getSeverityColor(alert.severity)}>
                              {alert.severity}
                            </Badge>
                            <Badge variant="outline">
                              {getStatusIcon(alert.status)}
                              <span className="ml-1">{alert.status}</span>
                            </Badge>
                          </div>
                          <p className="text-sm text-foreground mb-2">
                            {alert.message}
                          </p>
                          <div className="text-xs text-muted-foreground space-y-1">
                            <div>
                              Started:{' '}
                              {new Date(alert.startedAt).toLocaleString()}
                              {alert.duration &&
                                ` • Duration: ${alert.duration}m`}
                            </div>
                            {alert.acknowledgedAt && (
                              <div>
                                Acknowledged by {alert.acknowledgedBy} at{' '}
                                {new Date(
                                  alert.acknowledgedAt
                                ).toLocaleString()}
                              </div>
                            )}
                            {alert.resolvedAt && (
                              <div>
                                Resolved at{' '}
                                {new Date(alert.resolvedAt).toLocaleString()}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1">
                        {alert.status === 'firing' && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => acknowledgeAlert(alert.id)}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              Acknowledge
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => resolveAlert(alert.id)}
                            >
                              <CheckCircle className="h-4 w-4 mr-1" />
                              Resolve
                            </Button>
                          </>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedAlert(alert)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Rules Tab */}
        <TabsContent value="rules" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {alertRules.map((rule) => (
              <Card key={rule.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      {getCategoryIcon(rule.category)}
                      <div>
                        <CardTitle className="text-lg">{rule.name}</CardTitle>
                        <CardDescription className="mt-1">
                          {rule.description}
                        </CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge className={getSeverityColor(rule.severity)}>
                        {rule.severity}
                      </Badge>
                      <Switch
                        checked={rule.isActive}
                        onCheckedChange={() => toggleRuleStatus(rule.id)}
                      />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        Condition
                      </div>
                      <div className="text-sm">
                        {rule.condition.metric} {rule.condition.operator}{' '}
                        {rule.condition.threshold}
                        {rule.condition.duration &&
                          ` for ${rule.condition.duration}m`}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        Notifications
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {rule.notifications.channels.map((channel) => {
                          const ch = notificationChannels.find(
                            (c) => c.id === channel
                          );
                          return (
                            <Badge
                              key={channel}
                              variant="outline"
                              className="text-xs"
                            >
                              {ch?.icon}
                              <span className="ml-1">{ch?.name}</span>
                            </Badge>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-sm text-foreground">
                    <div>
                      Triggered: {rule.metadata.triggerCount} times
                      {rule.metadata.lastTriggered && (
                        <>
                          {' • '}Last:{' '}
                          {new Date(
                            rule.metadata.lastTriggered
                          ).toLocaleDateString()}
                        </>
                      )}
                    </div>
                    {rule.metadata.averageResolutionTime && (
                      <div>
                        Avg resolution:{' '}
                        {rule.metadata.averageResolutionTime.toFixed(1)}m
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {rule.filters.tags?.map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <div className="flex items-center space-x-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedRule(rule)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingRule(rule);
                          setIsCreateRuleDialogOpen(true);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteRule(rule.id)}
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

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Alert System Performance</CardTitle>
                <CardDescription>
                  Key performance indicators for the alerting system
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        Mean Time To Resolution (MTTR)
                      </span>
                      <span className="text-sm font-bold">
                        {dashboard.summary.mttr} minutes
                      </span>
                    </div>
                    <Progress
                      value={(dashboard.summary.mttr / 30) * 100}
                      className="h-2"
                    />
                    <div className="text-xs text-muted-foreground mt-1">
                      Target: &lt; 30 minutes
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Alert Latency</span>
                      <span className="text-sm font-bold">
                        {dashboard.performance.alertLatency}s
                      </span>
                    </div>
                    <Progress
                      value={(dashboard.performance.alertLatency / 5) * 100}
                      className="h-2"
                    />
                    <div className="text-xs text-muted-foreground mt-1">
                      Target: &lt; 5 seconds
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        Notification Success Rate
                      </span>
                      <span className="text-sm font-bold">
                        {dashboard.performance.notificationSuccess}%
                      </span>
                    </div>
                    <Progress
                      value={dashboard.performance.notificationSuccess}
                      className="h-2"
                    />
                    <div className="text-xs text-muted-foreground mt-1">
                      Target: &gt; 95%
                    </div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        False Positive Rate
                      </span>
                      <span className="text-sm font-bold">
                        {dashboard.performance.falsePositiveRate}%
                      </span>
                    </div>
                    <Progress
                      value={dashboard.performance.falsePositiveRate}
                      className="h-2"
                    />
                    <div className="text-xs text-muted-foreground mt-1">
                      Target: &lt; 5%
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Rule Effectiveness</CardTitle>
                <CardDescription>
                  How well your alert rules are performing
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {alertRules.slice(0, 5).map((rule) => {
                    const effectiveness =
                      rule.metadata.triggerCount > 0
                        ? (rule.metadata.resolutionCount /
                            rule.metadata.triggerCount) *
                          100
                        : 0;

                    return (
                      <div
                        key={rule.id}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <div className="flex items-center space-x-3">
                          {getSeverityIcon(rule.severity)}
                          <div>
                            <div className="font-medium">{rule.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {rule.metadata.triggerCount} triggered •{' '}
                              {rule.metadata.resolutionCount} resolved
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold">
                            {effectiveness.toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">
                            effective
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Alert Rule Form Component
const AlertRuleForm: React.FC<AlertRuleFormProps> = ({
  rule,
  onSubmit,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    name: rule?.name || '',
    description: rule?.description || '',
    category: rule?.category || 'performance',
    severity: rule?.severity || 'medium',
    metric: rule?.condition.metric || 'response_latency',
    operator: rule?.condition.operator || 'gt',
    threshold: rule?.condition.threshold || '',
    duration: rule?.condition.duration || 5,
    aggregation: rule?.condition.aggregation || 'avg',
    evaluationWindow: rule?.condition.evaluationWindow || 5,
    notifyEmail: rule?.notifications.channels.includes('email') || false,
    notifySlack: rule?.notifications.channels.includes('slack') || false,
    notifySms: rule?.notifications.channels.includes('sms') || false,
    notifyWebhook: rule?.notifications.channels.includes('webhook') || false,
    recipients: rule?.notifications.recipients?.join(', ') || '',
    cooldownPeriod: rule?.notifications.cooldownPeriod || 15,
    isActive: rule?.isActive ?? true,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const ruleData: Partial<AlertRule> = {
      name: formData.name,
      description: formData.description,
      category: formData.category as any,
      severity: formData.severity as any,
      isActive: formData.isActive,
      condition: {
        metric: formData.metric,
        operator: formData.operator as any,
        threshold: isNaN(Number(formData.threshold))
          ? formData.threshold
          : Number(formData.threshold),
        duration: formData.duration,
        aggregation: formData.aggregation as any,
        evaluationWindow: formData.evaluationWindow,
      },
      notifications: {
        channels: [
          ...(formData.notifyEmail ? ['email'] : []),
          ...(formData.notifySlack ? ['slack'] : []),
          ...(formData.notifySms ? ['sms'] : []),
          ...(formData.notifyWebhook ? ['webhook'] : []),
        ] as any,
        recipients: formData.recipients
          .split(',')
          .map((r) => r.trim())
          .filter(Boolean),
        cooldownPeriod: formData.cooldownPeriod,
      },
    };

    onSubmit(ruleData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="rule-name">Rule Name *</Label>
          <Input
            id="rule-name"
            value={formData.name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, name: e.target.value }))
            }
            placeholder="Enter alert rule name"
            required
          />
        </div>
        <div>
          <Label htmlFor="rule-severity">Severity *</Label>
          <Select
            value={formData.severity}
            onValueChange={(value) =>
              setFormData((prev) => ({
                ...prev,
                severity: value as 'low' | 'medium' | 'high' | 'critical',
              }))
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

      <div>
        <Label htmlFor="rule-description">Description</Label>
        <Textarea
          id="rule-description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Describe when this alert should trigger"
          rows={3}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="rule-category">Category</Label>
          <Select
            value={formData.category}
            onValueChange={(value) =>
              setFormData((prev) => ({
                ...prev,
                category: value as
                  | 'performance'
                  | 'quality'
                  | 'availability'
                  | 'security'
                  | 'business',
              }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="performance">Performance</SelectItem>
              <SelectItem value="quality">Quality</SelectItem>
              <SelectItem value="availability">Availability</SelectItem>
              <SelectItem value="security">Security</SelectItem>
              <SelectItem value="business">Business</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="rule-metric">Metric *</Label>
          <Select
            value={formData.metric}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, metric: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {availableMetrics.map((metric) => (
                <SelectItem key={metric.id} value={metric.id}>
                  {metric.name} ({metric.unit})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Alert Condition</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="operator">Operator</Label>
            <Select
              value={formData.operator}
              onValueChange={(value) =>
                setFormData((prev) => ({
                  ...prev,
                  operator: value as
                    | 'gt'
                    | 'gte'
                    | 'lt'
                    | 'lte'
                    | 'eq'
                    | 'ne'
                    | 'contains'
                    | 'not_contains',
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gt">Greater than</SelectItem>
                <SelectItem value="gte">Greater than or equal</SelectItem>
                <SelectItem value="lt">Less than</SelectItem>
                <SelectItem value="lte">Less than or equal</SelectItem>
                <SelectItem value="eq">Equal to</SelectItem>
                <SelectItem value="ne">Not equal to</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="threshold">Threshold *</Label>
            <Input
              id="threshold"
              value={formData.threshold}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, threshold: e.target.value }))
              }
              placeholder="e.g., 2000 or unhealthy"
              required
            />
          </div>
          <div>
            <Label htmlFor="duration">Duration (minutes)</Label>
            <Input
              id="duration"
              type="number"
              min="1"
              value={formData.duration}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  duration: parseInt(e.target.value, 10),
                }))
              }
            />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <Label htmlFor="aggregation">Aggregation</Label>
            <Select
              value={formData.aggregation}
              onValueChange={(value) =>
                setFormData((prev) => ({
                  ...prev,
                  aggregation: value as 'avg' | 'min' | 'max' | 'sum' | 'count',
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="avg">Average</SelectItem>
                <SelectItem value="min">Minimum</SelectItem>
                <SelectItem value="max">Maximum</SelectItem>
                <SelectItem value="sum">Sum</SelectItem>
                <SelectItem value="count">Count</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="evaluation-window">
              Evaluation Window (minutes)
            </Label>
            <Input
              id="evaluation-window"
              type="number"
              min="1"
              value={formData.evaluationWindow}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  evaluationWindow: parseInt(e.target.value, 10),
                }))
              }
            />
          </div>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Notification Settings</h4>
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center space-x-2">
              <Switch
                id="notify-email"
                checked={formData.notifyEmail}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({ ...prev, notifyEmail: checked }))
                }
              />
              <Label htmlFor="notify-email">Email</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="notify-slack"
                checked={formData.notifySlack}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({ ...prev, notifySlack: checked }))
                }
              />
              <Label htmlFor="notify-slack">Slack</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="notify-sms"
                checked={formData.notifySms}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({ ...prev, notifySms: checked }))
                }
              />
              <Label htmlFor="notify-sms">SMS</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="notify-webhook"
                checked={formData.notifyWebhook}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({ ...prev, notifyWebhook: checked }))
                }
              />
              <Label htmlFor="notify-webhook">Webhook</Label>
            </div>
          </div>
          <div>
            <Label htmlFor="recipients">Recipients</Label>
            <Input
              id="recipients"
              value={formData.recipients}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, recipients: e.target.value }))
              }
              placeholder="email1@company.com, #slack-channel, +1234567890"
            />
          </div>
          <div>
            <Label htmlFor="cooldown">Cooldown Period (minutes)</Label>
            <Input
              id="cooldown"
              type="number"
              min="0"
              value={formData.cooldownPeriod}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  cooldownPeriod: parseInt(e.target.value, 10),
                }))
              }
            />
            <p className="text-xs text-muted-foreground mt-1">
              Minimum time between consecutive alerts for this rule
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="is-active"
          checked={formData.isActive}
          onCheckedChange={(checked) =>
            setFormData((prev) => ({ ...prev, isActive: checked }))
          }
        />
        <Label htmlFor="is-active">Activate Rule</Label>
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Bell className="h-4 w-4 mr-2" />
          {rule ? 'Update Rule' : 'Create Rule'}
        </Button>
      </div>
    </form>
  );
};

export default PerformanceAlertingSystem;

interface PerformanceAlertingSystemProps {
  onAlertRuleCreate?: (rule: AlertRule) => void;
  onAlertRuleUpdate?: (rule: AlertRule) => void;
  onAlertRuleDelete?: (ruleId: string) => void;
  onAlertAcknowledge?: (alertId: string) => void;
  onAlertResolve?: (alertId: string, notes?: string) => void;
  className?: string;
}

interface AlertRuleFormProps {
  rule?: AlertRule | null;
  onSubmit: (rule: Partial<AlertRule>) => void;
  onCancel: () => void;
}
