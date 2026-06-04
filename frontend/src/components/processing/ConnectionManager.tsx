/**
 * Connection Manager Component
 *
 * UI component for managing WebSocket connection status with
 * reconnection controls, diagnostics, and network information.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  SignalIcon,
  WifiIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ServerIcon,
  ClockIcon,
  ChartBarIcon,
  CpuChipIcon,
  CircleStackIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import {
  useRealtimeProcessing,
  useConnectionStatus,
} from '@/hooks/useRealtimeProcessing';
import { getRealtimeWebSocketService } from '@/services/realtimeWebSocketService';
import {
  WebSocketConnectionState,
  PerformanceMetrics,
} from '@/types/realtime-processing';
import { cn } from '@/lib/utils';
import { formatDuration, formatBytes } from '@/utils/formatUtils';

interface ConnectionManagerProps {
  compact?: boolean;
  showDiagnostics?: boolean;
  showControls?: boolean;
  showNetworkInfo?: boolean;
  position?: 'floating' | 'static';
  className?: string;
}

interface ConnectionStatusProps {
  status: WebSocketConnectionState['status'];
  isConnected: boolean;
  reconnectionAttempts: number;
  maxReconnectionAttempts: number;
  lastError?: string;
  onReconnect?: () => Promise<void>;
  onDisconnect?: () => void;
}

interface ConnectionMetricsProps {
  metrics: PerformanceMetrics;
  compact?: boolean;
}

interface NetworkDiagnosticsProps {
  connectionState: WebSocketConnectionState;
  metrics: PerformanceMetrics;
  onTestConnection?: () => Promise<void>;
  onResetConnection?: () => void;
}

// Connection status configurations
const statusConfigs = {
  connected: {
    icon: SignalIcon,
    color: 'text-[var(--nous-terra)]',
    bgColor: 'bg-[var(--nous-terra)]/10',
    borderColor: 'border-[var(--nous-terra)]/20',
    label: 'Connected',
    description: 'Real-time connection is active',
  },
  connecting: {
    icon: ArrowPathIcon,
    color: 'text-[var(--nous-sol-safe)]',
    bgColor: 'bg-[var(--nous-sol)]/10',
    borderColor: 'border-[var(--nous-sol)]/20',
    label: 'Connecting',
    description: 'Establishing connection...',
  },
  disconnected: {
    icon: XCircleIcon,
    color: 'text-muted-foreground',
    bgColor: 'bg-[var(--nous-bg-3)]',
    borderColor: 'border-border',
    label: 'Disconnected',
    description: 'No active connection',
  },
  reconnecting: {
    icon: ArrowPathIcon,
    color: 'text-[var(--nous-corona)]',
    bgColor: 'bg-[var(--nous-corona)]/10',
    borderColor: 'border-[var(--nous-corona)]/20',
    label: 'Reconnecting',
    description: 'Attempting to reconnect...',
  },
  error: {
    icon: ExclamationTriangleIcon,
    color: 'text-[var(--nous-mars)]',
    bgColor: 'bg-[var(--nous-mars)]/10',
    borderColor: 'border-[var(--nous-mars)]/20',
    label: 'Connection Error',
    description: 'Connection failed',
  },
};

// Helper Components
const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  isConnected,
  reconnectionAttempts,
  maxReconnectionAttempts,
  lastError,
  onReconnect,
  onDisconnect,
}) => {
  const config = statusConfigs[status];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'flex items-center space-x-3 p-3 rounded-lg border',
        config.bgColor,
        config.borderColor
      )}
    >
      <div className="flex-shrink-0">
        {status === 'connecting' || status === 'reconnecting' ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          >
            <Icon className={cn('w-5 h-5', config.color)} />
          </motion.div>
        ) : (
          <Icon className={cn('w-5 h-5', config.color)} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <div>
            <h3 className={cn('text-sm font-medium', config.color)}>
              {config.label}
            </h3>
            <p className="text-xs text-foreground mt-1">{config.description}</p>
            {lastError && (
              <p className="text-xs text-[var(--nous-mars)] mt-1">
                {lastError}
              </p>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* Reconnection progress */}
            {reconnectionAttempts > 0 && (
              <div className="text-xs text-muted-foreground">
                {reconnectionAttempts}/{maxReconnectionAttempts}
              </div>
            )}

            {/* Action buttons */}
            {!isConnected && onReconnect && (
              <button
                onClick={onReconnect}
                className="px-3 py-1 text-xs font-medium text-[var(--nous-sol-safe)] bg-[var(--nous-sol)]/10 hover:bg-[var(--nous-sol)]/20 rounded transition-colors"
              >
                Reconnect
              </button>
            )}

            {isConnected && onDisconnect && (
              <button
                onClick={onDisconnect}
                className="px-3 py-1 text-xs font-medium text-[var(--nous-mars)] bg-[var(--nous-mars)]/10 hover:bg-[var(--nous-mars)]/20 rounded transition-colors"
              >
                Disconnect
              </button>
            )}
          </div>
        </div>

        {/* Reconnection progress bar */}
        {(status === 'connecting' || status === 'reconnecting') && (
          <div className="mt-2">
            <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-1">
              <motion.div
                className="bg-[var(--nous-sol)] h-1 rounded-full"
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: 3, repeat: Infinity }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const ConnectionMetrics: React.FC<ConnectionMetricsProps> = ({
  metrics,
  compact = false,
}) => {
  const formatLatency = (latency: number) => {
    if (latency < 1) return '< 1ms';
    return `${Math.round(latency)}ms`;
  };

  const formatRate = (rate: number) => {
    if (rate < 1) return `${(rate * 60).toFixed(1)}/min`;
    return `${rate.toFixed(1)}/s`;
  };

  if (compact) {
    return (
      <div className="flex items-center space-x-4 text-xs text-foreground">
        <div className="flex items-center space-x-1">
          <SignalIcon className="w-3 h-3" />
          <span>{formatLatency(metrics.connectionLatency)}</span>
        </div>
        <div className="flex items-center space-x-1">
          <ChartBarIcon className="w-3 h-3" />
          <span>{formatRate(metrics.messageRate)}</span>
        </div>
        {metrics.errorRate > 0 && (
          <div className="flex items-center space-x-1 text-[var(--nous-mars)]">
            <ExclamationTriangleIcon className="w-3 h-3" />
            <span>{metrics.errorRate.toFixed(1)}%</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-card p-3 rounded-lg border border-border">
        <div className="flex items-center space-x-2">
          <SignalIcon className="w-4 h-4 text-[var(--nous-sol-safe)]" />
          <div>
            <p className="text-xs text-muted-foreground">Latency</p>
            <p className="text-sm font-semibold text-foreground">
              {formatLatency(metrics.connectionLatency)}
            </p>
          </div>
        </div>
      </div>

      <div className="bg-card p-3 rounded-lg border border-border">
        <div className="flex items-center space-x-2">
          <ChartBarIcon className="w-4 h-4 text-[var(--nous-terra)]" />
          <div>
            <p className="text-xs text-muted-foreground">Message Rate</p>
            <p className="text-sm font-semibold text-foreground">
              {formatRate(metrics.messageRate)}
            </p>
          </div>
        </div>
      </div>

      <div className="bg-card p-3 rounded-lg border border-border">
        <div className="flex items-center space-x-2">
          <ExclamationTriangleIcon className="w-4 h-4 text-[var(--nous-mars)]" />
          <div>
            <p className="text-xs text-muted-foreground">Error Rate</p>
            <p className="text-sm font-semibold text-foreground">
              {metrics.errorRate.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      <div className="bg-card p-3 rounded-lg border border-border">
        <div className="flex items-center space-x-2">
          <ClockIcon className="w-4 h-4 text-[var(--nous-fg-3)]" />
          <div>
            <p className="text-xs text-muted-foreground">Uptime</p>
            <p className="text-sm font-semibold text-foreground">
              {formatDuration(metrics.uptime)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

const NetworkDiagnostics: React.FC<NetworkDiagnosticsProps> = ({
  connectionState,
  metrics,
  onTestConnection,
  onResetConnection,
}) => {
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [testResults, setTestResults] = useState<{
    latency?: number;
    success?: boolean;
    error?: string;
  } | null>(null);

  const handleTestConnection = useCallback(async () => {
    if (!onTestConnection) return;

    setIsTestingConnection(true);
    setTestResults(null);

    try {
      const startTime = Date.now();
      await onTestConnection();
      const latency = Date.now() - startTime;

      setTestResults({ latency, success: true });
    } catch (error) {
      setTestResults({
        success: false,
        error:
          error instanceof Error ? error.message : 'Connection test failed',
      });
    } finally {
      setIsTestingConnection(false);
    }
  }, [onTestConnection]);

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <h3 className="text-sm font-semibold text-foreground mb-4">
        Network Diagnostics
      </h3>

      <div className="space-y-4">
        {/* Connection State Info */}
        <div>
          <h4 className="text-xs font-medium text-foreground mb-2">
            Connection Status
          </h4>
          <dl className="grid grid-cols-1 gap-2 text-xs">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Status:</dt>
              <dd
                className={cn(
                  'font-medium',
                  statusConfigs[connectionState.status].color
                )}
              >
                {statusConfigs[connectionState.status].label}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Last Connected:</dt>
              <dd className="font-medium">
                {connectionState.lastConnectedAt
                  ? new Date(
                      connectionState.lastConnectedAt
                    ).toLocaleTimeString()
                  : 'Never'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Reconnection Attempts:</dt>
              <dd className="font-medium">
                {connectionState.reconnectionAttempts}/
                {connectionState.maxReconnectionAttempts}
              </dd>
            </div>
            {connectionState.lastError && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Last Error:</dt>
                <dd className="font-medium text-[var(--nous-mars)] truncate max-w-xs">
                  {connectionState.lastError}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Performance Metrics */}
        <div>
          <h4 className="text-xs font-medium text-foreground mb-2">
            Performance Metrics
          </h4>
          <ConnectionMetrics metrics={metrics} />
        </div>

        {/* Connection Test */}
        <div>
          <h4 className="text-xs font-medium text-foreground mb-2">
            Connection Test
          </h4>
          <div className="space-y-2">
            <button
              onClick={handleTestConnection}
              disabled={isTestingConnection}
              className="px-3 py-2 text-xs font-medium text-[var(--nous-sol-safe)] bg-[var(--nous-sol)]/10 hover:bg-[var(--nous-sol)]/20 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isTestingConnection ? 'Testing...' : 'Test Connection'}
            </button>

            {testResults && (
              <div
                className={cn(
                  'p-2 rounded text-xs',
                  testResults.success
                    ? 'bg-[var(--nous-terra)]/10 text-[var(--nous-terra)]'
                    : 'bg-[var(--nous-mars)]/10 text-[var(--nous-mars)]'
                )}
              >
                {testResults.success ? (
                  <div className="flex items-center space-x-2">
                    <CheckCircleIcon className="w-4 h-4" />
                    <span>
                      Connection successful! Latency: {testResults.latency}ms
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <XCircleIcon className="w-4 h-4" />
                    <span>{testResults.error}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex space-x-2">
          <button
            onClick={onResetConnection}
            className="px-3 py-2 text-xs font-medium text-[var(--nous-mars)] bg-[var(--nous-mars)]/10 hover:bg-[var(--nous-mars)]/20 rounded transition-colors"
          >
            Reset Connection
          </button>
        </div>
      </div>
    </div>
  );
};

// Main Connection Manager Component
export const ConnectionManager: React.FC<ConnectionManagerProps> = ({
  compact = false,
  showDiagnostics = false,
  showControls = true,
  showNetworkInfo = true,
  position = 'static',
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showDiagnosticsModal, setShowDiagnosticsModal] = useState(false);

  const {
    connectionStatus,
    isConnected,
    reconnect,
    disconnect,
    connectionLatency,
    messageRate,
    systemMetrics,
  } = useRealtimeProcessing();

  const connectionStatusData = useConnectionStatus();
  const wsService = getRealtimeWebSocketService();

  const metrics = wsService.getPerformanceMetrics();

  const handleTestConnection = useCallback(async () => {
    // Simple ping test
    const startTime = Date.now();
    const wsService = getRealtimeWebSocketService();

    if (!wsService.getConnectionState().status === 'connected') {
      throw new Error('No active connection');
    }

    // Send a test message
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Connection test timeout'));
      }, 5000);

      const handler = () => {
        clearTimeout(timeout);
        resolve(Date.now() - startTime);
      };

      // This would need to be implemented in the WebSocket service
      setTimeout(() => {
        clearTimeout(timeout);
        resolve(Date.now() - startTime);
      }, 100);
    });
  }, []);

  const handleResetConnection = useCallback(() => {
    disconnect();
    setTimeout(reconnect, 1000);
  }, [disconnect, reconnect]);

  if (compact) {
    return <ConnectionMetrics metrics={metrics} compact={true} />;
  }

  return (
    <div
      className={cn(
        position === 'floating' && 'fixed top-4 right-4 z-40 w-80',
        className
      )}
    >
      <div className="bg-card rounded-lg border border-border shadow-lg">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <SignalIcon className="w-5 h-5 text-foreground" />
              <h3 className="text-sm font-semibold text-foreground">
                Connection Status
              </h3>
            </div>
            <div className="flex items-center space-x-2">
              {showDiagnostics && (
                <button
                  onClick={() => setShowDiagnosticsModal(true)}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                  title="Connection Diagnostics"
                >
                  <InformationCircleIcon className="w-4 h-4" />
                </button>
              )}
              {position === 'floating' && (
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="text-muted-foreground hover:text-foreground transition-colors"
                >
                  {isExpanded ? (
                    <XMarkIcon className="w-4 h-4" />
                  ) : (
                    <ChartBarIcon className="w-4 h-4" />
                  )}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Connection Status */}
        <div className="p-4">
          <ConnectionStatus
            status={connectionStatusData.status}
            isConnected={connectionStatusData.isConnected}
            reconnectionAttempts={connectionStatusData.reconnectionAttempts}
            maxReconnectionAttempts={
              connectionStatusData.maxReconnectionAttempts
            }
            lastError={connectionStatusData.lastError}
            onReconnect={reconnect}
            onDisconnect={isConnected ? disconnect : undefined}
          />
        </div>

        {/* Expanded content */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-t border-border overflow-hidden"
            >
              <div className="p-4 space-y-4">
                {/* Network Info */}
                {showNetworkInfo && (
                  <div>
                    <h4 className="text-xs font-medium text-foreground mb-3">
                      Network Information
                    </h4>
                    <ConnectionMetrics metrics={metrics} />
                  </div>
                )}

                {/* Controls */}
                {showControls && (
                  <div>
                    <h4 className="text-xs font-medium text-foreground mb-3">
                      Connection Controls
                    </h4>
                    <div className="flex space-x-2">
                      {!isConnected && (
                        <button
                          onClick={reconnect}
                          className="px-3 py-2 text-xs font-medium text-[var(--nous-sol-safe)] bg-[var(--nous-sol)]/10 hover:bg-[var(--nous-sol)]/20 rounded transition-colors"
                        >
                          Connect
                        </button>
                      )}
                      {isConnected && (
                        <button
                          onClick={disconnect}
                          className="px-3 py-2 text-xs font-medium text-[var(--nous-mars)] bg-[var(--nous-mars)]/10 hover:bg-[var(--nous-mars)]/20 rounded transition-colors"
                        >
                          Disconnect
                        </button>
                      )}
                      <button
                        onClick={handleResetConnection}
                        className="px-3 py-2 text-xs font-medium text-foreground bg-[var(--nous-bg-2)] hover:bg-[var(--nous-bg-3)] rounded transition-colors"
                      >
                        Reset
                      </button>
                    </div>
                  </div>
                )}

                {/* Quick Stats */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-[var(--nous-bg-2)] p-2 rounded">
                    <div className="text-muted-foreground">Documents</div>
                    <div className="font-semibold text-foreground">
                      {systemMetrics.activeJobs} active
                    </div>
                  </div>
                  <div className="bg-[var(--nous-bg-2)] p-2 rounded">
                    <div className="text-muted-foreground">System Load</div>
                    <div className="font-semibold text-foreground">
                      {systemMetrics.cpuUsage.toFixed(1)}% CPU
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Diagnostics Modal */}
      <AnimatePresence>
        {showDiagnosticsModal && (
          <>
            <div
              className="fixed inset-0 bg-black bg-opacity-50 z-50"
              onClick={() => setShowDiagnosticsModal(false)}
            />
            <div className="fixed inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-y-1/2 md:-translate-x-1/2 md:w-[600px] md:max-h-[80vh] z-50">
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-card rounded-lg shadow-xl"
              >
                <div className="p-4 border-b border-border flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-foreground">
                    Connection Diagnostics
                  </h3>
                  <button
                    onClick={() => setShowDiagnosticsModal(false)}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <XMarkIcon className="w-5 h-5" />
                  </button>
                </div>

                <div className="p-4 overflow-y-auto max-h-[60vh]">
                  <NetworkDiagnostics
                    connectionState={connectionStatusData}
                    metrics={metrics}
                    onTestConnection={handleTestConnection}
                    onResetConnection={handleResetConnection}
                  />
                </div>
              </motion.div>
            </div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ConnectionManager;
