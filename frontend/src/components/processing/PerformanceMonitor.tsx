/**
 * Performance Monitor Component
 *
 * Real-time performance monitoring and metrics visualization for
 * the document processing system with charts and analytics.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  CpuChipIcon,
  CircleStackIcon,
  ServerIcon,
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  DocumentTextIcon,
  ArrowsUpDownIcon,
  SignalIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useRealtimeProcessing } from '@/hooks/useRealtimeProcessing';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import { PerformanceMetrics } from '@/types/realtime-processing';
import { cn } from '@/lib/utils';
import { formatDuration, formatBytes } from '@/utils/formatUtils';

interface PerformanceMonitorProps {
  refreshInterval?: number;
  showCharts?: boolean;
  showHistory?: boolean;
  historyLimit?: number;
  compact?: boolean;
  showAlerts?: boolean;
  className?: string;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: React.ComponentType<any>;
  color: string;
  trend?: {
    value: number;
    direction: 'up' | 'down';
  };
  threshold?: {
    warning: number;
    critical: number;
  };
  format?: (value: number) => string;
}

interface MiniChartProps {
  data: number[];
  height?: number;
  color?: string;
  showGrid?: boolean;
}

interface AlertProps {
  type: 'warning' | 'critical';
  message: string;
  metric: string;
  value: number;
  threshold: number;
  onDismiss?: () => void;
}

interface PerformanceHistoryProps {
  metrics: PerformanceMetrics[];
  onClear: () => void;
}

// Metric configurations
const metricConfigs = {
  cpu: {
    title: 'CPU Usage',
    icon: CpuChipIcon,
    color: 'text-blue-500',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    threshold: { warning: 70, critical: 90 },
    format: (value: number) => `${value.toFixed(1)}%`,
  },
  memory: {
    title: 'Memory Usage',
    icon: CircleStackIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    threshold: { warning: 80, critical: 95 },
    format: (value: number) => formatBytes(value),
  },
  throughput: {
    title: 'Throughput',
    icon: ArrowTrendingUpIcon,
    color: 'text-purple-500',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    threshold: { warning: 50, critical: 25 },
    format: (value: number) => `${value.toFixed(1)}/min`,
  },
  latency: {
    title: 'Response Time',
    icon: ClockIcon,
    color: 'text-orange-500',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    threshold: { warning: 500, critical: 1000 },
    format: (value: number) => `${value.toFixed(0)}ms`,
  },
};

// Helper Components
const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  icon: Icon,
  color,
  trend,
  threshold,
  format = (v) => v.toString()
}) => {
  const numericValue = typeof value === 'number' ? value : parseFloat(value.toString());
  const formattedValue = format(numericValue);

  let statusColor = 'text-gray-600';
  if (threshold) {
    if (numericValue >= threshold.critical) {
      statusColor = 'text-red-600';
    } else if (numericValue >= threshold.warning) {
      statusColor = 'text-yellow-600';
    }
  }

  return (
    <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className={cn('p-2 rounded-lg', metricConfigs.cpu.bgColor)}>
            <Icon className={cn('w-5 h-5', color)} />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">{title}</p>
            <div className="flex items-center space-x-2">
              <p className={cn('text-lg font-semibold', statusColor)}>
                {formattedValue}
              </p>
              {unit && (
                <span className="text-sm text-gray-500">{unit}</span>
              )}
            </div>
          </div>
        </div>

        {trend && (
          <div className="flex items-center space-x-1">
            {trend.direction === 'up' ? (
              <ArrowTrendingUpIcon className="w-4 h-4 text-green-500" />
            ) : (
              <ArrowTrendingDownIcon className="w-4 h-4 text-red-500" />
            )}
            <span className={cn(
              'text-xs font-medium',
              trend.direction === 'up' ? 'text-green-600' : 'text-red-600'
            )}>
              {Math.abs(trend.value).toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {/* Threshold indicator */}
      {threshold && (
        <div className="mt-3">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={cn(
                'h-2 rounded-full transition-all duration-300',
                numericValue >= threshold.critical ? 'bg-red-500' :
                numericValue >= threshold.warning ? 'bg-yellow-500' : 'bg-green-500'
              )}
              style={{ width: `${Math.min(100, (numericValue / threshold.critical) * 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>0</span>
            <span>{threshold.warning}%</span>
            <span>{threshold.critical}%</span>
          </div>
        </div>
      )}
    </div>
  );
};

const MiniChart: React.FC<MiniChartProps> = ({
  data,
  height = 40,
  color = '#3B82F6',
  showGrid = false
}) => {
  const maxValue = Math.max(...data, 1);
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - (value / maxValue) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="relative" style={{ height: `${height}px` }}>
      {showGrid && (
        <svg className="absolute inset-0 w-full h-full">
          <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#E5E7EB" strokeWidth="1" />
          <line x1="0" y1="100%" x2="100%" y2="100%" stroke="#E5E7EB" strokeWidth="1" />
        </svg>
      )}
      <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2"
          points={points}
        />
        <polyline
          fill={color}
          fillOpacity="0.1"
          points={`${points} 100,100 0,100`}
        />
      </svg>
    </div>
  );
};

const Alert: React.FC<AlertProps> = ({
  type,
  message,
  metric,
  value,
  threshold,
  onDismiss
}) => {
  const config = type === 'critical' ? {
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    textColor: 'text-red-800',
    iconColor: 'text-red-500'
  } : {
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    textColor: 'text-yellow-800',
    iconColor: 'text-yellow-500'
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex items-center space-x-3 p-3 rounded-lg border',
        config.bgColor,
        config.borderColor
      )}
    >
      <ExclamationTriangleIcon className={cn('w-5 h-5', config.iconColor)} />
      <div className="flex-1">
        <p className={cn('text-sm font-medium', config.textColor)}>
          {metric} Alert
        </p>
        <p className="text-xs text-gray-600">
          {message} {`(${value} > ${threshold})`}
        </p>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          ×
        </button>
      )}
    </motion.div>
  );
};

const PerformanceHistory: React.FC<PerformanceHistoryProps> = ({
  metrics,
  onClear
}) => {
  if (metrics.length === 0) {
    return (
      <div className="text-center py-8">
        <ChartBarIcon className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-sm text-gray-500">No performance data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="text-center">
          <p className="text-xs text-gray-500">Avg CPU</p>
          <p className="text-lg font-semibold text-gray-900">
            {(metrics.reduce((sum, m) => sum + m.connectionLatency, 0) / metrics.length).toFixed(1)}%
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Avg Memory</p>
          <p className="text-lg font-semibold text-gray-900">
            {(metrics.reduce((sum, m) => sum + m.messageRate, 0) / metrics.length).toFixed(1)}
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Peak Latency</p>
          <p className="text-lg font-semibold text-gray-900">
            {Math.max(...metrics.map(m => m.connectionLatency))}ms
          </p>
        </div>
        <div className="text-center">
          <p className="text-xs text-gray-500">Uptime</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatDuration(metrics[metrics.length - 1]?.uptime || 0)}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Latency History</h4>
          <MiniChart
            data={metrics.slice(-20).map(m => m.connectionLatency)}
            color="#EF4444"
            height={80}
          />
        </div>

        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Message Rate</h4>
          <MiniChart
            data={metrics.slice(-20).map(m => m.messageRate)}
            color="#10B981"
            height={80}
          />
        </div>
      </div>

      {/* Clear button */}
      <div className="flex justify-end">
        <button
          onClick={onClear}
          className="px-3 py-2 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded transition-colors"
        >
          Clear History
        </button>
      </div>
    </div>
  );
};

// Main Performance Monitor Component
export const PerformanceMonitor: React.FC<PerformanceMonitorProps> = ({
  refreshInterval = 5000,
  showCharts = true,
  showHistory = false,
  historyLimit = 100,
  compact = false,
  showAlerts = true,
  className
}) => {
  const [performanceHistory, setPerformanceHistory] = useState<PerformanceMetrics[]>([]);
  const [alerts, setAlerts] = useState<Array<Alert & { id: string }>>([]);

  const {
    systemMetrics,
    connectionLatency,
    messageRate,
    documents,
  } = useRealtimeProcessing();

  const store = useRealtimeProcessingStore();

  // Calculate derived metrics
  const currentMetrics: PerformanceMetrics = useMemo(() => ({
    connectionLatency,
    messageRate,
    errorRate: store.queue.metrics.errorRate,
    reconnectionCount: store.connection.reconnectionAttempts,
    uptime: store.connection.lastConnectedAt
      ? Date.now() - new Date(store.connection.lastConnectedAt).getTime()
      : 0,
    lastMessageTimestamp: Date.now(),
  }), [connectionLatency, messageRate, store]);

  // Calculate trends
  const trends = useMemo(() => {
    if (performanceHistory.length < 2) return {};

    const previous = performanceHistory[performanceHistory.length - 2];
    const current = currentMetrics;

    return {
      cpu: previous.connectionLatency > 0
        ? { value: ((current.connectionLatency - previous.connectionLatency) / previous.connectionLatency) * 100,
            direction: current.connectionLatency > previous.connectionLatency ? 'up' as const : 'down' as const }
        : undefined,
      memory: previous.messageRate > 0
        ? { value: ((current.messageRate - previous.messageRate) / previous.messageRate) * 100,
            direction: current.messageRate > previous.messageRate ? 'up' as const : 'down' as const }
        : undefined,
    };
  }, [currentMetrics, performanceHistory]);

  // Update performance history
  useEffect(() => {
    const interval = setInterval(() => {
      setPerformanceHistory(prev => {
        const newHistory = [...prev, currentMetrics];
        return newHistory.slice(-historyLimit);
      });
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [currentMetrics, refreshInterval, historyLimit]);

  // Check for alerts
  useEffect(() => {
    if (!showAlerts) return;

    const newAlerts: Array<Alert & { id: string }> = [];

    // CPU usage alert
    if (systemMetrics.cpuUsage >= metricConfigs.cpu.threshold!.critical) {
      newAlerts.push({
        id: `cpu-critical-${Date.now()}`,
        type: 'critical',
        message: 'CPU usage is critically high',
        metric: 'CPU',
        value: systemMetrics.cpuUsage,
        threshold: metricConfigs.cpu.threshold!.critical,
      });
    } else if (systemMetrics.cpuUsage >= metricConfigs.cpu.threshold!.warning) {
      newAlerts.push({
        id: `cpu-warning-${Date.now()}`,
        type: 'warning',
        message: 'CPU usage is elevated',
        metric: 'CPU',
        value: systemMetrics.cpuUsage,
        threshold: metricConfigs.cpu.threshold!.warning,
      });
    }

    // Memory usage alert
    if (systemMetrics.memoryUsage >= metricConfigs.memory.threshold!.critical) {
      newAlerts.push({
        id: `memory-critical-${Date.now()}`,
        type: 'critical',
        message: 'Memory usage is critically high',
        metric: 'Memory',
        value: systemMetrics.memoryUsage,
        threshold: metricConfigs.memory.threshold!.critical,
      });
    }

    // Latency alert
    if (connectionLatency >= metricConfigs.latency.threshold!.critical) {
      newAlerts.push({
        id: `latency-critical-${Date.now()}`,
        type: 'critical',
        message: 'Response time is too high',
        metric: 'Latency',
        value: connectionLatency,
        threshold: metricConfigs.latency.threshold!.critical,
      });
    }

    // Error rate alert
    if (currentMetrics.errorRate >= 10) {
      newAlerts.push({
        id: `error-critical-${Date.now()}`,
        type: 'critical',
        message: 'High error rate detected',
        metric: 'Error Rate',
        value: currentMetrics.errorRate,
        threshold: 10,
      });
    }

    setAlerts(newAlerts);
  }, [systemMetrics, connectionLatency, currentMetrics.errorRate, showAlerts]);

  const handleDismissAlert = useCallback((alertId: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  }, []);

  const handleClearHistory = useCallback(() => {
    setPerformanceHistory([]);
  }, []);

  if (compact) {
    return (
      <div className={cn('grid grid-cols-2 md:grid-cols-4 gap-4', className)}>
        <MetricCard
          title="CPU"
          value={systemMetrics.cpuUsage}
          icon={CpuChipIcon}
          color="text-blue-500"
          trend={trends.cpu}
          threshold={metricConfigs.cpu.threshold}
          format={v => `${v.toFixed(1)}%`}
        />
        <MetricCard
          title="Memory"
          value={systemMetrics.memoryUsage}
          icon={CircleStackIcon}
          color="text-green-500"
          trend={trends.memory}
          threshold={metricConfigs.memory.threshold}
          format={v => formatBytes(v)}
        />
        <MetricCard
          title="Latency"
          value={connectionLatency}
          icon={ClockIcon}
          color="text-orange-500"
          threshold={metricConfigs.latency.threshold}
          format={v => `${v.toFixed(0)}ms`}
        />
        <MetricCard
          title="Messages"
          value={messageRate}
          icon={ArrowTrendingUpIcon}
          color="text-purple-500"
          format={v => `${v.toFixed(1)}/s`}
        />
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      {/* Alerts */}
      {showAlerts && alerts.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-900">Performance Alerts</h3>
          {alerts.map(alert => (
            <Alert
              key={alert.id}
              type={alert.type}
              message={alert.message}
              metric={alert.metric}
              value={alert.value}
              threshold={alert.threshold}
              onDismiss={() => handleDismissAlert(alert.id)}
            />
          ))}
        </div>
      )}

      {/* System Metrics */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">System Performance</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="CPU Usage"
            value={systemMetrics.cpuUsage}
            icon={CpuChipIcon}
            color="text-blue-500"
            trend={trends.cpu}
            threshold={metricConfigs.cpu.threshold}
            format={v => `${v.toFixed(1)}%`}
          />
          <MetricCard
            title="Memory Usage"
            value={systemMetrics.memoryUsage}
            icon={CircleStackIcon}
            color="text-green-500"
            trend={trends.memory}
            threshold={metricConfigs.memory.threshold}
            format={v => formatBytes(v)}
          />
          <MetricCard
            title="Active Jobs"
            value={systemMetrics.activeJobs}
            icon={ServerIcon}
            color="text-purple-500"
            unit="jobs"
          />
          <MetricCard
            title="Avg Duration"
            value={systemMetrics.averageJobDuration}
            icon={ClockIcon}
            color="text-orange-500"
            format={v => formatDuration(v)}
          />
        </div>
      </div>

      {/* Connection Metrics */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Connection Performance</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard
            title="Response Time"
            value={connectionLatency}
            icon={ClockIcon}
            color="text-orange-500"
            threshold={metricConfigs.latency.threshold}
            format={v => `${v.toFixed(0)}ms`}
          />
          <MetricCard
            title="Message Rate"
            value={messageRate}
            icon={ArrowTrendingUpIcon}
            color="text-green-500"
            format={v => `${v.toFixed(1)}/s`}
          />
          <MetricCard
            title="Error Rate"
            value={currentMetrics.errorRate}
            icon={ExclamationTriangleIcon}
            color="text-red-500"
            threshold={{ warning: 5, critical: 10 }}
            format={v => `${v.toFixed(1)}%`}
          />
        </div>
      </div>

      {/* Queue Metrics */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Processing Queue</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            title="Success Rate"
            value={store.queue.metrics.successRate}
            icon={ArrowTrendingUpIcon}
            color="text-green-500"
            format={v => `${v.toFixed(1)}%`}
          />
          <MetricCard
            title="Throughput"
            value={store.queue.metrics.throughput}
            icon={DocumentTextIcon}
            color="text-blue-500"
            format={v => `${v.toFixed(1)}/min`}
          />
          <MetricCard
            title="Avg Processing"
            value={store.queue.metrics.averageProcessingTime}
            icon={ClockIcon}
            color="text-purple-500"
            format={v => `${v.toFixed(1)}s`}
          />
          <MetricCard
            title="Queued Jobs"
            value={store.queue.summary.queued}
            icon={ArrowsUpDownIcon}
            color="text-orange-500"
            unit="jobs"
          />
        </div>
      </div>

      {/* Performance History */}
      {showHistory && (
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Performance History</h3>
          <PerformanceHistory
            metrics={performanceHistory}
            onClear={handleClearHistory}
          />
        </div>
      )}
    </div>
  );
};

export default PerformanceMonitor;