/**
 * WebSocket service for real-time monitoring data
 * Handles real-time updates for metrics, alerts, and system status
 */

import EventEmitter from 'events';
import { useMonitoringStore } from '@/stores/monitoringStore';
import {
  RealTimeUpdate,
  SystemHealthScore,
  PerformanceMetrics,
  BusinessMetrics,
  InfrastructureMetrics,
  Alert,
  UserAnalytics,
  WebSocketMessage
} from '@/types/monitoring';

// ============================================================================
// WEBSOCKET MESSAGE TYPES
// ============================================================================

export interface MonitoringWebSocketMessage extends WebSocketMessage {
  type: MonitoringMessageType;
}

export type MonitoringMessageType =
  | 'system_health_update'
  | 'performance_metrics_update'
  | 'business_metrics_update'
  | 'infrastructure_update'
  | 'alert_triggered'
  | 'alert_resolved'
  | 'alert_updated'
  | 'user_analytics_update'
  | 'connection_status'
  | 'error'
  | 'ping'
  | 'pong';

// ============================================================================
// MESSAGE PAYLOADS
// ============================================================================

export interface SystemHealthUpdatePayload {
  health: SystemHealthScore;
  timestamp: string;
}

export interface PerformanceMetricsUpdatePayload {
  metrics: PerformanceMetrics;
  timestamp: string;
}

export interface BusinessMetricsUpdatePayload {
  metrics: BusinessMetrics;
  timestamp: string;
}

export interface InfrastructureUpdatePayload {
  metrics: InfrastructureMetrics;
  timestamp: string;
}

export interface AlertTriggeredPayload {
  alert: Alert;
  timestamp: string;
}

export interface AlertResolvedPayload {
  alert_id: string;
  resolved_at: string;
  resolved_by?: string;
  timestamp: string;
}

export interface AlertUpdatedPayload {
  alert: Alert;
  changes: Record<string, any>;
  timestamp: string;
}

export interface UserAnalyticsUpdatePayload {
  analytics: UserAnalytics;
  timestamp: string;
}

export interface ConnectionStatusPayload {
  status: 'connected' | 'disconnected' | 'reconnecting';
  message?: string;
  timestamp: string;
}

export interface ErrorPayload {
  error: {
    message: string;
    code?: string;
    details?: any;
  };
  timestamp: string;
}

// ============================================================================
// MONITORING WEBSOCKET CLIENT
// ============================================================================

export class MonitoringWebSocketClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string | null = null;
  private organizationId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000; // Start with 1 second
  private maxReconnectDelay = 30000; // Max 30 seconds
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private heartbeatTimeout: NodeJS.Timeout | null = null;
  private isConnecting = false;
  private isDestroyed = false;

  constructor(url: string) {
    super();
    this.url = url;
  }

  // ============================================================================
  // CONNECTION MANAGEMENT
  // ============================================================================

  public async connect(token: string, organizationId: string): Promise<void> {
    if (this.isConnecting || this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isConnecting = true;
    this.token = token;
    this.organizationId = organizationId;

    try {
      await this.createConnection();
      this.startHeartbeat();
      this.emit('connected');
    } catch (error) {
      this.isConnecting = false;
      this.emit('error', error);
      throw error;
    }
  }

  private async createConnection(): Promise<void> {
    const wsUrl = `${this.url}?token=${encodeURIComponent(this.token!)}&org_id=${encodeURIComponent(this.organizationId!)}`;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this.emit('connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };

        this.ws.onclose = (event) => {
          this.isConnecting = false;
          this.stopHeartbeat();
          this.emit('disconnected', { code: event.code, reason: event.reason });

          // Attempt reconnection if not intentionally closed
          if (!this.isDestroyed && event.code !== 1000) {
            this.attemptReconnection();
          }
        };

        this.ws.onerror = (error) => {
          this.isConnecting = false;
          this.emit('error', error);
          reject(error);
        };

        // Set connection timeout
        setTimeout(() => {
          if (this.isConnecting) {
            this.isConnecting = false;
            this.ws?.close();
            reject(new Error('Connection timeout'));
          }
        }, 10000);

      } catch (error) {
        reject(error);
      }
    });
  }

  private attemptReconnection(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts || this.isDestroyed) {
      this.emit('reconnection_failed');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectDelay);

    this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });

    setTimeout(async () => {
      try {
        if (!this.isDestroyed && this.token && this.organizationId) {
          await this.createConnection();
          this.startHeartbeat();
        }
      } catch (error) {
        // Continue attempting reconnection
        this.attemptReconnection();
      }
    }, delay);
  }

  public disconnect(): void {
    this.isDestroyed = true;
    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  // ============================================================================
  // HEARTBEAT MANAGEMENT
  // ============================================================================

  private startHeartbeat(): void {
    this.stopHeartbeat();

    // Send ping every 30 seconds
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.sendMessage('ping', {});
        this.heartbeatTimeout = setTimeout(() => {
          this.emit('heartbeat_timeout');
          this.ws?.close();
        }, 5000); // Expect pong within 5 seconds
      }
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.heartbeatTimeout) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }

  // ============================================================================
  // MESSAGE HANDLING
  // ============================================================================

  private handleMessage(data: string): void {
    try {
      const message: MonitoringWebSocketMessage = JSON.parse(data);

      // Handle pong response
      if (message.type === 'pong') {
        if (this.heartbeatTimeout) {
          clearTimeout(this.heartbeatTimeout);
          this.heartbeatTimeout = null;
        }
        return;
      }

      // Process monitoring-specific messages
      this.processMonitoringMessage(message);
      this.emit('message', message);

    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
      this.emit('error', new Error('Invalid message format'));
    }
  }

  private processMonitoringMessage(message: MonitoringWebSocketMessage): void {
    const store = useMonitoringStore.getState();
    const realTimeUpdate: RealTimeUpdate = {
      type: this.convertMessageTypeToUpdateType(message.type),
      timestamp: message.timestamp,
      data: message.payload,
      source: 'monitoring_websocket',
      version: 1
    };

    // Add to real-time updates
    store.addRealTimeUpdate(realTimeUpdate);

    // Update specific store sections based on message type
    switch (message.type) {
      case 'system_health_update':
        store.updateSystemHealth((message.payload as SystemHealthUpdatePayload).health);
        break;

      case 'performance_metrics_update':
        store.updatePerformanceMetrics((message.payload as PerformanceMetricsUpdatePayload).metrics);
        break;

      case 'business_metrics_update':
        store.updateBusinessMetrics((message.payload as BusinessMetricsUpdatePayload).metrics);
        break;

      case 'infrastructure_update':
        store.updateInfrastructureMetrics((message.payload as InfrastructureUpdatePayload).metrics);
        break;

      case 'alert_triggered':
        const newAlert = (message.payload as AlertTriggeredPayload).alert;
        store.updateActiveAlerts([...store.activeAlerts, newAlert]);
        this.emitAlertNotification(newAlert, 'triggered');
        break;

      case 'alert_resolved':
        const resolvedPayload = message.payload as AlertResolvedPayload;
        store.resolveAlert(resolvedPayload.alert_id, resolvedPayload.resolved_by);
        break;

      case 'alert_updated':
        const updatedAlert = (message.payload as AlertUpdatedPayload).alert;
        store.updateActiveAlerts(
          store.activeAlerts.map(alert => alert.id === updatedAlert.id ? updatedAlert : alert)
        );
        break;

      case 'user_analytics_update':
        store.updateUserAnalytics((message.payload as UserAnalyticsUpdatePayload).analytics);
        break;

      case 'connection_status':
        const statusPayload = message.payload as ConnectionStatusPayload;
        store.setRealTimeConnection(statusPayload.status === 'connected');
        break;

      case 'error':
        const errorPayload = message.payload as ErrorPayload;
        this.emit('error', new Error(errorPayload.error.message));
        store.showNotification(errorPayload.error.message, 'error');
        break;

      default:
        console.warn('Unknown monitoring message type:', message.type);
    }
  }

  private convertMessageTypeToUpdateType(messageType: MonitoringMessageType): RealTimeUpdate['type'] {
    const typeMap: Record<MonitoringMessageType, RealTimeUpdate['type']> = {
      'system_health_update': 'system_status_change',
      'performance_metrics_update': 'metric_update',
      'business_metrics_update': 'metric_update',
      'infrastructure_update': 'metric_update',
      'alert_triggered': 'alert_triggered',
      'alert_resolved': 'alert_resolved',
      'alert_updated': 'alert_triggered',
      'user_analytics_update': 'user_activity',
      'connection_status': 'system_status_change',
      'error': 'error_increase',
      'ping': 'metric_update',
      'pong': 'metric_update'
    };

    return typeMap[messageType] || 'metric_update';
  }

  private emitAlertNotification(alert: Alert, action: 'triggered' | 'resolved'): void {
    const store = useMonitoringStore.getState();
    const message = action === 'triggered'
      ? `New ${alert.severity} alert: ${alert.name}`
      : `Alert resolved: ${alert.name}`;

    store.showNotification(message, action === 'triggered' ? 'warning' : 'success');

    // Also emit a custom event for alert-specific handling
    this.emit('alert_notification', { alert, action });
  }

  // ============================================================================
  // MESSAGE SENDING
  // ============================================================================

  public sendMessage(type: string, payload: any): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot send message');
      return;
    }

    const message: MonitoringWebSocketMessage = {
      type: type as MonitoringMessageType,
      payload,
      timestamp: new Date().toISOString(),
      id: this.generateMessageId()
    };

    this.ws.send(JSON.stringify(message));
  }

  private generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // ============================================================================
  // UTILITY METHODS
  // ============================================================================

  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  public getConnectionStatus(): 'connecting' | 'connected' | 'disconnected' | 'reconnecting' {
    if (this.isConnecting) return 'connecting';
    if (this.isConnected()) return 'connected';
    if (this.reconnectAttempts > 0) return 'reconnecting';
    return 'disconnected';
  }

  public updateConnectionParams(token: string, organizationId: string): void {
    this.token = token;
    this.organizationId = organizationId;

    // Reconnect with new parameters if currently connected
    if (this.isConnected()) {
      this.disconnect();
      setTimeout(() => {
        if (!this.isDestroyed) {
          this.connect(token, organizationId);
        }
      }, 1000);
    }
  }

  // ============================================================================
  // SUBSCRIPTION MANAGEMENT
  // ============================================================================

  public subscribeToMetrics(metrics: string[]): void {
    this.sendMessage('subscribe_metrics', { metrics });
  }

  public unsubscribeFromMetrics(metrics: string[]): void {
    this.sendMessage('unsubscribe_metrics', { metrics });
  }

  public subscribeToAlerts(severity?: string[]): void {
    this.sendMessage('subscribe_alerts', { severity });
  }

  public unsubscribeFromAlerts(): void {
    this.sendMessage('unsubscribe_alerts', {});
  }

  public subscribeToSystemHealth(): void {
    this.sendMessage('subscribe_system_health', {});
  }

  public unsubscribeFromSystemHealth(): void {
    this.sendMessage('unsubscribe_system_health', {});
  }

  public subscribeToUserAnalytics(): void {
    this.sendMessage('subscribe_user_analytics', {});
  }

  public unsubscribeFromUserAnalytics(): void {
    this.sendMessage('unsubscribe_user_analytics', {});
  }

  // ============================================================================
  // STATISTICS
  // ============================================================================

  public getStats() {
    return {
      connectionStatus: this.getConnectionStatus(),
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.maxReconnectAttempts,
      currentReconnectDelay: this.reconnectDelay,
      isHeartbeatActive: !!this.heartbeatInterval
    };
  }
}

// ============================================================================
// MONITORING WEBSOCKET MANAGER
// ============================================================================

class MonitoringWebSocketManager {
  private client: MonitoringWebSocketClient | null = null;
  private instance: MonitoringWebSocketManager | null = null;

  private constructor() {}

  public static getInstance(): MonitoringWebSocketManager {
    if (!this.instance) {
      this.instance = new MonitoringWebSocketManager() as any;
    }
    return this.instance as MonitoringWebSocketManager;
  }

  public initialize(url: string): MonitoringWebSocketClient {
    if (this.client) {
      this.client.disconnect();
    }

    this.client = new MonitoringWebSocketClient(url);
    return this.client;
  }

  public getClient(): MonitoringWebSocketClient | null {
    return this.client;
  }

  public destroy(): void {
    if (this.client) {
      this.client.disconnect();
      this.client = null;
    }
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export const monitoringWebSocketManager = MonitoringWebSocketManager.getInstance();

export const createMonitoringWebSocketClient = (url: string): MonitoringWebSocketClient => {
  return monitoringWebSocketManager.initialize(url);
};

export const getMonitoringWebSocketClient = (): MonitoringWebSocketClient | null => {
  return monitoringWebSocketManager.getClient();
};

export const destroyMonitoringWebSocketClient = (): void => {
  monitoringWebSocketManager.destroy();
};

// Hook for React components
export const useMonitoringWebSocket = () => {
  const client = getMonitoringWebSocketClient();

  return {
    client,
    isConnected: client?.isConnected() ?? false,
    status: client?.getConnectionStatus() ?? 'disconnected',
    stats: client?.getStats() ?? null,
    subscribeToMetrics: client?.subscribeToMetrics.bind(client),
    unsubscribeFromMetrics: client?.unsubscribeFromMetrics.bind(client),
    subscribeToAlerts: client?.subscribeToAlerts.bind(client),
    unsubscribeFromAlerts: client?.unsubscribeFromAlerts.bind(client),
    subscribeToSystemHealth: client?.subscribeToSystemHealth.bind(client),
    unsubscribeFromSystemHealth: client?.unsubscribeFromSystemHealth.bind(client),
    subscribeToUserAnalytics: client?.subscribeToUserAnalytics.bind(client),
    unsubscribeFromUserAnalytics: client?.unsubscribeFromUserAnalytics.bind(client),
  };
};

export default MonitoringWebSocketClient;