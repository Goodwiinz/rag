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
  Calendar,
  Clock,
  Play,
  Pause,
  Square,
  RotateCcw,
  Settings,
  Plus,
  Edit,
  Trash2,
  Eye,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Timer,
  Bell,
  Mail,
  Users,
  FileText,
  BarChart3,
  Activity,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Info,
} from 'lucide-react';

// Types
interface EvaluationSchedule {
  id: string;
  name: string;
  description: string;
  type: 'test_suite' | 'metric_collection' | 'report_generation' | 'health_check';
  target: {
    type: 'test_suite' | 'metric' | 'report' | 'system';
    id: string;
    name: string;
  };
  schedule: {
    frequency: 'minutes' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'cron';
    interval?: number; // For minutes frequency
    time?: string; // HH:MM format for daily/weekly
    dayOfWeek?: number; // 0-6 for weekly
    dayOfMonth?: number; // 1-31 for monthly
    cronExpression?: string; // Custom cron expression
    timezone: string;
  };
  execution: {
    timeout: number; // minutes
    retryPolicy: {
      maxRetries: number;
      retryDelay: number; // minutes
      backoffMultiplier: number;
    };
    parallelExecution: boolean;
    maxConcurrency: number;
  };
  notifications: {
    onSuccess: boolean;
    onFailure: boolean;
    onTimeout: boolean;
    recipients: string[];
    channels: ('email' | 'slack' | 'webhook' | 'in_app')[];
    customMessage?: string;
  };
  conditions: {
    minSuccessRate?: number;
    maxExecutionTime?: number; // minutes
    requirePreviousSuccess?: boolean;
    skipOnHolidays?: boolean;
    businessHoursOnly?: boolean;
  };
  isActive: boolean;
  priority: 'low' | 'medium' | 'high' | 'critical';
  tags: string[];
  created: string;
  updated: string;
  createdBy: string;
  lastRun?: string;
  nextRun?: string | null;
  runCount: number;
  successCount: number;
  failureCount: number;
  averageDuration: number; // minutes
}

interface ScheduleExecution {
  id: string;
  scheduleId: string;
  scheduleName: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timeout' | 'cancelled';
  startTime: string;
  endTime?: string;
  duration?: number; // minutes
  triggeredBy: 'schedule' | 'manual' | 'retry';
  result?: {
    success: boolean;
    data?: any;
    error?: string;
    metrics?: Record<string, number>;
  };
  logs: Array<{
    timestamp: string;
    level: 'info' | 'warning' | 'error';
    message: string;
  }>;
  retryCount: number;
}

interface ScheduleTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  type: EvaluationSchedule['type'];
  schedule: Partial<EvaluationSchedule['schedule']>;
  execution: Partial<EvaluationSchedule['execution']>;
  notifications: Partial<EvaluationSchedule['notifications']>;
}

// Mock data
const mockSchedules: EvaluationSchedule[] = [
  {
    id: 'sched-001',
    name: 'Daily Quality Assurance',
    description: 'Run comprehensive test suite to ensure system quality',
    type: 'test_suite',
    target: {
      type: 'test_suite',
      id: 'ts-001',
      name: 'Core RAG Functionality',
    },
    schedule: {
      frequency: 'daily',
      time: '08:00',
      timezone: 'UTC',
    },
    execution: {
      timeout: 30,
      retryPolicy: {
        maxRetries: 2,
        retryDelay: 5,
        backoffMultiplier: 2,
      },
      parallelExecution: true,
      maxConcurrency: 5,
    },
    notifications: {
      onSuccess: false,
      onFailure: true,
      onTimeout: true,
      recipients: ['qa-team@company.com', 'dev-team@company.com'],
      channels: ['email', 'slack'],
    },
    conditions: {
      minSuccessRate: 90,
      maxExecutionTime: 25,
      businessHoursOnly: false,
    },
    isActive: true,
    priority: 'high',
    tags: ['daily', 'quality', 'core'],
    created: '2025-10-01T00:00:00Z',
    updated: '2025-10-15T14:30:00Z',
    createdBy: 'qa-lead',
    lastRun: '2025-10-17T08:00:00Z',
    nextRun: '2025-10-18T08:00:00Z',
    runCount: 15,
    successCount: 14,
    failureCount: 1,
    averageDuration: 18.5,
  },
  {
    id: 'sched-002',
    name: 'Hourly Performance Metrics',
    description: 'Collect custom performance metrics every hour',
    type: 'metric_collection',
    target: {
      type: 'metric',
      id: 'metric-001',
      name: 'Response Quality Index',
    },
    schedule: {
      frequency: 'hourly',
      timezone: 'UTC',
    },
    execution: {
      timeout: 5,
      retryPolicy: {
        maxRetries: 3,
        retryDelay: 1,
        backoffMultiplier: 1.5,
      },
      parallelExecution: false,
      maxConcurrency: 1,
    },
    notifications: {
      onSuccess: false,
      onFailure: true,
      onTimeout: false,
      recipients: ['ops-team@company.com'],
      channels: ['email'],
    },
    conditions: {
      requirePreviousSuccess: false,
    },
    isActive: true,
    priority: 'medium',
    tags: ['hourly', 'metrics', 'performance'],
    created: '2025-10-05T09:00:00Z',
    updated: '2025-10-14T16:45:00Z',
    createdBy: 'ops-admin',
    lastRun: '2025-10-17T11:00:00Z',
    nextRun: '2025-10-17T12:00:00Z',
    runCount: 280,
    successCount: 275,
    failureCount: 5,
    averageDuration: 2.3,
  },
  {
    id: 'sched-003',
    name: 'Weekly Performance Report',
    description: 'Generate comprehensive weekly performance report',
    type: 'report_generation',
    target: {
      type: 'report',
      id: 'perf-weekly',
      name: 'Weekly Performance Report',
    },
    schedule: {
      frequency: 'weekly',
      dayOfWeek: 1, // Monday
      time: '09:00',
      timezone: 'UTC',
    },
    execution: {
      timeout: 15,
      retryPolicy: {
        maxRetries: 1,
        retryDelay: 10,
        backoffMultiplier: 1,
      },
      parallelExecution: false,
      maxConcurrency: 1,
    },
    notifications: {
      onSuccess: true,
      onFailure: true,
      onTimeout: true,
      recipients: ['management@company.com', 'stakeholders@company.com'],
      channels: ['email'],
    },
    conditions: {
      businessHoursOnly: true,
      skipOnHolidays: true,
    },
    isActive: true,
    priority: 'medium',
    tags: ['weekly', 'reports', 'management'],
    created: '2025-10-01T00:00:00Z',
    updated: '2025-10-10T13:20:00Z',
    createdBy: 'admin',
    lastRun: '2025-10-14T09:00:00Z',
    nextRun: '2025-10-21T09:00:00Z',
    runCount: 3,
    successCount: 3,
    failureCount: 0,
    averageDuration: 12.7,
  },
  {
    id: 'sched-004',
    name: 'System Health Check',
    description: 'Monitor system health and detect anomalies',
    type: 'health_check',
    target: {
      type: 'system',
      id: 'system-health',
      name: 'System Health',
    },
    schedule: {
      frequency: 'minutes',
      interval: 15,
      timezone: 'UTC',
    },
    execution: {
      timeout: 2,
      retryPolicy: {
        maxRetries: 1,
        retryDelay: 1,
        backoffMultiplier: 1,
      },
      parallelExecution: false,
      maxConcurrency: 1,
    },
    notifications: {
      onSuccess: false,
      onFailure: true,
      onTimeout: true,
      recipients: ['ops-team@company.com', 'on-call@company.com'],
      channels: ['email', 'slack', 'webhook'],
    },
    conditions: {
      maxExecutionTime: 1,
    },
    isActive: false,
    priority: 'critical',
    tags: ['health', 'monitoring', 'critical'],
    created: '2025-10-08T11:30:00Z',
    updated: '2025-10-16T10:15:00Z',
    createdBy: 'ops-admin',
    lastRun: '2025-10-16T22:45:00Z',
    nextRun: null, // Inactive
    runCount: 1250,
    successCount: 1245,
    failureCount: 5,
    averageDuration: 0.8,
  },
];

const scheduleTemplates: ScheduleTemplate[] = [
  {
    id: 'template-001',
    name: 'Daily Test Suite',
    description: 'Run test suite daily at a specific time',
    category: 'Quality Assurance',
    type: 'test_suite',
    schedule: {
      frequency: 'daily',
      time: '08:00',
      timezone: 'UTC',
    },
    execution: {
      timeout: 30,
      parallelExecution: true,
      maxConcurrency: 5,
    },
    notifications: {
      onFailure: true,
      channels: ['email'],
    },
  },
  {
    id: 'template-002',
    name: 'Hourly Metrics Collection',
    description: 'Collect performance metrics every hour',
    category: 'Performance Monitoring',
    type: 'metric_collection',
    schedule: {
      frequency: 'hourly',
      timezone: 'UTC',
    },
    execution: {
      timeout: 5,
      parallelExecution: false,
      maxConcurrency: 1,
    },
    notifications: {
      onFailure: true,
      channels: ['email'],
    },
  },
  {
    id: 'template-003',
    name: 'Weekly Report Generation',
    description: 'Generate and distribute weekly reports',
    category: 'Reporting',
    type: 'report_generation',
    schedule: {
      frequency: 'weekly',
      dayOfWeek: 1,
      time: '09:00',
      timezone: 'UTC',
    },
    execution: {
      timeout: 15,
      parallelExecution: false,
      maxConcurrency: 1,
    },
    notifications: {
      onSuccess: true,
      onFailure: true,
      channels: ['email'],
    },
  },
];

const mockExecutions: ScheduleExecution[] = [
  {
    id: 'exec-001',
    scheduleId: 'sched-001',
    scheduleName: 'Daily Quality Assurance',
    status: 'completed',
    startTime: '2025-10-17T08:00:00Z',
    endTime: '2025-10-17T08:18:30Z',
    duration: 18.5,
    triggeredBy: 'schedule',
    result: {
      success: true,
      metrics: {
        totalTests: 45,
        passedTests: 42,
        failedTests: 3,
        successRate: 93.3,
      },
    },
    logs: [
      { timestamp: '2025-10-17T08:00:00Z', level: 'info', message: 'Starting scheduled execution' },
      { timestamp: '2025-10-17T08:00:15Z', level: 'info', message: 'Running test suite: Core RAG Functionality' },
      { timestamp: '2025-10-17T08:18:25Z', level: 'info', message: 'Test execution completed' },
      { timestamp: '2025-10-17T08:18:30Z', level: 'info', message: 'Execution completed successfully' },
    ],
    retryCount: 0,
  },
  {
    id: 'exec-002',
    scheduleId: 'sched-002',
    scheduleName: 'Hourly Performance Metrics',
    status: 'failed',
    startTime: '2025-10-17T10:00:00Z',
    endTime: '2025-10-17T10:05:15Z',
    duration: 5.25,
    triggeredBy: 'schedule',
    result: {
      success: false,
      error: 'Timeout: Metric calculation exceeded 5 minute limit',
    },
    logs: [
      { timestamp: '2025-10-17T10:00:00Z', level: 'info', message: 'Starting metric collection' },
      { timestamp: '2025-10-17T10:01:30Z', level: 'warning', message: 'Metric calculation taking longer than expected' },
      { timestamp: '2025-10-17T10:05:00Z', level: 'error', message: 'Timeout reached' },
      { timestamp: '2025-10-17T10:05:15Z', level: 'error', message: 'Execution failed: Timeout' },
    ],
    retryCount: 1,
  },
];

const timezones = [
  { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'Europe/Paris', label: 'Paris (CET/CEST)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
];

const AutomatedEvaluationScheduling: React.FC<AutomatedEvaluationSchedulingProps> = ({
  onScheduleCreate,
  onScheduleUpdate,
  onScheduleDelete,
  onExecutionTrigger,
  className,
}) => {
  const [schedules, setSchedules] = useState<EvaluationSchedule[]>(mockSchedules);
  const [executions, setExecutions] = useState<ScheduleExecution[]>(mockExecutions);
  const [selectedSchedule, setSelectedSchedule] = useState<EvaluationSchedule | null>(null);
  const [activeTab, setActiveTab] = useState('schedules');
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<EvaluationSchedule | null>(null);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [expandedSchedules, setExpandedSchedules] = useState<Set<string>>(new Set());

  // Filter schedules
  const filteredSchedules = useMemo(() => {
    return schedules.filter(schedule => {
      const matchesStatus = filterStatus === 'all' ||
                           (filterStatus === 'active' && schedule.isActive) ||
                           (filterStatus === 'inactive' && !schedule.isActive);
      const matchesType = filterType === 'all' || schedule.type === filterType;
      return matchesStatus && matchesType;
    });
  }, [schedules, filterStatus, filterType]);

  // Get upcoming runs
  const upcomingRuns = useMemo(() => {
    return schedules
      .filter(s => s.isActive && s.nextRun)
      .sort((a, b) => new Date(a.nextRun!).getTime() - new Date(b.nextRun!).getTime())
      .slice(0, 5);
  }, [schedules]);

  // Get recent executions
  const recentExecutions = useMemo(() => {
    return executions
      .sort((a, b) => new Date(b.startTime).getTime() - new Date(a.startTime).getTime())
      .slice(0, 10);
  }, [executions]);

  // Toggle schedule expansion
  const toggleScheduleExpansion = useCallback((scheduleId: string) => {
    setExpandedSchedules(prev => {
      const newSet = new Set(prev);
      if (newSet.has(scheduleId)) {
        newSet.delete(scheduleId);
      } else {
        newSet.add(scheduleId);
      }
      return newSet;
    });
  }, []);

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'timeout':
        return <Timer className="h-4 w-4 text-orange-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-gray-500" />;
    }
  };

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'low': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // Get type icon
  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'test_suite': return <FileText className="h-4 w-4" />;
      case 'metric_collection': return <BarChart3 className="h-4 w-4" />;
      case 'report_generation': return <Activity className="h-4 w-4" />;
      case 'health_check': return <CheckCircle className="h-4 w-4" />;
      default: return <Clock className="h-4 w-4" />;
    }
  };

  // Trigger manual execution
  const triggerExecution = useCallback(async (scheduleId: string) => {
    const schedule = schedules.find(s => s.id === scheduleId);
    if (!schedule) return;

    const execution: ScheduleExecution = {
      id: `exec-${Date.now()}`,
      scheduleId,
      scheduleName: schedule.name,
      status: 'running',
      startTime: new Date().toISOString(),
      triggeredBy: 'manual',
      logs: [
        { timestamp: new Date().toISOString(), level: 'info', message: 'Manual execution triggered' }
      ],
      retryCount: 0,
    };

    setExecutions(prev => [execution, ...prev]);
    onExecutionTrigger?.(scheduleId, execution.id);

    // Simulate execution completion
    setTimeout(() => {
      const isSuccess = Math.random() > 0.2;
      setExecutions(prev => prev.map(e =>
        e.id === execution.id
          ? {
              ...e,
              status: isSuccess ? 'completed' : 'failed',
              endTime: new Date().toISOString(),
              duration: Math.random() * 20 + 5,
              result: {
                success: isSuccess,
                metrics: {
                  executionTime: Math.random() * 20 + 5,
                  successRate: Math.random() * 15 + 85,
                },
              },
              logs: [
                ...e.logs,
                { timestamp: new Date().toISOString(), level: 'info', message: 'Execution completed' }
              ]
            }
          : e
      ));
    }, 3000 + Math.random() * 5000);
  }, [schedules, onExecutionTrigger]);

  // Toggle schedule status
  const toggleScheduleStatus = useCallback((scheduleId: string) => {
    setSchedules(prev => prev.map(schedule =>
      schedule.id === scheduleId
        ? { ...schedule, isActive: !schedule.isActive, updated: new Date().toISOString() }
        : schedule
    ));
  }, []);

  // Delete schedule
  const handleDeleteSchedule = useCallback((scheduleId: string) => {
    setSchedules(prev => prev.filter(s => s.id !== scheduleId));
    onScheduleDelete?.(scheduleId);
  }, [onScheduleDelete]);

  // Save schedule
  const handleSaveSchedule = useCallback((scheduleData: Partial<EvaluationSchedule>) => {
    if (editingSchedule) {
      // Update existing schedule
      const updatedSchedule = { ...editingSchedule, ...scheduleData, updated: new Date().toISOString() };
      setSchedules(prev => prev.map(s =>
        s.id === editingSchedule.id
          ? updatedSchedule
          : s
      ));
      onScheduleUpdate?.(updatedSchedule);
      setEditingSchedule(null);
    } else {
      // Create new schedule
      const newSchedule: EvaluationSchedule = {
        id: `sched-${Date.now()}`,
        name: scheduleData.name || 'New Schedule',
        description: scheduleData.description || '',
        type: scheduleData.type || 'test_suite',
        target: scheduleData.target || { type: 'test_suite', id: '', name: '' },
        schedule: scheduleData.schedule || {
          frequency: 'daily',
          timezone: 'UTC',
        },
        execution: scheduleData.execution || {
          timeout: 30,
          retryPolicy: { maxRetries: 1, retryDelay: 5, backoffMultiplier: 2 },
          parallelExecution: false,
          maxConcurrency: 1,
        },
        notifications: scheduleData.notifications || {
          onSuccess: false,
          onFailure: true,
          onTimeout: false,
          recipients: [],
          channels: ['email'],
        },
        conditions: scheduleData.conditions || {},
        isActive: scheduleData.isActive ?? true,
        priority: scheduleData.priority || 'medium',
        tags: scheduleData.tags || [],
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        createdBy: 'current-user',
        runCount: 0,
        successCount: 0,
        failureCount: 0,
        averageDuration: 0,
      };
      setSchedules(prev => [...prev, newSchedule]);
      onScheduleCreate?.(newSchedule);
    }
    setIsCreateDialogOpen(false);
  }, [editingSchedule, onScheduleCreate, onScheduleUpdate]);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Automated Scheduling</h2>
          <p className="text-gray-600 dark:text-gray-400">Configure and manage automated evaluation schedules</p>
        </div>
        <div className="flex items-center space-x-2">
          <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Schedule
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>{editingSchedule ? 'Edit Schedule' : 'Create Evaluation Schedule'}</DialogTitle>
                <DialogDescription>
                  Configure automated execution of tests, metrics collection, and report generation
                </DialogDescription>
              </DialogHeader>
              <ScheduleForm
                schedule={editingSchedule}
                onSubmit={handleSaveSchedule}
                onCancel={() => {
                  setIsCreateDialogOpen(false);
                  setEditingSchedule(null);
                }}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Activity className="h-5 w-5 text-blue-500" />
              <div>
                <div className="text-2xl font-bold">{schedules.filter(s => s.isActive).length}</div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Active Schedules</div>
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
                  {schedules.reduce((sum, s) => sum + s.successCount, 0)}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Successful Executions</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Clock className="h-5 w-5 text-orange-500" />
              <div>
                <div className="text-2xl font-bold">
                  {upcomingRuns.length > 0 && upcomingRuns[0]?.nextRun ?
                    new Date(upcomingRuns[0].nextRun).toLocaleDateString() : 'N/A'
                  }
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Next Run</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Timer className="h-5 w-5 text-purple-500" />
              <div>
                <div className="text-2xl font-bold">
                  {Math.round(schedules.reduce((sum, s) => sum + s.averageDuration, 0) / schedules.length || 0)}m
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Avg Duration</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center space-x-4">
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="test_suite">Test Suite</SelectItem>
                <SelectItem value="metric_collection">Metric Collection</SelectItem>
                <SelectItem value="report_generation">Report Generation</SelectItem>
                <SelectItem value="health_check">Health Check</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="schedules" className="flex items-center space-x-2">
            <Calendar className="h-4 w-4" />
            <span>Schedules</span>
          </TabsTrigger>
          <TabsTrigger value="executions" className="flex items-center space-x-2">
            <Activity className="h-4 w-4" />
            <span>Executions</span>
          </TabsTrigger>
          <TabsTrigger value="upcoming" className="flex items-center space-x-2">
            <Clock className="h-4 w-4" />
            <span>Upcoming</span>
          </TabsTrigger>
          <TabsTrigger value="templates" className="flex items-center space-x-2">
            <FileText className="h-4 w-4" />
            <span>Templates</span>
          </TabsTrigger>
        </TabsList>

        {/* Schedules Tab */}
        <TabsContent value="schedules" className="space-y-4">
          <div className="space-y-4">
            {filteredSchedules.map(schedule => (
              <Card key={schedule.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      {getTypeIcon(schedule.type)}
                      <div>
                        <CardTitle className="text-lg">{schedule.name}</CardTitle>
                        <CardDescription className="mt-1">{schedule.description}</CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge className={getPriorityColor(schedule.priority)}>
                        {schedule.priority}
                      </Badge>
                      <Badge variant={schedule.isActive ? 'default' : 'secondary'}>
                        {schedule.isActive ? 'Active' : 'Inactive'}
                      </Badge>
                      <Switch
                        checked={schedule.isActive}
                        onCheckedChange={() => toggleScheduleStatus(schedule.id)}
                      />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <div className="text-sm font-medium text-gray-600 dark:text-gray-400">Schedule</div>
                      <div className="text-sm">
                        {schedule.schedule.frequency === 'minutes' ? `Every ${schedule.schedule.interval} minutes` :
                         schedule.schedule.frequency === 'hourly' ? 'Every hour' :
                         schedule.schedule.frequency === 'daily' ? `Daily at ${schedule.schedule.time}` :
                         schedule.schedule.frequency === 'weekly' ? `Weekly on ${schedule.schedule.dayOfWeek !== undefined && schedule.schedule.dayOfWeek >= 0 && schedule.schedule.dayOfWeek <= 6 ? ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][schedule.schedule.dayOfWeek] : 'Invalid'} at ${schedule.schedule.time}` :
                         schedule.schedule.frequency === 'monthly' ? `Monthly on day ${schedule.schedule.dayOfMonth}` :
                         'Custom cron'}
                      </div>
                      <div className="text-xs text-gray-500">{schedule.schedule.timezone}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-600 dark:text-gray-400">Target</div>
                      <div className="text-sm">{schedule.target.name}</div>
                      <div className="text-xs text-gray-500">{schedule.target.type.replace('_', ' ')}</div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-600 dark:text-gray-400">Statistics</div>
                      <div className="text-sm">
                        {schedule.runCount} runs • {schedule.successCount} success • {schedule.failureCount} failures
                      </div>
                      <div className="text-xs text-gray-500">
                        Avg: {schedule.averageDuration.toFixed(1)}m • Success rate: {schedule.runCount > 0 ? ((schedule.successCount / schedule.runCount) * 100).toFixed(1) : 0}%
                      </div>
                    </div>
                  </div>

                  {schedule.nextRun && (
                    <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                      <div className="flex items-center space-x-2">
                        <Clock className="h-4 w-4 text-blue-500" />
                        <span className="text-sm">
                          Next run: {new Date(schedule.nextRun).toLocaleString()}
                        </span>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => triggerExecution(schedule.id)}
                      >
                        <Play className="h-4 w-4 mr-2" />
                        Run Now
                      </Button>
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {schedule.tags.map(tag => (
                        <Badge key={tag} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <div className="flex items-center space-x-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleScheduleExpansion(schedule.id)}
                      >
                        {expandedSchedules.has(schedule.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingSchedule(schedule);
                          setIsCreateDialogOpen(true);
                        }}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteSchedule(schedule.id)}
                        className="text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {expandedSchedules.has(schedule.id) && (
                    <div className="mt-4 p-4 border rounded-lg space-y-4">
                      <div>
                        <h5 className="font-medium mb-2">Execution Settings</h5>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>Timeout: {schedule.execution.timeout} minutes</div>
                          <div>Max retries: {schedule.execution.retryPolicy.maxRetries}</div>
                          <div>Parallel: {schedule.execution.parallelExecution ? 'Yes' : 'No'}</div>
                          <div>Max concurrency: {schedule.execution.maxConcurrency}</div>
                        </div>
                      </div>
                      <div>
                        <h5 className="font-medium mb-2">Notifications</h5>
                        <div className="flex flex-wrap gap-2">
                          {schedule.notifications.onSuccess && <Badge variant="outline" className="text-xs">On Success</Badge>}
                          {schedule.notifications.onFailure && <Badge variant="destructive" className="text-xs">On Failure</Badge>}
                          {schedule.notifications.onTimeout && <Badge variant="secondary" className="text-xs">On Timeout</Badge>}
                          {schedule.notifications.channels.map(channel => (
                            <Badge key={channel} variant="outline" className="text-xs">{channel}</Badge>
                          ))}
                        </div>
                      </div>
                      {schedule.lastRun && (
                        <div>
                          <h5 className="font-medium mb-2">Last Run</h5>
                          <div className="text-sm text-gray-600 dark:text-gray-400">
                            {new Date(schedule.lastRun).toLocaleString()}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Executions Tab */}
        <TabsContent value="executions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Executions</CardTitle>
              <CardDescription>History of automated and manual executions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {recentExecutions.map(execution => (
                  <div key={execution.id} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3">
                        {getStatusIcon(execution.status)}
                        <div>
                          <h5 className="font-medium">{execution.scheduleName}</h5>
                          <div className="text-sm text-gray-600 dark:text-gray-400">
                            Started: {new Date(execution.startTime).toLocaleString()}
                            {execution.endTime && (
                              <>
                                {' • '}Duration: {execution.duration?.toFixed(1)}m
                              </>
                            )}
                            {' • '}Triggered by: {execution.triggeredBy}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge variant={execution.status === 'completed' ? 'default' :
                                       execution.status === 'failed' ? 'destructive' :
                                       execution.status === 'running' ? 'secondary' : 'outline'}>
                          {execution.status}
                        </Badge>
                        {execution.retryCount > 0 && (
                          <Badge variant="outline" className="text-xs">
                            Retry #{execution.retryCount}
                          </Badge>
                        )}
                      </div>
                    </div>

                    {execution.result && (
                      <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-800 rounded">
                        <div className="text-sm">
                          {execution.result.success ? (
                            <span className="text-green-600">✓ Success</span>
                          ) : (
                            <span className="text-red-600">✗ Failed: {execution.result.error}</span>
                          )}
                          {execution.result.metrics && (
                            <div className="mt-2 grid grid-cols-2 gap-4 text-xs">
                              {Object.entries(execution.result.metrics).map(([key, value]) => (
                                <div key={key}>
                                  <span className="text-gray-500">{key.replace(/_/g, ' ')}: </span>
                                  <span className="font-medium">{typeof value === 'number' ? value.toFixed(1) : value}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Upcoming Tab */}
        <TabsContent value="upcoming" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Upcoming Runs</CardTitle>
              <CardDescription>Scheduled executions for the next 24 hours</CardDescription>
            </CardHeader>
            <CardContent>
              {upcomingRuns.length > 0 ? (
                <div className="space-y-3">
                  {upcomingRuns.map(schedule => (
                    <div key={schedule.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center space-x-3">
                        {getTypeIcon(schedule.type)}
                        <div>
                          <h5 className="font-medium">{schedule.name}</h5>
                          <div className="text-sm text-gray-600 dark:text-gray-400">
                            {schedule.nextRun && new Date(schedule.nextRun).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline">{schedule.target.type.replace('_', ' ')}</Badge>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => triggerExecution(schedule.id)}
                        >
                          <Play className="h-4 w-4 mr-2" />
                          Run Now
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No upcoming runs scheduled</p>
                  <p className="text-sm">Activate schedules to see upcoming executions here</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {scheduleTemplates.map(template => (
              <Card key={template.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{template.name}</CardTitle>
                  <CardDescription>{template.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">{template.category}</Badge>
                    <div className="text-sm text-gray-500">{template.type.replace('_', ' ')}</div>
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-medium">Schedule:</div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      {template.schedule.frequency}
                      {template.schedule.time && ` at ${template.schedule.time}`}
                    </div>
                  </div>

                  <div className="flex space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => {
                        const newSchedule: Partial<EvaluationSchedule> = {
                          name: template.name,
                          description: template.description,
                          type: template.type,
                          schedule: template.schedule as any,
                          execution: template.execution as any,
                          notifications: template.notifications as any,
                        };
                        setEditingSchedule(newSchedule as EvaluationSchedule);
                        setIsCreateDialogOpen(true);
                      }}
                    >
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
      </Tabs>
    </div>
  );
};

// Schedule Form Component
const ScheduleForm: React.FC<ScheduleFormProps> = ({ schedule, onSubmit, onCancel }) => {
  const [formData, setFormData] = useState({
    name: schedule?.name || '',
    description: schedule?.description || '',
    type: schedule?.type || 'test_suite',
    targetName: schedule?.target.name || '',
    frequency: schedule?.schedule.frequency || 'daily',
    interval: schedule?.schedule.interval || 15,
    time: schedule?.schedule.time || '09:00',
    dayOfWeek: schedule?.schedule.dayOfWeek || 1,
    dayOfMonth: schedule?.schedule.dayOfMonth || 1,
    timezone: schedule?.schedule.timezone || 'UTC',
    timeout: schedule?.execution.timeout || 30,
    maxRetries: schedule?.execution.retryPolicy.maxRetries || 1,
    retryDelay: schedule?.execution.retryPolicy.retryDelay || 5,
    parallelExecution: schedule?.execution.parallelExecution || false,
    maxConcurrency: schedule?.execution.maxConcurrency || 1,
    notifyOnSuccess: schedule?.notifications.onSuccess || false,
    notifyOnFailure: schedule?.notifications.onFailure ?? true,
    notifyOnTimeout: schedule?.notifications.onTimeout || false,
    recipients: schedule?.notifications.recipients?.join(', ') || '',
    channels: schedule?.notifications.channels?.join(', ') || 'email',
    isActive: schedule?.isActive ?? true,
    priority: schedule?.priority || 'medium',
    tags: schedule?.tags?.join(', ') || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const scheduleData: Partial<EvaluationSchedule> = {
      name: formData.name,
      description: formData.description,
      type: formData.type as any,
      target: {
        type: formData.type as any,
        id: schedule?.target.id || '',
        name: formData.targetName,
      },
      schedule: {
        frequency: formData.frequency as any,
        timezone: formData.timezone,
        ...(formData.frequency === 'minutes' && { interval: formData.interval }),
        ...(formData.frequency === 'daily' && { time: formData.time }),
        ...(formData.frequency === 'weekly' && { dayOfWeek: formData.dayOfWeek, time: formData.time }),
        ...(formData.frequency === 'monthly' && { dayOfMonth: formData.dayOfMonth, time: formData.time }),
      },
      execution: {
        timeout: formData.timeout,
        retryPolicy: {
          maxRetries: formData.maxRetries,
          retryDelay: formData.retryDelay,
          backoffMultiplier: 2,
        },
        parallelExecution: formData.parallelExecution,
        maxConcurrency: formData.maxConcurrency,
      },
      notifications: {
        onSuccess: formData.notifyOnSuccess,
        onFailure: formData.notifyOnFailure,
        onTimeout: formData.notifyOnTimeout,
        recipients: formData.recipients.split(',').map(r => r.trim()).filter(Boolean),
        channels: formData.channels.split(',').map(c => c.trim()).filter(c => ['email', 'slack', 'webhook', 'in_app'].includes(c)) as ('email' | 'slack' | 'webhook' | 'in_app')[],
      },
      isActive: formData.isActive,
      priority: formData.priority as any,
      tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
    };

    onSubmit(scheduleData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="schedule-name">Name *</Label>
          <Input
            id="schedule-name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Enter schedule name"
            required
          />
        </div>
        <div>
          <Label htmlFor="schedule-type">Type *</Label>
          <Select value={formData.type} onValueChange={(value) => setFormData(prev => ({ ...prev, type: value as EvaluationSchedule['type'] }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="test_suite">Test Suite</SelectItem>
              <SelectItem value="metric_collection">Metric Collection</SelectItem>
              <SelectItem value="report_generation">Report Generation</SelectItem>
              <SelectItem value="health_check">Health Check</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="schedule-description">Description</Label>
        <Textarea
          id="schedule-description"
          value={formData.description}
          onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
          placeholder="Describe what this schedule does"
          rows={3}
        />
      </div>

      <div>
        <Label htmlFor="target-name">Target Name *</Label>
        <Input
          id="target-name"
          value={formData.targetName}
          onChange={(e) => setFormData(prev => ({ ...prev, targetName: e.target.value }))}
          placeholder="e.g., Core RAG Functionality, Response Quality Index"
          required
        />
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Schedule Configuration</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="frequency">Frequency *</Label>
            <Select value={formData.frequency} onValueChange={(value) => setFormData(prev => ({ ...prev, frequency: value as EvaluationSchedule['schedule']['frequency'] }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="minutes">Every N minutes</SelectItem>
                <SelectItem value="hourly">Hourly</SelectItem>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="timezone">Timezone</Label>
            <Select value={formData.timezone} onValueChange={(value) => setFormData(prev => ({ ...prev, timezone: value }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {timezones.map(tz => (
                  <SelectItem key={tz.value} value={tz.value}>{tz.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {formData.frequency === 'minutes' && (
          <div className="mt-4">
            <Label htmlFor="interval">Interval (minutes)</Label>
            <Input
              id="interval"
              type="number"
              min="1"
              value={formData.interval}
              onChange={(e) => setFormData(prev => ({ ...prev, interval: parseInt(e.target.value) }))}
            />
          </div>
        )}

        {(formData.frequency === 'daily' || formData.frequency === 'weekly' || formData.frequency === 'monthly') && (
          <div className="mt-4">
            <Label htmlFor="time">Time</Label>
            <Input
              id="time"
              type="time"
              value={formData.time}
              onChange={(e) => setFormData(prev => ({ ...prev, time: e.target.value }))}
            />
          </div>
        )}

        {formData.frequency === 'weekly' && (
          <div className="mt-4">
            <Label htmlFor="dayOfWeek">Day of Week</Label>
            <Select value={formData.dayOfWeek.toString()} onValueChange={(value) => setFormData(prev => ({ ...prev, dayOfWeek: parseInt(value) }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">Sunday</SelectItem>
                <SelectItem value="1">Monday</SelectItem>
                <SelectItem value="2">Tuesday</SelectItem>
                <SelectItem value="3">Wednesday</SelectItem>
                <SelectItem value="4">Thursday</SelectItem>
                <SelectItem value="5">Friday</SelectItem>
                <SelectItem value="6">Saturday</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}

        {formData.frequency === 'monthly' && (
          <div className="mt-4">
            <Label htmlFor="dayOfMonth">Day of Month</Label>
            <Input
              id="dayOfMonth"
              type="number"
              min="1"
              max="31"
              value={formData.dayOfMonth}
              onChange={(e) => setFormData(prev => ({ ...prev, dayOfMonth: parseInt(e.target.value) }))}
            />
          </div>
        )}
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Execution Settings</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="timeout">Timeout (minutes)</Label>
            <Input
              id="timeout"
              type="number"
              min="1"
              value={formData.timeout}
              onChange={(e) => setFormData(prev => ({ ...prev, timeout: parseInt(e.target.value) }))}
            />
          </div>
          <div>
            <Label htmlFor="maxRetries">Max Retries</Label>
            <Input
              id="maxRetries"
              type="number"
              min="0"
              value={formData.maxRetries}
              onChange={(e) => setFormData(prev => ({ ...prev, maxRetries: parseInt(e.target.value) }))}
            />
          </div>
          <div>
            <Label htmlFor="retryDelay">Retry Delay (minutes)</Label>
            <Input
              id="retryDelay"
              type="number"
              min="1"
              value={formData.retryDelay}
              onChange={(e) => setFormData(prev => ({ ...prev, retryDelay: parseInt(e.target.value) }))}
            />
          </div>
          <div>
            <Label htmlFor="maxConcurrency">Max Concurrency</Label>
            <Input
              id="maxConcurrency"
              type="number"
              min="1"
              value={formData.maxConcurrency}
              onChange={(e) => setFormData(prev => ({ ...prev, maxConcurrency: parseInt(e.target.value) }))}
            />
          </div>
        </div>
        <div className="flex items-center space-x-2 mt-4">
          <Switch
            id="parallel-execution"
            checked={formData.parallelExecution}
            onCheckedChange={(checked) => setFormData(prev => ({ ...prev, parallelExecution: checked }))}
          />
          <Label htmlFor="parallel-execution">Enable Parallel Execution</Label>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Notifications</h4>
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <Switch
              id="notify-success"
              checked={formData.notifyOnSuccess}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, notifyOnSuccess: checked }))}
            />
            <Label htmlFor="notify-success">Notify on Success</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="notify-failure"
              checked={formData.notifyOnFailure}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, notifyOnFailure: checked }))}
            />
            <Label htmlFor="notify-failure">Notify on Failure</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="notify-timeout"
              checked={formData.notifyOnTimeout}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, notifyOnTimeout: checked }))}
            />
            <Label htmlFor="notify-timeout">Notify on Timeout</Label>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <Label htmlFor="recipients">Recipients</Label>
            <Input
              id="recipients"
              value={formData.recipients}
              onChange={(e) => setFormData(prev => ({ ...prev, recipients: e.target.value }))}
              placeholder="email1@company.com, email2@company.com"
            />
          </div>
          <div>
            <Label htmlFor="channels">Channels</Label>
            <Input
              id="channels"
              value={formData.channels}
              onChange={(e) => setFormData(prev => ({ ...prev, channels: e.target.value }))}
              placeholder="email, slack, webhook"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="priority">Priority</Label>
          <Select value={formData.priority} onValueChange={(value) => setFormData(prev => ({ ...prev, priority: value as EvaluationSchedule['priority'] }))}>
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
        <div>
          <Label htmlFor="tags">Tags</Label>
          <Input
            id="tags"
            value={formData.tags}
            onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
            placeholder="e.g., daily, quality, important (comma-separated)"
          />
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="is-active"
          checked={formData.isActive}
          onCheckedChange={(checked) => setFormData(prev => ({ ...prev, isActive: checked }))}
        />
        <Label htmlFor="is-active">Activate Schedule</Label>
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Calendar className="h-4 w-4 mr-2" />
          {schedule ? 'Update Schedule' : 'Create Schedule'}
        </Button>
      </div>
    </form>
  );
};

export default AutomatedEvaluationScheduling;

interface AutomatedEvaluationSchedulingProps {
  onScheduleCreate?: (schedule: EvaluationSchedule) => void;
  onScheduleUpdate?: (schedule: EvaluationSchedule) => void;
  onScheduleDelete?: (scheduleId: string) => void;
  onExecutionTrigger?: (scheduleId: string, executionId: string) => void;
  className?: string;
}

interface ScheduleFormProps {
  schedule?: EvaluationSchedule | null;
  onSubmit: (schedule: Partial<EvaluationSchedule>) => void;
  onCancel: () => void;
}