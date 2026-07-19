/**
 * Real-time Document Processing Status Dashboard
 * Main dashboard component that displays document processing status, queue information,
 * and system metrics with real-time WebSocket updates
 */

'use client';

import React, {
  useEffect,
  useState,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Wifi,
  WifiOff,
  AlertTriangle,
  FileText,
  Users,
  TrendingUp,
  Settings,
} from 'lucide-react';

import {
  useRealtimeStore,
  useConnectionStatus,
  useDocuments,
  useSystemMetrics,
  useRealtimeActions,
} from '@/store/realtime-store';
import {
  DocumentProcessingState,
  ProcessingStatus,
  WebSocketConnectionState,
  Channel,
  UpdateFrequency,
} from '@/types/realtime-processing';
import {
  formatFileSize,
  formatDuration,
  formatRelativeTime,
} from '@/lib/format-utils';

interface RealtimeStatusDashboardProps {
  className?: string;
  autoConnect?: boolean;
  showSystemMetrics?: boolean;
  maxDocuments?: number;
  refreshInterval?: number;
}

export const RealtimeStatusDashboard: React.FC<
  RealtimeStatusDashboardProps
> = ({
  className = '',
  autoConnect = true,
  showSystemMetrics = true,
  maxDocuments = 50,
  refreshInterval = 30000,
}) => {
  const connectionStatus = useConnectionStatus();
  const documents = useDocuments();
  const systemMetrics = useSystemMetrics();
  const {
    connect,
    disconnect,
    reconnect,
    subscribeToDocument,
    unsubscribeFromDocument,
  } = useRealtimeActions();

  const [activeTab, setActiveTab] = useState('queue');
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
  const [filter, setFilter] = useState({
    status: 'all' as ProcessingStatus | 'all',
    fileType: 'all' as string,
  });

  const refreshIntervalRef = useRef<NodeJS.Timeout>();

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect && connectionStatus.status === 'disconnected') {
      const token = localStorage.getItem('auth_token');
      if (token) {
        connect(token, {
          channels: [
            Channel.DOCUMENT_PROCESSING,
            Channel.SYSTEM_STATUS,
            Channel.USER_NOTIFICATIONS,
          ],
          frequency: UpdateFrequency.REALTIME,
        }).catch(console.error);
      }
    }
  }, [autoConnect, connectionStatus.status, connect]);

  // Refresh system metrics periodically
  useEffect(() => {
    if (refreshInterval > 0) {
      refreshIntervalRef.current = setInterval(() => {
        // Trigger system metrics refresh
      }, refreshInterval);
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [refreshInterval]);

  // Filter documents
  const filteredDocuments = useMemo(() => {
    let filtered = documents.slice(0, maxDocuments);

    if (filter.status !== 'all') {
      filtered = filtered.filter((doc) => doc.status === filter.status);
    }

    if (filter.fileType !== 'all') {
      filtered = filtered.filter((doc) => doc.fileType === filter.fileType);
    }

    return filtered.sort((a, b) => {
      // Sort by status priority and creation time
      const statusOrder: Record<ProcessingStatus, number> = {
        processing: 0,
        uploading: 1,
        queued: 2,
        paused: 3,
        failed: 4,
        cancelled: 5,
        completed: 6,
      };

      const aPriority = statusOrder[a.status] ?? 999;
      const bPriority = statusOrder[b.status] ?? 999;

      if (aPriority !== bPriority) {
        return aPriority - bPriority;
      }

      return (
        new Date(b.metadata.uploadStartedAt).getTime() -
        new Date(a.metadata.uploadStartedAt).getTime()
      );
    });
  }, [documents, filter, maxDocuments]);

  // Calculate statistics
  const statistics = useMemo(() => {
    const total = filteredDocuments.length;
    const queued = filteredDocuments.filter(
      (doc) => doc.status === 'queued'
    ).length;
    const processing = filteredDocuments.filter(
      (doc) => doc.status === 'processing'
    ).length;
    const completed = filteredDocuments.filter(
      (doc) => doc.status === 'completed'
    ).length;
    const failed = filteredDocuments.filter(
      (doc) => doc.status === 'failed'
    ).length;

    const averageProgress =
      filteredDocuments.length > 0
        ? Math.round(
            filteredDocuments.reduce(
              (sum, doc) => sum + doc.overallProgress,
              0
            ) / filteredDocuments.length
          )
        : 0;

    return { total, queued, processing, completed, failed, averageProgress };
  }, [filteredDocuments]);

  const handleDocumentClick = useCallback(
    (documentId: string) => {
      setSelectedDocument(selectedDocument === documentId ? null : documentId);
    },
    [selectedDocument]
  );

  const handleSubscribeToDocument = useCallback(
    (documentId: string) => {
      if (selectedDocument === documentId) {
        unsubscribeFromDocument(documentId);
      } else {
        subscribeToDocument(documentId);
      }
    },
    [selectedDocument, subscribeToDocument, unsubscribeFromDocument]
  );

  const getStatusBadgeVariant = (status: ProcessingStatus) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'processing':
        return 'secondary';
      case 'failed':
        return 'destructive';
      case 'queued':
        return 'outline';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: ProcessingStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'processing':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'queued':
        return <Clock className="h-4 w-4 text-muted-foreground" />;
      default:
        return <FileText className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const renderConnectionStatus = () => (
    <div className="flex items-center gap-2 mb-4">
      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-md border ${
          connectionStatus.status === 'connected'
            ? 'bg-green-50 border-green-200 text-green-800'
            : connectionStatus.status === 'connecting'
              ? 'bg-blue-50 border-blue-200 text-blue-800'
              : connectionStatus.status === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : 'bg-gray-50 border-border text-foreground'
        }`}
      >
        {connectionStatus.status === 'connected' ? (
          <Wifi className="h-4 w-4" />
        ) : (
          <WifiOff className="h-4 w-4" />
        )}
        <span className="font-medium capitalize">
          {connectionStatus.status}
        </span>
        {connectionStatus.latency > 0 && (
          <span className="text-xs opacity-75">
            ({connectionStatus.latency}ms)
          </span>
        )}
      </div>

      <Button
        variant="outline"
        size="sm"
        onClick={() =>
          connectionStatus.status === 'connected' ? disconnect() : reconnect()
        }
        disabled={connectionStatus.status === 'connecting'}
      >
        {connectionStatus.status === 'connected' ? 'Disconnect' : 'Connect'}
      </Button>
    </div>
  );

  const renderSystemMetrics = () => (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Documents</p>
              <p className="text-2xl font-bold">{statistics.total}</p>
            </div>
            <FileText className="h-8 w-8 text-muted-foreground" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Processing</p>
              <p className="text-2xl font-bold text-blue-600">
                {statistics.processing}
              </p>
            </div>
            <Loader2 className="h-8 w-8 text-blue-500" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Completed</p>
              <p className="text-2xl font-bold text-green-600">
                {statistics.completed}
              </p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-500" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Average Progress</p>
              <p className="text-2xl font-bold">
                {statistics.averageProgress}%
              </p>
            </div>
            <TrendingUp className="h-8 w-8 text-muted-foreground" />
          </div>
        </CardContent>
      </Card>

      {showSystemMetrics && (
        <>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">
                    Active Connections
                  </p>
                  <p className="text-2xl font-bold">
                    {systemMetrics.concurrentConnections}
                  </p>
                </div>
                <Users className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Active Jobs</p>
                  <p className="text-2xl font-bold">
                    {systemMetrics.activeJobs}
                  </p>
                </div>
                <Activity className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">CPU Usage</p>
                  <p className="text-2xl font-bold">
                    {systemMetrics.cpuUsage}%
                  </p>
                </div>
                <Settings className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Memory Usage</p>
                  <p className="text-2xl font-bold">
                    {systemMetrics.memoryUsage}%
                  </p>
                </div>
                <AlertTriangle className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );

  const renderDocumentsList = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">
          Documents ({filteredDocuments.length})
        </h3>

        <div className="flex items-center gap-2">
          <select
            value={filter.status}
            onChange={(e) =>
              setFilter((prev) => ({
                ...prev,
                status: e.target.value as ProcessingStatus | 'all',
              }))
            }
            className="px-3 py-2 border rounded-md"
          >
            <option value="all">All Status</option>
            <option value="queued">Queued</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>

          <select
            value={filter.fileType}
            onChange={(e) =>
              setFilter((prev) => ({ ...prev, fileType: e.target.value }))
            }
            className="px-3 py-2 border rounded-md"
          >
            <option value="all">All Types</option>
            <option value="pdf">PDF</option>
            <option value="txt">Text</option>
            <option value="jpg">Image</option>
            <option value="png">Image</option>
            <option value="mp3">Audio</option>
            <option value="mp4">Video</option>
          </select>
        </div>
      </div>

      <ScrollArea className="h-96">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Progress</TableHead>
              <TableHead>Stage</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredDocuments.map((document) => (
              <TableRow
                key={document.id}
                className={`cursor-pointer hover:bg-muted/50 ${selectedDocument === document.id ? 'bg-muted' : ''}`}
                onClick={() => handleDocumentClick(document.id)}
              >
                <TableCell>
                  <div className="space-y-1">
                    <p className="font-medium truncate max-w-[200px]">
                      {document.filename}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {formatFileSize(document.metadata.fileSize)} •{' '}
                      {document.fileType.toUpperCase()}
                    </p>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(document.status)}
                    <Badge variant={getStatusBadgeVariant(document.status)}>
                      {document.status.toUpperCase()}
                    </Badge>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="w-32">
                    <Progress
                      value={document.overallProgress}
                      className="h-2"
                    />
                    <span className="text-xs text-muted-foreground">
                      {document.overallProgress}%
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="space-y-1">
                    <p className="text-sm font-medium">
                      {document.currentStage.name}
                    </p>
                    {document.currentStage.status === 'in_progress' && (
                      <p className="text-xs text-muted-foreground">
                        {document.currentStage.progress}%
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <p className="text-sm text-muted-foreground">
                    {document.metadata.processingStartedAt
                      ? formatRelativeTime(
                          document.metadata.processingStartedAt
                        )
                      : '-'}
                  </p>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSubscribeToDocument(document.id);
                      }}
                      disabled={connectionStatus.status !== 'connected'}
                    >
                      {selectedDocument === document.id
                        ? 'Unsubscribe'
                        : 'Subscribe'}
                    </Button>

                    {document.actions.retry && document.status === 'failed' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          // Handle retry logic
                        }}
                        disabled={connectionStatus.status !== 'connected'}
                      >
                        Retry
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  );

  return (
    <div className={`space-y-6 ${className}`}>
      {renderConnectionStatus()}

      {connectionStatus.status === 'error' && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Connection error: {connectionStatus.lastError || 'Unknown error'}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="queue">Queue</TabsTrigger>
          {showSystemMetrics && (
            <TabsTrigger value="metrics">System Metrics</TabsTrigger>
          )}
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="queue" className="space-y-4">
          {renderSystemMetrics()}
          {renderDocumentsList()}
        </TabsContent>

        {showSystemMetrics && (
          <TabsContent value="metrics" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>System Metrics</CardTitle>
                <CardDescription>
                  Real-time system performance indicators
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Connections</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span>Active Connections:</span>
                          <span className="font-mono">
                            {systemMetrics.concurrentConnections}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Uptime:</span>
                          <span className="font-mono">
                            {formatDuration(Date.now())}
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pads-2">
                      <CardTitle className="text-sm">Performance</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span>Active Jobs:</span>
                          <span className="font-mono">
                            {systemMetrics.activeJobs}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Queued Jobs:</span>
                          <span className="font-mono">
                            {systemMetrics.queuedJobs}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Avg Duration:</span>
                          <span className="font-mono">
                            {systemMetrics.averageJobDuration}s
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Resources</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span>CPU Usage:</span>
                          <span className="font-mono">
                            {systemMetrics.cpuUsage}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Memory Usage:</span>
                          <span className="font-mono">
                            {systemMetrics.memoryUsage}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Disk Space:</span>
                          <span className="font-mono">
                            {systemMetrics.diskSpace}%
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="analytics" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Processing Analytics</CardTitle>
              <CardDescription>
                Detailed analytics for document processing performance
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <p className="text-muted-foreground">
                  Analytics coming soon...
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default RealtimeStatusDashboard;
