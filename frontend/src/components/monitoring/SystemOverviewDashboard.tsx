/**
 * SystemOverviewDashboard - Main system health and status dashboard
 * Provides a comprehensive overview of system health, SLI/SLO status, active users, and critical alerts
 */

import React, { useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { useMonitoringStore } from '@/stores/monitoringStore';
import { useMonitoringWebSocket } from '@/services/monitoringWebsocketService';
import MetricCard from './MetricCard';
import StatusGrid from './StatusGrid';
import AlertList from './AlertList';
import {
  SystemHealthScore,
  SLIMetrics,
  ComponentHealth,
  Alert,
  TrendData,
} from '@/types/monitoring';
import {
  ServerIcon,
  UsersIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  ChartBarIcon,
  ArrowPathIcon,
  BellIcon,
  CogIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';

interface SystemOverviewDashboardProps {
  className?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
  showDetails?: boolean;
  compact?: boolean;
  onSystemHealthClick?: (health: SystemHealthScore) => void;
  onAlertClick?: (alert: Alert) => void;
  onComponentClick?: (component: ComponentHealth) => void;
}

const SystemOverviewDashboard: React.FC<SystemOverviewDashboardProps> = ({
  className,
  autoRefresh = true,
  refreshInterval = 30000,
  showDetails = true,
  compact = false,
  onSystemHealthClick,
  onAlertClick,
  onComponentClick,
}) => {
  // Store hooks
  const systemHealth = useMonitoringStore((state) => state.systemHealth);
  const systemHealthLoading = useMonitoringStore(
    (state) => state.systemHealthLoading
  );
  const activeAlerts = useMonitoringStore((state) => state.activeAlerts);
  const criticalAlerts = useMonitoringStore((state) => state.criticalAlerts);
  const realTimeUpdates = useMonitoringStore((state) => state.realTimeUpdates);
  const isRealTimeConnected = useMonitoringStore(
    (state) => state.isRealTimeConnected
  );
  const autoRefreshEnabled = useMonitoringStore((state) => state.autoRefresh);
  const setTimeRange = useMonitoringStore((state) => state.setTimeRange);

  // WebSocket hook
  const { client, subscribeToSystemHealth, subscribeToAlerts } =
    useMonitoringWebSocket();

  // Local state
  const [selectedTimeRange, setSelectedTimeRange] = React.useState('24h');

  // Mock SLI/SLO data for demonstration
  const mockSLIMetrics: SLIMetrics[] = useMemo(
    () => [
      {
        name: 'Availability',
        current_value: 99.95,
        target: 99.9,
        window: '30d',
        status: 'passing',
        history: Array.from({ length: 30 }, (_, i) => ({
          timestamp: new Date(
            Date.now() - (29 - i) * 24 * 60 * 60 * 1000
          ).toISOString(),
          value: 99.9 + Math.random() * 0.1 - 0.05,
          target: 99.9,
          achieved: true,
        })),
      },
      {
        name: 'Latency P95',
        current_value: 245,
        target: 300,
        window: '24h',
        status: 'passing',
        history: Array.from({ length: 24 }, (_, i) => ({
          timestamp: new Date(
            Date.now() - (23 - i) * 60 * 60 * 1000
          ).toISOString(),
          value: 200 + Math.random() * 100,
          target: 300,
          achieved: true,
        })),
      },
      {
        name: 'Error Rate',
        current_value: 0.12,
        target: 1.0,
        window: '24h',
        status: 'passing',
        history: Array.from({ length: 24 }, (_, i) => ({
          timestamp: new Date(
            Date.now() - (23 - i) * 60 * 60 * 1000
          ).toISOString(),
          value: Math.random() * 0.5,
          target: 1.0,
          achieved: true,
        })),
      },
      {
        name: 'Throughput',
        current_value: 1250,
        target: 1000,
        window: '1h',
        status: 'passing',
        history: Array.from({ length: 60 }, (_, i) => ({
          timestamp: new Date(Date.now() - (59 - i) * 60 * 1000).toISOString(),
          value: 1000 + Math.random() * 500,
          target: 1000,
          achieved: true,
        })),
      },
    ],
    []
  );

  // Mock component health data
  const mockComponents: ComponentHealth[] = useMemo(
    () => [
      {
        name: 'API Gateway',
        status: 'healthy',
        score: 98,
        last_check: new Date().toISOString(),
        metrics: { response_time: 120, requests_per_second: 450 },
        dependencies: ['Authentication Service', 'Rate Limiter'],
      },
      {
        name: 'Document Processor',
        status: 'degraded',
        score: 75,
        last_check: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
        metrics: { queue_depth: 25, processing_rate: 15, error_rate: 2.5 },
        dependencies: ['Storage Service', 'OCR Service'],
      },
      {
        name: 'Search Engine',
        status: 'healthy',
        score: 92,
        last_check: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
        metrics: { query_latency: 85, index_size: '2.5GB', cache_hit_rate: 85 },
        dependencies: ['Vector Database', 'Knowledge Graph'],
      },
      {
        name: 'Vector Database',
        status: 'healthy',
        score: 88,
        last_check: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
        metrics: { memory_usage: 65, disk_usage: 45, query_time: 45 },
        dependencies: [],
      },
      {
        name: 'Knowledge Graph',
        status: 'healthy',
        score: 95,
        last_check: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
        metrics: { node_count: 125000, edge_count: 340000, query_time: 35 },
        dependencies: ['Neo4j Database'],
      },
      {
        name: 'User Analytics',
        status: 'healthy',
        score: 91,
        last_check: new Date(Date.now() - 4 * 60 * 1000).toISOString(),
        metrics: { active_sessions: 127, events_per_minute: 450 },
        dependencies: ['Event Store', 'Redis Cache'],
      },
    ],
    []
  );

  // Mock system health trend data
  const healthTrendData = useMemo(() => {
    return Array.from({ length: 24 }, (_, i) => ({
      time: new Date(Date.now() - (23 - i) * 60 * 60 * 1000).toLocaleTimeString(
        [],
        { hour: '2-digit', minute: '2-digit' }
      ),
      health: 85 + Math.random() * 15,
      alerts: Math.floor(Math.random() * 10),
    }));
  }, []);

  // WebSocket subscription
  useEffect(() => {
    if (client && isRealTimeConnected) {
      subscribeToSystemHealth?.();
      subscribeToAlerts?.();
    }
  }, [client, isRealTimeConnected, subscribeToSystemHealth, subscribeToAlerts]);

  // Auto-refresh logic
  useEffect(() => {
    if (!autoRefresh || !autoRefreshEnabled) return;

    const interval = setInterval(() => {
      // Refresh data would go here
      console.log('Auto-refreshing system overview data...');
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, autoRefreshEnabled, refreshInterval]);

  // Calculate overall stats
  const overallStats = useMemo(() => {
    const healthyComponents = mockComponents.filter(
      (c) => c.status === 'healthy'
    ).length;
    const totalComponents = mockComponents.length;
    const systemScore =
      systemHealth?.overall ||
      Math.round(
        mockComponents.reduce((sum, c) => sum + c.score, 0) / totalComponents
      );

    return {
      systemScore,
      healthyComponents,
      totalComponents,
      activeAlerts: activeAlerts.filter((a) => a.status === 'active').length,
      criticalAlerts: criticalAlerts.length,
      uptime: 99.95, // Mock uptime
      lastUpdate: systemHealth?.timestamp || new Date().toISOString(),
    };
  }, [systemHealth, mockComponents, activeAlerts, criticalAlerts]);

  const formatLastUpdate = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / (1000 * 60));

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      return date.toLocaleTimeString();
    } catch {
      return 'Unknown';
    }
  };

  if (compact) {
    return (
      <div className={cn('space-y-4', className)}>
        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            title="System Health"
            value={overallStats.systemScore}
            unit="%"
            status={
              overallStats.systemScore >= 90
                ? 'success'
                : overallStats.systemScore >= 70
                  ? 'warning'
                  : 'error'
            }
            icon={<SignalIcon className="h-5 w-5" />}
            size="sm"
          />
          <MetricCard
            title="Components"
            value={`${overallStats.healthyComponents}/${overallStats.totalComponents}`}
            status={
              overallStats.healthyComponents === overallStats.totalComponents
                ? 'success'
                : 'warning'
            }
            icon={<ServerIcon className="h-5 w-5" />}
            size="sm"
          />
          <MetricCard
            title="Active Alerts"
            value={overallStats.activeAlerts}
            status={
              overallStats.criticalAlerts > 0
                ? 'error'
                : overallStats.activeAlerts > 0
                  ? 'warning'
                  : 'success'
            }
            icon={<BellIcon className="h-5 w-5" />}
            size="sm"
          />
          <MetricCard
            title="Uptime"
            value={overallStats.uptime}
            unit="%"
            status="success"
            icon={<ClockIcon className="h-5 w-5" />}
            size="sm"
          />
        </div>

        {/* Status Grid */}
        <StatusGrid
          components={mockComponents}
          compact={true}
          columns={2}
          onComponentClick={onComponentClick}
        />

        {/* Recent Alerts */}
        {criticalAlerts.length > 0 && (
          <AlertList
            alerts={criticalAlerts.slice(0, 3)}
            title="Critical Alerts"
            compact={true}
            showFilters={false}
            onAlertClick={onAlertClick}
          />
        )}
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">
            System Overview
          </h1>
          <p className="text-foreground mt-1">
            Real-time system health and performance monitoring
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div
              className={cn(
                'h-2 w-2 rounded-full',
                isRealTimeConnected ? 'bg-green-500' : 'bg-red-500'
              )}
            />
            <span className="text-sm text-foreground">
              {isRealTimeConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <Badge variant="outline">
            Updated {formatLastUpdate(overallStats.lastUpdate)}
          </Badge>
          <Button variant="outline" size="sm">
            <ArrowPathIcon className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="System Health"
          value={overallStats.systemScore}
          unit="%"
          status={
            overallStats.systemScore >= 90
              ? 'success'
              : overallStats.systemScore >= 70
                ? 'warning'
                : 'error'
          }
          description="Overall system health score"
          icon={<SignalIcon className="h-6 w-6" />}
          onClick={() => onSystemHealthClick?.(systemHealth!)}
          threshold={{ value: 80, type: 'gte' }}
        />
        <MetricCard
          title="Component Health"
          value={`${overallStats.healthyComponents}/${overallStats.totalComponents}`}
          status={
            overallStats.healthyComponents === overallStats.totalComponents
              ? 'success'
              : 'warning'
          }
          description="Healthy components"
          icon={<ServerIcon className="h-6 w-6" />}
          onClick={() => {}}
        />
        <MetricCard
          title="Active Alerts"
          value={overallStats.activeAlerts}
          status={
            overallStats.criticalAlerts > 0
              ? 'error'
              : overallStats.activeAlerts > 0
                ? 'warning'
                : 'success'
          }
          description={`${overallStats.criticalAlerts} critical`}
          icon={<BellIcon className="h-6 w-6" />}
          onClick={() => {}}
        />
        <MetricCard
          title="System Uptime"
          value={overallStats.uptime}
          unit="%"
          status="success"
          description="Last 30 days"
          icon={<ClockIcon className="h-6 w-6" />}
          threshold={{ value: 99, type: 'gte' }}
        />
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="components">Components</TabsTrigger>
          <TabsTrigger value="sli-slo">SLI/SLO</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Health Trend Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <ChartBarIcon className="h-5 w-5" />
                  <span>System Health Trend</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={healthTrendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis domain={[0, 100]} />
                      <Tooltip />
                      <Area
                        type="monotone"
                        dataKey="health"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.3}
                        name="Health Score"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Quick Status */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <CheckCircleIcon className="h-5 w-5" />
                  <span>System Status</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Status Items */}
                {mockComponents.slice(0, 4).map((component) => {
                  const statusColor =
                    component.status === 'healthy'
                      ? 'text-green-600'
                      : component.status === 'degraded'
                        ? 'text-yellow-600'
                        : 'text-red-600';
                  return (
                    <div
                      key={component.name}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center space-x-3">
                        <div
                          className={cn(
                            'h-2 w-2 rounded-full',
                            statusColor.replace('text', 'bg')
                          )}
                        />
                        <span className="font-medium">{component.name}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span
                          className={cn('text-sm font-medium', statusColor)}
                        >
                          {component.score}%
                        </span>
                        <Progress value={component.score} className="w-20" />
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </div>

          {/* Real-time Updates */}
          {realTimeUpdates.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <SignalIcon className="h-5 w-5" />
                  <span>Recent Activity</span>
                  <Badge variant="outline">{realTimeUpdates.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {realTimeUpdates
                    .slice(-10)
                    .reverse()
                    .map((update, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between text-sm"
                      >
                        <span className="text-foreground">
                          {update.type.replace(/_/g, ' ')}
                        </span>
                        <span className="text-muted-foreground">
                          {formatLastUpdate(update.timestamp)}
                        </span>
                      </div>
                    ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Components Tab */}
        <TabsContent value="components">
          <StatusGrid
            components={mockComponents}
            title="Component Health"
            description="Real-time status of all system components"
            showDetails={showDetails}
            showActions={true}
            onComponentClick={onComponentClick}
          />
        </TabsContent>

        {/* SLI/SLO Tab */}
        <TabsContent value="sli-slo" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {mockSLIMetrics.map((sli) => (
              <Card key={sli.name}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>{sli.name}</span>
                    <Badge
                      variant={
                        sli.status === 'passing' ? 'default' : 'destructive'
                      }
                    >
                      {sli.status}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-foreground">Current</span>
                      <span className="text-lg font-semibold">
                        {sli.name.includes('Rate')
                          ? `${sli.current_value}%`
                          : sli.current_value}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-foreground">Target</span>
                      <span className="text-lg font-semibold">
                        {sli.name.includes('Rate')
                          ? `${sli.target}%`
                          : sli.target}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-foreground">Window</span>
                      <span className="text-sm">{sli.window}</span>
                    </div>
                    <Progress
                      value={(sli.current_value / sli.target) * 100}
                      className="h-2"
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts">
          <AlertList
            alerts={activeAlerts}
            title="System Alerts"
            showFilters={true}
            showActions={true}
            maxHeight="500px"
            onAlertClick={onAlertClick}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SystemOverviewDashboard;
