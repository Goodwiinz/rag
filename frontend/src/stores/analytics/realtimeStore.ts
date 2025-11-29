import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { AnalyticsMetric, TimeSeriesData } from './analyticsStore';

interface RealtimeState {
  // Connection
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';
  lastConnected?: string;
  reconnectAttempts: number;
  maxReconnectAttempts: number;

  // Subscriptions
  subscriptions: Record<string, {
    metricIds: string[];
    active: boolean;
    lastUpdate: string;
  }>;

  // Live Data
  liveMetrics: Record<string, AnalyticsMetric>;
  liveTimeSeries: Record<string, TimeSeriesData[]>;
  buffer: {
    metrics: AnalyticsMetric[];
    timeSeries: TimeSeriesData[];
    maxSize: number;
  };

  // Performance
  updateFrequency: number;
  lastUpdate: string;
  updateCount: number;
  errorCount: number;

  // Settings
  autoReconnect: boolean;
  bufferSize: number;
  compressionEnabled: boolean;
}

interface RealtimeActions {
  // Connection Management
  connect: () => void;
  disconnect: () => void;
  reconnect: () => void;
  setConnectionStatus: (status: RealtimeState['connectionStatus']) => void;
  incrementReconnectAttempts: () => void;
  resetReconnectAttempts: () => void;

  // Subscription Management
  subscribe: (subscriptionId: string, metricIds: string[]) => void;
  unsubscribe: (subscriptionId: string) => void;
  updateSubscription: (subscriptionId: string, metricIds: string[]) => void;
  toggleSubscription: (subscriptionId: string) => void;
  clearSubscriptions: () => void;

  // Data Management
  updateLiveMetric: (metricId: string, metric: AnalyticsMetric) => void;
  addTimeSeriesData: (metricId: string, data: TimeSeriesData) => void;
  processBuffer: () => void;
  clearBuffer: () => void;
  clearLiveData: () => void;

  // Performance Monitoring
  incrementUpdateCount: () => void;
  incrementErrorCount: () => void;
  setUpdateFrequency: (frequency: number) => void;
  updateLastUpdateTime: () => void;

  // Settings
  toggleAutoReconnect: () => void;
  setBufferSize: (size: number) => void;
  toggleCompression: () => void;

  // Data Processing
  processIncomingData: (data: any) => void;
  handleMetricUpdate: (metric: AnalyticsMetric) => void;
  handleTimeSeriesUpdate: (metricId: string, data: TimeSeriesData) => void;
  handleConnectionEvent: (event: 'connect' | 'disconnect' | 'error') => void;

  // Statistics
  getConnectionStats: () => {
    uptime: number;
    totalUpdates: number;
    errorRate: number;
    averageUpdateFrequency: number;
  };
}

export const useRealtimeStore = create<RealtimeState & RealtimeActions>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      // Initial State
      isConnected: false,
      connectionStatus: 'disconnected',
      reconnectAttempts: 0,
      maxReconnectAttempts: 5,
      subscriptions: {},
      liveMetrics: {},
      liveTimeSeries: {},
      buffer: {
        metrics: [],
        timeSeries: [],
        maxSize: 1000,
      },
      updateFrequency: 1000, // 1 second
      lastUpdate: new Date().toISOString(),
      updateCount: 0,
      errorCount: 0,
      autoReconnect: true,
      bufferSize: 1000,
      compressionEnabled: true,

      // Connection Management
      connect: () => {
        const { setConnectionStatus } = get();
        setConnectionStatus('connecting');

        // WebSocket connection logic would go here
        console.log('Connecting to real-time analytics service...');

        // Simulate connection success
        setTimeout(() => {
          setConnectionStatus('connected');
          set({
            isConnected: true,
            lastConnected: new Date().toISOString(),
            reconnectAttempts: 0
          }, false, 'connect');
        }, 1000);
      },

      disconnect: () => {
        const { clearSubscriptions, clearLiveData } = get();
        setConnectionStatus('disconnected');
        set({ isConnected: false }, false, 'disconnect');
        clearSubscriptions();
        clearLiveData();
      },

      reconnect: () => {
        const { reconnectAttempts, maxReconnectAttempts, disconnect, connect } = get();

        if (reconnectAttempts >= maxReconnectAttempts) {
          disconnect();
          return;
        }

        setConnectionStatus('reconnecting');
        set({ reconnectAttempts: reconnectAttempts + 1 }, false, 'incrementReconnectAttempts');

        // Exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);

        setTimeout(() => {
          connect();
        }, delay);
      },

      setConnectionStatus: (status) => set({ connectionStatus: status }, false, 'setConnectionStatus'),
      incrementReconnectAttempts: () =>
        set(
          (state) => ({ reconnectAttempts: state.reconnectAttempts + 1 }),
          false,
          'incrementReconnectAttempts'
        ),
      resetReconnectAttempts: () => set({ reconnectAttempts: 0 }, false, 'resetReconnectAttempts'),

      // Subscription Management
      subscribe: (subscriptionId, metricIds) =>
        set(
          (state) => ({
            subscriptions: {
              ...state.subscriptions,
              [subscriptionId]: {
                metricIds,
                active: true,
                lastUpdate: new Date().toISOString(),
              },
            },
          }),
          false,
          'subscribe'
        ),

      unsubscribe: (subscriptionId) =>
        set(
          (state) => {
            const newSubscriptions = { ...state.subscriptions };
            delete newSubscriptions[subscriptionId];
            return { subscriptions: newSubscriptions };
          },
          false,
          'unsubscribe'
        ),

      updateSubscription: (subscriptionId, metricIds) =>
        set(
          (state) => ({
            subscriptions: {
              ...state.subscriptions,
              [subscriptionId]: {
                ...state.subscriptions[subscriptionId],
                metricIds,
                lastUpdate: new Date().toISOString(),
              },
            },
          }),
          false,
          'updateSubscription'
        ),

      toggleSubscription: (subscriptionId) =>
        set(
          (state) => ({
            subscriptions: {
              ...state.subscriptions,
              [subscriptionId]: {
                ...state.subscriptions[subscriptionId],
                active: !state.subscriptions[subscriptionId]?.active,
              },
            },
          }),
          false,
          'toggleSubscription'
        ),

      clearSubscriptions: () => set({ subscriptions: {} }, false, 'clearSubscriptions'),

      // Data Management
      updateLiveMetric: (metricId, metric) =>
        set(
          (state) => ({
            liveMetrics: { ...state.liveMetrics, [metricId]: metric },
            lastUpdate: new Date().toISOString(),
          }),
          false,
          'updateLiveMetric'
        ),

      addTimeSeriesData: (metricId, data) =>
        set(
          (state) => {
            const existingData = state.liveTimeSeries[metricId] || [];
            const updatedData = [...existingData, data];

            // Keep only last 1000 points per metric
            if (updatedData.length > 1000) {
              updatedData.splice(0, updatedData.length - 1000);
            }

            return {
              liveTimeSeries: { ...state.liveTimeSeries, [metricId]: updatedData },
              lastUpdate: new Date().toISOString(),
            };
          },
          false,
          'addTimeSeriesData'
        ),

      processBuffer: () =>
        set(
          (state) => {
            const { metrics, timeSeries, maxSize } = state.buffer;

            // Process metrics
            metrics.forEach((metric) => {
              // Add to live metrics
            });

            // Process time series data
            timeSeries.forEach((data) => {
              // Add to live time series
            });

            // Clear buffer
            return {
              buffer: { ...state.buffer, metrics: [], timeSeries: [] },
            };
          },
          false,
          'processBuffer'
        ),

      clearBuffer: () =>
        set(
          (state) => ({
            buffer: { ...state.buffer, metrics: [], timeSeries: [] },
          }),
          false,
          'clearBuffer'
        ),

      clearLiveData: () =>
        set(
          {
            liveMetrics: {},
            liveTimeSeries: {},
          },
          false,
          'clearLiveData'
        ),

      // Performance Monitoring
      incrementUpdateCount: () =>
        set(
          (state) => ({ updateCount: state.updateCount + 1 }),
          false,
          'incrementUpdateCount'
        ),

      incrementErrorCount: () =>
        set(
          (state) => ({ errorCount: state.errorCount + 1 }),
          false,
          'incrementErrorCount'
        ),

      setUpdateFrequency: (frequency) => set({ updateFrequency: frequency }, false, 'setUpdateFrequency'),
      updateLastUpdateTime: () => set({ lastUpdate: new Date().toISOString() }, false, 'updateLastUpdateTime'),

      // Settings
      toggleAutoReconnect: () =>
        set(
          (state) => ({ autoReconnect: !state.autoReconnect }),
          false,
          'toggleAutoReconnect'
        ),

      setBufferSize: (size) =>
        set(
          (state) => ({
            bufferSize: size,
            buffer: { ...state.buffer, maxSize: size },
          }),
          false,
          'setBufferSize'
        ),

      toggleCompression: () =>
        set(
          (state) => ({ compressionEnabled: !state.compressionEnabled }),
          false,
          'toggleCompression'
        ),

      // Data Processing
      processIncomingData: (data) => {
        const { handleMetricUpdate, handleTimeSeriesUpdate, handleConnectionEvent } = get();

        switch (data.type) {
          case 'metric_update':
            handleMetricUpdate(data.payload);
            break;
          case 'time_series_update':
            handleTimeSeriesUpdate(data.payload.metricId, data.payload.data);
            break;
          case 'connection_event':
            handleConnectionEvent(data.payload.event);
            break;
          default:
            console.warn('Unknown data type:', data.type);
        }
      },

      handleMetricUpdate: (metric) => {
        const { updateLiveMetric, incrementUpdateCount } = get();
        updateLiveMetric(metric.id, metric);
        incrementUpdateCount();
      },

      handleTimeSeriesUpdate: (metricId, data) => {
        const { addTimeSeriesData, incrementUpdateCount } = get();
        addTimeSeriesData(metricId, data);
        incrementUpdateCount();
      },

      handleConnectionEvent: (event) => {
        const { setConnectionStatus, reconnect, disconnect } = get();

        switch (event) {
          case 'connect':
            setConnectionStatus('connected');
            break;
          case 'disconnect':
            setConnectionStatus('disconnected');
            break;
          case 'error':
            setConnectionStatus('error');
            if (get().autoReconnect) {
              reconnect();
            } else {
              disconnect();
            }
            break;
        }
      },

      // Statistics
      getConnectionStats: () => {
        const { lastConnected, updateCount, errorCount, updateFrequency } = get();

        const uptime = lastConnected ? Date.now() - new Date(lastConnected).getTime() : 0;
        const errorRate = updateCount > 0 ? (errorCount / updateCount) * 100 : 0;

        return {
          uptime,
          totalUpdates: updateCount,
          errorRate,
          averageUpdateFrequency: updateFrequency,
        };
      },
    })),
    {
      name: 'realtime-store',
    }
  )
);