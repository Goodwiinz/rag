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
  Download,
  Upload,
  FileText,
  Database,
  Archive,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Settings,
  Plus,
  Eye,
  Trash2,
  Filter,
  Search,
  BarChart3,
  PieChart as PieChartIcon,
  FileSpreadsheet,
  FileImage,
  FileVideo,
  FileAudio,
  Globe,
  Mail,
  Link,
  Copy,
  Move,
  FolderOpen,
  Save,
  Zap,
  Activity,
  TrendingUp,
  Server,
  Cloud,
  Shield,
} from 'lucide-react';

// Types
interface ExportJob {
  id: string;
  name: string;
  description: string;
  type: 'manual' | 'scheduled' | 'api';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  config: {
    dataType:
      | 'evaluation_results'
      | 'test_suites'
      | 'metrics'
      | 'alerts'
      | 'analytics'
      | 'audit_logs'
      | 'all';
    dateRange: {
      start: string;
      end: string;
    };
    filters: {
      categories?: string[];
      severities?: string[];
      tags?: string[];
      users?: string[];
    };
    format: 'json' | 'csv' | 'excel' | 'pdf' | 'xml' | 'parquet';
    compression: 'none' | 'gzip' | 'zip';
    encryption: {
      enabled: boolean;
      algorithm?: 'AES-256' | 'RSA';
      keyId?: string;
    };
    destination: {
      type: 'download' | 'email' | 's3' | 'gcs' | 'azure_blob' | 'ftp' | 'api';
      config: Record<string, any>;
    };
    retention: {
      enabled: boolean;
      period: number; // days
      autoDelete: boolean;
    };
  };
  progress: {
    percentage: number;
    currentStep: string;
    totalSteps: number;
    recordsProcessed: number;
    totalRecords: number;
    estimatedTimeRemaining?: number; // seconds
  };
  result: {
    fileSize: number; // bytes
    recordCount: number;
    fileCount: number;
    checksum: string;
    downloadUrl?: string;
    destinationPath?: string;
  };
  metadata: {
    created: string;
    updated: string;
    createdBy: string;
    startedAt?: string;
    completedAt?: string;
    duration?: number; // seconds
    error?: string;
  };
}

interface ArchivePolicy {
  id: string;
  name: string;
  description: string;
  isActive: boolean;
  conditions: {
    dataAge: number; // days
    dataTypes: string[];
    categories?: string[];
    minRecords?: number;
  };
  actions: {
    archive: boolean;
    compress: boolean;
    encrypt: boolean;
    moveToColdStorage: boolean;
    deleteOriginal: boolean;
  };
  schedule: {
    enabled: boolean;
    frequency: 'daily' | 'weekly' | 'monthly';
    time: string; // HH:MM
    timezone: string;
  };
  retention: {
    archivedData: number; // days
    coldStorage: number; // days
    permanent: boolean;
  };
  destinations: {
    archive: string; // S3 bucket, GCS bucket, etc.
    coldStorage?: string;
  };
  metadata: {
    created: string;
    updated: string;
    createdBy: string;
    lastRun?: string;
    totalArchived: number;
    totalSpaceSaved: number; // GB
  };
}

interface StorageStats {
  totalData: {
    size: number; // GB
    records: number;
    files: number;
  };
  byType: {
    evaluation_results: { size: number; records: number };
    test_suites: { size: number; records: number };
    metrics: { size: number; records: number };
    alerts: { size: number; records: number };
    analytics: { size: number; records: number };
    audit_logs: { size: number; records: number };
  };
  byAge: {
    last30days: { size: number; records: number };
    last90days: { size: number; records: number };
    lastYear: { size: number; records: number };
    older: { size: number; records: number };
  };
  archived: {
    size: number; // GB
    records: number;
    files: number;
    compressionRatio: number; // percentage
  };
  growth: {
    daily: number; // GB
    weekly: number; // GB
    monthly: number; // GB
  };
}

// Mock data
const mockExportJobs: ExportJob[] = [
  {
    id: 'export-001',
    name: 'Q3 Evaluation Results Export',
    description: 'Comprehensive export of all evaluation results for Q3 2025',
    type: 'scheduled',
    status: 'completed',
    priority: 'high',
    config: {
      dataType: 'evaluation_results',
      dateRange: {
        start: '2025-07-01T00:00:00Z',
        end: '2025-09-30T23:59:59Z',
      },
      filters: {
        categories: ['quality', 'performance'],
      },
      format: 'excel',
      compression: 'zip',
      encryption: {
        enabled: true,
        algorithm: 'AES-256',
        keyId: 'key-001',
      },
      destination: {
        type: 's3',
        config: {
          bucket: 'exports-evaluation-results',
          path: 'q3-2025/',
          region: 'us-west-2',
        },
      },
      retention: {
        enabled: true,
        period: 90,
        autoDelete: false,
      },
    },
    progress: {
      percentage: 100,
      currentStep: 'Completed',
      totalSteps: 5,
      recordsProcessed: 15420,
      totalRecords: 15420,
    },
    result: {
      fileSize: 268435456, // 256 MB
      recordCount: 15420,
      fileCount: 3,
      checksum: 'sha256:a1b2c3d4...',
      destinationPath: 's3://exports-evaluation-results/q3-2025/q3-results.zip',
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-01T01:15:30Z',
      createdBy: 'admin',
      startedAt: '2025-10-01T00:00:00Z',
      completedAt: '2025-10-01T01:15:30Z',
      duration: 4530,
    },
  },
  {
    id: 'export-002',
    name: 'Weekly Metrics Export',
    description: 'Automated weekly export of performance metrics',
    type: 'scheduled',
    status: 'running',
    priority: 'medium',
    config: {
      dataType: 'metrics',
      dateRange: {
        start: '2025-10-10T00:00:00Z',
        end: '2025-10-17T23:59:59Z',
      },
      filters: {},
      format: 'json',
      compression: 'gzip',
      encryption: {
        enabled: false,
      },
      destination: {
        type: 'download',
        config: {},
      },
      retention: {
        enabled: false,
        period: 30,
        autoDelete: false,
      },
    },
    progress: {
      percentage: 65,
      currentStep: 'Processing metrics data',
      totalSteps: 4,
      recordsProcessed: 3200,
      totalRecords: 4920,
      estimatedTimeRemaining: 180,
    },
    result: {
      fileSize: 0,
      recordCount: 0,
      fileCount: 0,
      checksum: '',
    },
    metadata: {
      created: '2025-10-17T12:00:00Z',
      updated: '2025-10-17T12:00:00Z',
      createdBy: 'system',
      startedAt: '2025-10-17T12:00:00Z',
    },
  },
  {
    id: 'export-003',
    name: 'Audit Logs Export for Compliance',
    description: 'Export audit logs for compliance review',
    type: 'manual',
    status: 'failed',
    priority: 'urgent',
    config: {
      dataType: 'audit_logs',
      dateRange: {
        start: '2025-09-01T00:00:00Z',
        end: '2025-09-30T23:59:59Z',
      },
      filters: {},
      format: 'csv',
      compression: 'none',
      encryption: {
        enabled: true,
        algorithm: 'AES-256',
      },
      destination: {
        type: 'email',
        config: {
          recipients: ['compliance@company.com'],
          subject: 'Audit Logs - September 2025',
        },
      },
      retention: {
        enabled: true,
        period: 365,
        autoDelete: false,
      },
    },
    progress: {
      percentage: 25,
      currentStep: 'Querying database',
      totalSteps: 3,
      recordsProcessed: 0,
      totalRecords: 50000,
    },
    result: {
      fileSize: 0,
      recordCount: 0,
      fileCount: 0,
      checksum: '',
    },
    metadata: {
      created: '2025-10-16T14:30:00Z',
      updated: '2025-10-16T15:45:00Z',
      createdBy: 'compliance-officer',
      startedAt: '2025-10-16T14:30:00Z',
      error: 'Database connection timeout after 75 minutes',
    },
  },
];

const mockArchivePolicies: ArchivePolicy[] = [
  {
    id: 'policy-001',
    name: 'Standard 90-Day Archive',
    description: 'Archive evaluation data older than 90 days',
    isActive: true,
    conditions: {
      dataAge: 90,
      dataTypes: ['evaluation_results', 'test_suites'],
      minRecords: 1000,
    },
    actions: {
      archive: true,
      compress: true,
      encrypt: true,
      moveToColdStorage: false,
      deleteOriginal: false,
    },
    schedule: {
      enabled: true,
      frequency: 'weekly',
      time: '02:00',
      timezone: 'UTC',
    },
    retention: {
      archivedData: 365,
      coldStorage: 0,
      permanent: false,
    },
    destinations: {
      archive: 's3://evaluation-archive/standard/',
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-15T14:30:00Z',
      createdBy: 'admin',
      lastRun: '2025-10-15T02:00:00Z',
      totalArchived: 250000,
      totalSpaceSaved: 125, // GB
    },
  },
  {
    id: 'policy-002',
    name: 'Annual Cold Storage Migration',
    description: 'Move archived data to cold storage after 1 year',
    isActive: true,
    conditions: {
      dataAge: 365,
      dataTypes: ['evaluation_results', 'test_suites', 'metrics'],
      minRecords: 100,
    },
    actions: {
      archive: false,
      compress: true,
      encrypt: true,
      moveToColdStorage: true,
      deleteOriginal: false,
    },
    schedule: {
      enabled: true,
      frequency: 'monthly',
      time: '03:00',
      timezone: 'UTC',
    },
    retention: {
      archivedData: 1825, // 5 years
      coldStorage: 365,
      permanent: false,
    },
    destinations: {
      archive: 's3://evaluation-archive/standard/',
      coldStorage: 'glacier://evaluation-cold-storage/',
    },
    metadata: {
      created: '2025-10-01T00:00:00Z',
      updated: '2025-10-10T09:15:00Z',
      createdBy: 'storage-admin',
      lastRun: '2025-10-10T03:00:00Z',
      totalArchived: 45000,
      totalSpaceSaved: 280, // GB
    },
  },
];

const mockStorageStats: StorageStats = {
  totalData: {
    size: 1250, // GB
    records: 2500000,
    files: 15000,
  },
  byType: {
    evaluation_results: { size: 450, records: 850000 },
    test_suites: { size: 280, records: 620000 },
    metrics: { size: 320, records: 580000 },
    alerts: { size: 120, records: 280000 },
    analytics: { size: 60, records: 120000 },
    audit_logs: { size: 20, records: 50000 },
  },
  byAge: {
    last30days: { size: 180, records: 380000 },
    last90days: { size: 420, records: 950000 },
    lastYear: { size: 450, records: 920000 },
    older: { size: 200, records: 250000 },
  },
  archived: {
    size: 850, // GB
    records: 1850000,
    files: 12000,
    compressionRatio: 65, // 65% compression
  },
  growth: {
    daily: 2.5, // GB per day
    weekly: 17.5, // GB per week
    monthly: 75, // GB per month
  },
};

const dataTypes = [
  {
    id: 'evaluation_results',
    name: 'Evaluation Results',
    description: 'Individual evaluation results and metrics',
  },
  {
    id: 'test_suites',
    name: 'Test Suites',
    description: 'Test suite configurations and results',
  },
  {
    id: 'metrics',
    name: 'Metrics',
    description: 'Custom and system metrics data',
  },
  {
    id: 'alerts',
    name: 'Alerts',
    description: 'Alert rules and alert history',
  },
  {
    id: 'analytics',
    name: 'Analytics',
    description: 'Analytics reports and dashboards',
  },
  {
    id: 'audit_logs',
    name: 'Audit Logs',
    description: 'System audit logs and activities',
  },
  { id: 'all', name: 'All Data', description: 'Complete system data export' },
];

const exportFormats = [
  {
    id: 'json',
    name: 'JSON',
    description: 'Structured data format',
    icon: <FileText className="h-4 w-4" />,
  },
  {
    id: 'csv',
    name: 'CSV',
    description: 'Comma-separated values',
    icon: <FileSpreadsheet className="h-4 w-4" />,
  },
  {
    id: 'excel',
    name: 'Excel',
    description: 'Microsoft Excel format',
    icon: <FileSpreadsheet className="h-4 w-4" />,
  },
  {
    id: 'pdf',
    name: 'PDF',
    description: 'Portable Document Format',
    icon: <FileText className="h-4 w-4" />,
  },
  {
    id: 'xml',
    name: 'XML',
    description: 'eXtensible Markup Language',
    icon: <FileText className="h-4 w-4" />,
  },
  {
    id: 'parquet',
    name: 'Parquet',
    description: 'Columnar storage format',
    icon: <Database className="h-4 w-4" />,
  },
];

const EvaluationDataExportArchival: React.FC<
  EvaluationDataExportArchivalProps
> = ({
  onExportJobCreate,
  onExportJobCancel,
  onArchivePolicyCreate,
  onArchivePolicyUpdate,
  className,
}) => {
  const [exportJobs, setExportJobs] = useState<ExportJob[]>(mockExportJobs);
  const [archivePolicies, setArchivePolicies] =
    useState<ArchivePolicy[]>(mockArchivePolicies);
  const [storageStats, setStorageStats] =
    useState<StorageStats>(mockStorageStats);
  const [selectedJob, setSelectedJob] = useState<ExportJob | null>(null);
  const [selectedPolicy, setSelectedPolicy] = useState<ArchivePolicy | null>(
    null
  );
  const [activeTab, setActiveTab] = useState('overview');
  const [isCreateExportDialogOpen, setIsCreateExportDialogOpen] =
    useState(false);
  const [isCreatePolicyDialogOpen, setIsCreatePolicyDialogOpen] =
    useState(false);
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterType, setFilterType] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Filter export jobs
  const filteredJobs = useMemo(() => {
    return exportJobs.filter((job) => {
      const matchesSearch =
        job.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        job.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus =
        filterStatus === 'all' || job.status === filterStatus;
      const matchesType = filterType === 'all' || job.type === filterType;
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [exportJobs, searchTerm, filterStatus, filterType]);

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'cancelled':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'low':
        return 'bg-gray-100 text-foreground border-border';
      default:
        return 'bg-gray-100 text-foreground border-border';
    }
  };

  // Get format icon
  const getFormatIcon = (format: string) => {
    const formatConfig = exportFormats.find((f) => f.id === format);
    return formatConfig?.icon || <FileText className="h-4 w-4" />;
  };

  // Format file size
  const formatFileSize = (bytes: number): string => {
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
  };

  // Cancel export job
  const cancelExportJob = useCallback(
    (jobId: string) => {
      setExportJobs((prev) =>
        prev.map((job) =>
          job.id === jobId
            ? { ...job, status: 'cancelled', updated: new Date().toISOString() }
            : job
        )
      );
      onExportJobCancel?.(jobId);
    },
    [onExportJobCancel]
  );

  // Delete export job
  const deleteExportJob = useCallback((jobId: string) => {
    setExportJobs((prev) => prev.filter((job) => job.id !== jobId));
  }, []);

  // Toggle archive policy status
  const togglePolicyStatus = useCallback((policyId: string) => {
    setArchivePolicies((prev) =>
      prev.map((policy) =>
        policy.id === policyId
          ? {
              ...policy,
              isActive: !policy.isActive,
              updated: new Date().toISOString(),
            }
          : policy
      )
    );
  }, []);

  // Delete archive policy
  const deleteArchivePolicy = useCallback((policyId: string) => {
    setArchivePolicies((prev) =>
      prev.filter((policy) => policy.id !== policyId)
    );
  }, []);

  // Save export job
  const handleSaveExportJob = useCallback(
    (jobData: Partial<ExportJob>) => {
      const newJob: ExportJob = {
        id: `export-${Date.now()}`,
        name: jobData.name || 'New Export Job',
        description: jobData.description || '',
        type: 'manual',
        status: 'pending',
        priority: jobData.priority || 'medium',
        config: jobData.config || {
          dataType: 'evaluation_results',
          dateRange: {
            start: new Date(
              Date.now() - 30 * 24 * 60 * 60 * 1000
            ).toISOString(),
            end: new Date().toISOString(),
          },
          filters: {},
          format: 'json',
          compression: 'none',
          encryption: { enabled: false },
          destination: { type: 'download', config: {} },
          retention: { enabled: false, period: 30, autoDelete: false },
        },
        progress: {
          percentage: 0,
          currentStep: 'Queued',
          totalSteps: 1,
          recordsProcessed: 0,
          totalRecords: 0,
        },
        result: {
          fileSize: 0,
          recordCount: 0,
          fileCount: 0,
          checksum: '',
        },
        metadata: {
          created: new Date().toISOString(),
          updated: new Date().toISOString(),
          createdBy: 'current-user',
        },
      };
      setExportJobs((prev) => [newJob, ...prev]);
      onExportJobCreate?.(newJob);
      setIsCreateExportDialogOpen(false);
    },
    [onExportJobCreate]
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Data Export & Archival
          </h2>
          <p className="text-foreground">
            Export evaluation data and manage archival policies
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Dialog
            open={isCreatePolicyDialogOpen}
            onOpenChange={setIsCreatePolicyDialogOpen}
          >
            <DialogTrigger asChild>
              <Button variant="outline">
                <Archive className="h-4 w-4 mr-2" />
                Archive Policy
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Create Archive Policy</DialogTitle>
                <DialogDescription>
                  Define policies for automatic data archival and retention
                </DialogDescription>
              </DialogHeader>
              <ArchivePolicyForm
                onSubmit={(policyData) => {
                  const newPolicy: ArchivePolicy = {
                    id: `policy-${Date.now()}`,
                    ...policyData,
                    isActive: true,
                    metadata: {
                      created: new Date().toISOString(),
                      updated: new Date().toISOString(),
                      createdBy: 'current-user',
                      totalArchived: 0,
                      totalSpaceSaved: 0,
                    },
                  } as ArchivePolicy;
                  setArchivePolicies((prev) => [...prev, newPolicy]);
                  onArchivePolicyCreate?.(newPolicy);
                  setIsCreatePolicyDialogOpen(false);
                }}
                onCancel={() => setIsCreatePolicyDialogOpen(false)}
              />
            </DialogContent>
          </Dialog>
          <Dialog
            open={isCreateExportDialogOpen}
            onOpenChange={setIsCreateExportDialogOpen}
          >
            <DialogTrigger asChild>
              <Button>
                <Download className="h-4 w-4 mr-2" />
                Export Data
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>Create Export Job</DialogTitle>
                <DialogDescription>
                  Configure and schedule data export jobs
                </DialogDescription>
              </DialogHeader>
              <ExportJobForm
                onSubmit={handleSaveExportJob}
                onCancel={() => setIsCreateExportDialogOpen(false)}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Storage Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Database className="h-5 w-5 text-blue-500" />
              <div>
                <div className="text-2xl font-bold">
                  {storageStats.totalData.size} GB
                </div>
                <div className="text-sm text-foreground">Total Storage</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Archive className="h-5 w-5 text-green-500" />
              <div>
                <div className="text-2xl font-bold">
                  {storageStats.archived.size} GB
                </div>
                <div className="text-sm text-foreground">Archived</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Activity className="h-5 w-5 text-purple-500" />
              <div>
                <div className="text-2xl font-bold">
                  {storageStats.growth.daily} GB
                </div>
                <div className="text-sm text-foreground">Daily Growth</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5 text-orange-500" />
              <div>
                <div className="text-2xl font-bold">
                  {storageStats.archived.compressionRatio}%
                </div>
                <div className="text-sm text-foreground">Compression</div>
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
          <TabsTrigger value="exports" className="flex items-center space-x-2">
            <Download className="h-4 w-4" />
            <span>Export Jobs</span>
          </TabsTrigger>
          <TabsTrigger value="policies" className="flex items-center space-x-2">
            <Archive className="h-4 w-4" />
            <span>Archive Policies</span>
          </TabsTrigger>
          <TabsTrigger value="storage" className="flex items-center space-x-2">
            <Server className="h-4 w-4" />
            <span>Storage Analytics</span>
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Data Distribution by Type</CardTitle>
                <CardDescription>
                  Storage usage across different data types
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(storageStats.byType).map(([type, stats]) => (
                    <div
                      key={type}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-2">
                        <div className="w-4 h-4 bg-blue-500 rounded" />
                        <span className="text-sm font-medium capitalize">
                          {type.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="text-sm">
                        {stats.size} GB • {stats.records.toLocaleString()}{' '}
                        records
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Data Distribution by Age</CardTitle>
                <CardDescription>Storage usage by data age</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(storageStats.byAge).map(([age, stats]) => (
                    <div key={age} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium capitalize">
                          {age
                            .replace(/(\d+)/, ' $1')
                            .replace('last ', 'Last ')}
                        </span>
                        <span>{stats.size} GB</span>
                      </div>
                      <Progress
                        value={(stats.size / storageStats.totalData.size) * 100}
                        className="h-2"
                      />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Recent Export Activity</CardTitle>
              <CardDescription>
                Latest export jobs and their status
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {exportJobs.slice(0, 5).map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div className="flex items-center space-x-3">
                      {getStatusIcon(job.status)}
                      <div>
                        <div className="font-medium">{job.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {job.config.dataType.replace('_', ' ')} •{' '}
                          {job.config.format.toUpperCase()}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium">
                        {formatFileSize(job.result.fileSize)}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {job.metadata.completedAt
                          ? new Date(
                              job.metadata.completedAt
                            ).toLocaleDateString()
                          : new Date(job.metadata.created).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Export Jobs Tab */}
        <TabsContent value="exports" className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center space-x-4 mb-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search export jobs..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="manual">Manual</SelectItem>
                    <SelectItem value="scheduled">Scheduled</SelectItem>
                    <SelectItem value="api">API</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3">
                {filteredJobs.map((job) => (
                  <div key={job.id} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        {getStatusIcon(job.status)}
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <h4 className="font-medium">{job.name}</h4>
                            <Badge className={getPriorityColor(job.priority)}>
                              {job.priority}
                            </Badge>
                            <Badge variant="outline">{job.type}</Badge>
                          </div>
                          <p className="text-sm text-foreground mb-2">
                            {job.description}
                          </p>
                          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                            <span>{job.config.dataType.replace('_', ' ')}</span>
                            <span>•</span>
                            <span>
                              {getFormatIcon(job.config.format)}{' '}
                              {job.config.format.toUpperCase()}
                            </span>
                            <span>•</span>
                            <span>
                              Created:{' '}
                              {new Date(
                                job.metadata.created
                              ).toLocaleDateString()}
                            </span>
                            {job.metadata.completedAt && (
                              <>
                                <span>•</span>
                                <span>
                                  Completed:{' '}
                                  {new Date(
                                    job.metadata.completedAt
                                  ).toLocaleDateString()}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedJob(job)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {job.status === 'running' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => cancelExportJob(job.id)}
                            className="text-orange-600"
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteExportJob(job.id)}
                          className="text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {job.status === 'running' && (
                      <div className="mt-4 space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span>{job.progress.currentStep}</span>
                          <span>{job.progress.percentage}%</span>
                        </div>
                        <Progress
                          value={job.progress.percentage}
                          className="h-2"
                        />
                        <div className="text-xs text-muted-foreground">
                          {job.progress.recordsProcessed.toLocaleString()} /{' '}
                          {job.progress.totalRecords.toLocaleString()} records
                          {job.progress.estimatedTimeRemaining && (
                            <>
                              {' • '}~
                              {Math.ceil(
                                job.progress.estimatedTimeRemaining / 60
                              )}{' '}
                              min remaining
                            </>
                          )}
                        </div>
                      </div>
                    )}

                    {job.status === 'completed' && job.result.downloadUrl && (
                      <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded">
                        <div className="flex items-center justify-between">
                          <div className="text-sm">
                            <span className="font-medium">
                              Export completed successfully
                            </span>
                            <span className="text-foreground ml-2">
                              {formatFileSize(job.result.fileSize)} •{' '}
                              {job.result.recordCount.toLocaleString()} records
                            </span>
                          </div>
                          <Button size="sm" variant="outline">
                            <Download className="h-4 w-4 mr-2" />
                            Download
                          </Button>
                        </div>
                      </div>
                    )}

                    {job.status === 'failed' && job.metadata.error && (
                      <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 rounded">
                        <div className="text-sm text-red-600 dark:text-red-400">
                          <strong>Error:</strong> {job.metadata.error}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Archive Policies Tab */}
        <TabsContent value="policies" className="space-y-4">
          <div className="space-y-4">
            {archivePolicies.map((policy) => (
              <Card
                key={policy.id}
                className="hover:shadow-md transition-shadow"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">{policy.name}</CardTitle>
                      <CardDescription className="mt-1">
                        {policy.description}
                      </CardDescription>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Badge
                        variant={policy.isActive ? 'default' : 'secondary'}
                      >
                        {policy.isActive ? 'Active' : 'Inactive'}
                      </Badge>
                      <Switch
                        checked={policy.isActive}
                        onCheckedChange={() => togglePolicyStatus(policy.id)}
                      />
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        Conditions
                      </div>
                      <div className="text-sm">
                        Archive data older than {policy.conditions.dataAge} days
                        {policy.conditions.categories && (
                          <div>
                            Categories:{' '}
                            {policy.conditions.categories.join(', ')}
                          </div>
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        Schedule
                      </div>
                      <div className="text-sm">
                        {policy.schedule.enabled
                          ? `${policy.schedule.frequency} at ${policy.schedule.time} (${policy.schedule.timezone})`
                          : 'Disabled'}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        Results
                      </div>
                      <div className="text-sm">
                        {policy.metadata.totalArchived.toLocaleString()} records
                        archived
                        {policy.metadata.totalSpaceSaved > 0 && (
                          <div>
                            • {policy.metadata.totalSpaceSaved} GB saved
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="text-xs text-muted-foreground">
                      Last run:{' '}
                      {policy.metadata.lastRun
                        ? new Date(policy.metadata.lastRun).toLocaleString()
                        : 'Never'}
                    </div>
                    <div className="flex items-center space-x-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedPolicy(policy)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteArchivePolicy(policy.id)}
                        className="text-red-600"
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

        {/* Storage Analytics Tab */}
        <TabsContent value="storage" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Storage Growth Trends</CardTitle>
                <CardDescription>Data growth over time periods</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Daily Growth</span>
                    <span className="text-sm font-bold">
                      {storageStats.growth.daily} GB/day
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Weekly Growth</span>
                    <span className="text-sm font-bold">
                      {storageStats.growth.weekly} GB/week
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Monthly Growth</span>
                    <span className="text-sm font-bold">
                      {storageStats.growth.monthly} GB/month
                    </span>
                  </div>
                  <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded">
                    <div className="text-sm text-blue-600 dark:text-blue-400">
                      <strong>Projected Annual Growth:</strong> ~
                      {(storageStats.growth.monthly * 12).toFixed(0)} GB
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Archive Performance</CardTitle>
                <CardDescription>
                  Archival system performance metrics
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        Compression Ratio
                      </span>
                      <span className="text-sm font-bold">
                        {storageStats.archived.compressionRatio}%
                      </span>
                    </div>
                    <Progress
                      value={storageStats.archived.compressionRatio}
                      className="h-2"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                      Total Space Saved
                    </span>
                    <span className="text-sm font-bold">
                      {storageStats.archived.size} GB
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                      Archived Records
                    </span>
                    <span className="text-sm font-bold">
                      {storageStats.archived.records.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Archive Files</span>
                    <span className="text-sm font-bold">
                      {storageStats.archived.files.toLocaleString()}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Export Job Form Component
const ExportJobForm: React.FC<ExportJobFormProps> = ({
  onSubmit,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    dataType: 'evaluation_results',
    startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0],
    endDate: new Date().toISOString().split('T')[0],
    format: 'json',
    compression: 'none',
    encryptEnabled: false,
    destinationType: 'download',
    recipients: '',
    retentionEnabled: false,
    retentionPeriod: 30,
    autoDelete: false,
    priority: 'medium',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const jobData: Partial<ExportJob> = {
      name: formData.name,
      description: formData.description,
      priority: formData.priority as any,
      config: {
        dataType: formData.dataType as any,
        dateRange: {
          start: new Date(formData.startDate || '').toISOString(),
          end: new Date(formData.endDate || '').toISOString(),
        },
        filters: {},
        format: formData.format as any,
        compression: formData.compression as any,
        encryption: {
          enabled: formData.encryptEnabled,
          algorithm: formData.encryptEnabled ? 'AES-256' : undefined,
        },
        destination: {
          type: formData.destinationType as any,
          config:
            formData.destinationType === 'email'
              ? {
                  recipients: formData.recipients
                    .split(',')
                    .map((r) => r.trim())
                    .filter(Boolean),
                }
              : {},
        },
        retention: {
          enabled: formData.retentionEnabled,
          period: formData.retentionPeriod,
          autoDelete: formData.autoDelete,
        },
      },
    };

    onSubmit(jobData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="job-name">Job Name *</Label>
          <Input
            id="job-name"
            value={formData.name}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, name: e.target.value }))
            }
            placeholder="Enter export job name"
            required
          />
        </div>
        <div>
          <Label htmlFor="job-priority">Priority</Label>
          <Select
            value={formData.priority}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, priority: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="job-description">Description</Label>
        <Textarea
          id="job-description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Describe what this export job does"
          rows={3}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="data-type">Data Type *</Label>
          <Select
            value={formData.dataType}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, dataType: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {dataTypes.map((type) => (
                <SelectItem key={type.id} value={type.id}>
                  {type.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="format">Export Format *</Label>
          <Select
            value={formData.format}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, format: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {exportFormats.map((format) => (
                <SelectItem key={format.id} value={format.id}>
                  <div className="flex items-center space-x-2">
                    {format.icon}
                    <span>{format.name}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="start-date">Start Date *</Label>
          <Input
            id="start-date"
            type="date"
            value={formData.startDate}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, startDate: e.target.value }))
            }
            required
          />
        </div>
        <div>
          <Label htmlFor="end-date">End Date *</Label>
          <Input
            id="end-date"
            type="date"
            value={formData.endDate}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, endDate: e.target.value }))
            }
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="compression">Compression</Label>
          <Select
            value={formData.compression}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, compression: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="gzip">GZIP</SelectItem>
              <SelectItem value="zip">ZIP</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="destination-type">Destination</Label>
          <Select
            value={formData.destinationType}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, destinationType: value }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="download">Download</SelectItem>
              <SelectItem value="email">Email</SelectItem>
              <SelectItem value="s3">Amazon S3</SelectItem>
              <SelectItem value="gcs">Google Cloud Storage</SelectItem>
              <SelectItem value="api">API Endpoint</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {formData.destinationType === 'email' && (
        <div>
          <Label htmlFor="recipients">Recipients</Label>
          <Input
            id="recipients"
            value={formData.recipients}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, recipients: e.target.value }))
            }
            placeholder="email1@company.com, email2@company.com"
          />
        </div>
      )}

      <div className="space-y-3">
        <div className="flex items-center space-x-2">
          <Switch
            id="encrypt-enabled"
            checked={formData.encryptEnabled}
            onCheckedChange={(checked) =>
              setFormData((prev) => ({ ...prev, encryptEnabled: checked }))
            }
          />
          <Label htmlFor="encrypt-enabled">Enable Encryption</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Switch
            id="retention-enabled"
            checked={formData.retentionEnabled}
            onCheckedChange={(checked) =>
              setFormData((prev) => ({ ...prev, retentionEnabled: checked }))
            }
          />
          <Label htmlFor="retention-enabled">Enable Retention Policy</Label>
        </div>
      </div>

      {formData.retentionEnabled && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border rounded-lg p-4">
          <div>
            <Label htmlFor="retention-period">Retention Period (days)</Label>
            <Input
              id="retention-period"
              type="number"
              min="1"
              value={formData.retentionPeriod}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  retentionPeriod: parseInt(e.target.value),
                }))
              }
            />
          </div>
          <div className="flex items-center space-x-2 pt-6">
            <Switch
              id="auto-delete"
              checked={formData.autoDelete}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, autoDelete: checked }))
              }
            />
            <Label htmlFor="auto-delete">
              Auto-delete after retention period
            </Label>
          </div>
        </div>
      )}

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Download className="h-4 w-4 mr-2" />
          Create Export Job
        </Button>
      </div>
    </form>
  );
};

// Archive Policy Form Component
const ArchivePolicyForm: React.FC<ArchivePolicyFormProps> = ({
  onSubmit,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    dataAge: 90,
    dataTypes: ['evaluation_results'],
    archive: true,
    compress: true,
    encrypt: true,
    moveToColdStorage: false,
    scheduleEnabled: true,
    frequency: 'weekly',
    scheduleTime: '02:00',
    timezone: 'UTC',
    retentionDays: 365,
    coldStorageDays: 0,
    permanent: false,
    archiveDestination: 's3://evaluation-archive/standard/',
    coldStorageDestination: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const policyData: Partial<ArchivePolicy> = {
      name: formData.name,
      description: formData.description,
      conditions: {
        dataAge: formData.dataAge,
        dataTypes: formData.dataTypes,
      },
      actions: {
        archive: formData.archive,
        compress: formData.compress,
        encrypt: formData.encrypt,
        moveToColdStorage: formData.moveToColdStorage,
        deleteOriginal: false,
      },
      schedule: {
        enabled: formData.scheduleEnabled,
        frequency: formData.frequency as any,
        time: formData.scheduleTime,
        timezone: formData.timezone,
      },
      retention: {
        archivedData: formData.retentionDays,
        coldStorage: formData.coldStorageDays,
        permanent: formData.permanent,
      },
      destinations: {
        archive: formData.archiveDestination,
        coldStorage: formData.coldStorageDestination || undefined,
      },
    };

    onSubmit(policyData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <Label htmlFor="policy-name">Policy Name *</Label>
        <Input
          id="policy-name"
          value={formData.name}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, name: e.target.value }))
          }
          placeholder="Enter archive policy name"
          required
        />
      </div>

      <div>
        <Label htmlFor="policy-description">Description</Label>
        <Textarea
          id="policy-description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="Describe when this archive policy should run"
          rows={3}
        />
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Archive Conditions</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="data-age">Data Age (days) *</Label>
            <Input
              id="data-age"
              type="number"
              min="1"
              value={formData.dataAge}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  dataAge: parseInt(e.target.value),
                }))
              }
              required
            />
          </div>
          <div>
            <Label>Data Types to Archive</Label>
            <div className="space-y-2 mt-2">
              {[
                'evaluation_results',
                'test_suites',
                'metrics',
                'alerts',
                'analytics',
                'audit_logs',
              ].map((type) => (
                <div key={type} className="flex items-center space-x-2">
                  <Switch
                    id={`data-type-${type}`}
                    checked={formData.dataTypes.includes(type)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        setFormData((prev) => ({
                          ...prev,
                          dataTypes: [...prev.dataTypes, type],
                        }));
                      } else {
                        setFormData((prev) => ({
                          ...prev,
                          dataTypes: prev.dataTypes.filter((t) => t !== type),
                        }));
                      }
                    }}
                  />
                  <Label htmlFor={`data-type-${type}`} className="capitalize">
                    {type.replace('_', ' ')}
                  </Label>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Archive Actions</h4>
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <Switch
              id="archive-action"
              checked={formData.archive}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, archive: checked }))
              }
            />
            <Label htmlFor="archive-action">Archive data</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="compress-action"
              checked={formData.compress}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, compress: checked }))
              }
            />
            <Label htmlFor="compress-action">Compress archived data</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="encrypt-action"
              checked={formData.encrypt}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, encrypt: checked }))
              }
            />
            <Label htmlFor="encrypt-action">Encrypt archived data</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="cold-storage-action"
              checked={formData.moveToColdStorage}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, moveToColdStorage: checked }))
              }
            />
            <Label htmlFor="cold-storage-action">Move to cold storage</Label>
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
          <Label htmlFor="schedule-enabled">Enable scheduled archiving</Label>
        </div>
        {formData.scheduleEnabled && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="frequency">Frequency</Label>
              <Select
                value={formData.frequency}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, frequency: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="monthly">Monthly</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="schedule-time">Time</Label>
              <Input
                id="schedule-time"
                type="time"
                value={formData.scheduleTime}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    scheduleTime: e.target.value,
                  }))
                }
              />
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
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Retention & Destinations</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="retention-days">Archive Retention (days)</Label>
            <Input
              id="retention-days"
              type="number"
              min="1"
              value={formData.retentionDays}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  retentionDays: parseInt(e.target.value),
                }))
              }
            />
          </div>
          <div>
            <Label htmlFor="archive-destination">Archive Destination</Label>
            <Input
              id="archive-destination"
              value={formData.archiveDestination}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  archiveDestination: e.target.value,
                }))
              }
              placeholder="s3://bucket/path/"
            />
          </div>
        </div>
        {formData.moveToColdStorage && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <Label htmlFor="cold-storage-days">
                Cold Storage Retention (days)
              </Label>
              <Input
                id="cold-storage-days"
                type="number"
                min="0"
                value={formData.coldStorageDays}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    coldStorageDays: parseInt(e.target.value),
                  }))
                }
              />
            </div>
            <div>
              <Label htmlFor="cold-storage-destination">
                Cold Storage Destination
              </Label>
              <Input
                id="cold-storage-destination"
                value={formData.coldStorageDestination}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    coldStorageDestination: e.target.value,
                  }))
                }
                placeholder="glacier://bucket/path/"
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Archive className="h-4 w-4 mr-2" />
          Create Archive Policy
        </Button>
      </div>
    </form>
  );
};

export default EvaluationDataExportArchival;

interface EvaluationDataExportArchivalProps {
  onExportJobCreate?: (job: ExportJob) => void;
  onExportJobCancel?: (jobId: string) => void;
  onArchivePolicyCreate?: (policy: ArchivePolicy) => void;
  onArchivePolicyUpdate?: (policy: ArchivePolicy) => void;
  className?: string;
}

interface ExportJobFormProps {
  onSubmit: (job: Partial<ExportJob>) => void;
  onCancel: () => void;
}

interface ArchivePolicyFormProps {
  onSubmit: (policy: Partial<ArchivePolicy>) => void;
  onCancel: () => void;
}
