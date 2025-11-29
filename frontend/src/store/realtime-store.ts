/**
 * Real-time Document Processing Zustand Store
 * Manages WebSocket connections, document processing state, and real-time updates
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import {
  RealtimeStore,
  WebSocketConnectionState,
  DocumentProcessingState,
  WebSocketMessage,
  DocumentUpdateMessage,
  QueueUpdateMessage,
  SystemMetricsMessage,
  NotificationMessage,
  ConnectionStatusMessage,
  Channel,
  UpdateFrequency,
  MessagePriority,
  RealtimeProcessingState,
  WebSocketClientConfig
} from '../types/realtime-processing';

// WebSocket Service
import { RealtimeWebSocketService } from '../services/realtime-websocket-service';

// Initial state
const initialState: Omit<RealtimeStore, 'actions'> = {
  connection: {
    status: 'disconnected',
    reconnectionAttempts: 0,
    maxReconnectionAttempts: 5,
    reconnectInterval: 5000,
    latency: 0
  },
  connectionInfo: null,
  documents: new Map(),
  subscribedDocuments: new Set(),
  systemMetrics: {
    concurrentConnections: 0,
    memoryUsage: 0,
    cpuUsage: 0,
    diskSpace: 0,
    activeJobs: 0,
    queuedJobs: 0,
    completedJobs: 0,
    averageJobDuration: 0
  },
  config: {
    updateFrequency: UpdateFrequency.NORMAL,
    subscribedChannels: new Set([Channel.DOCUMENT_PROCESSING, Channel.USER_NOTIFICATIONS]),
    messageFilter: {},
    autoReconnect: true,
    reconnectDelay: 5000,
    maxReconnectAttempts: 5
  }
};

// Create the Zustand store
export const useRealtimeStore = create<RealtimeStore>()(
  devtools(
    subscribeWithSelector(
      immer((set, get) => ({
        ...initialState,

        // WebSocket Connection Actions
        connect: async (token, options = {}) => {
          const { channels = [], frequency, clientInfo } = options;
          const state = get();

          try {
            // Update connection status to connecting
            set((draft) => {
              draft.connection.status = 'connecting';
              draft.connection.lastError = undefined;
            });

            // Create WebSocket configuration
            const wsConfig: WebSocketClientConfig = {
              url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/api/v2/ws/connect`,
              token,
              channels: channels.length > 0 ? channels : Array.from(state.config.subscribedChannels),
              frequency: frequency || state.config.updateFrequency,
              clientInfo: {
                ...clientInfo,
                timestamp: new Date().toISOString(),
                userAgent: typeof window !== 'undefined' ? window.navigator.userAgent : 'unknown',
                url: typeof window !== 'undefined' ? window.location.href : 'unknown'
              },
              autoReconnect: state.config.autoReconnect,
              reconnectDelay: state.config.reconnectDelay,
              maxReconnectAttempts: state.config.maxReconnectAttempts,
              heartbeatInterval: 30000,
              enableBatching: true,
              batchSize: 100,
              batchTimeout: 100
            };

            // Initialize and connect WebSocket service
            await RealtimeWebSocketService.initialize(wsConfig, {
              onConnect: (connectionInfo) => {
                set((draft) => {
                  draft.connection.status = 'connected';
                  draft.connection.lastConnectedAt = new Date().toISOString();
                  draft.connection.reconnectionAttempts = 0;
                  draft.connectionInfo = connectionInfo;
                });
              },
              onDisconnect: (reason) => {
                set((draft) => {
                  draft.connection.status = 'disconnected';
                  draft.connectionInfo = null;
                });
              },
              onError: (error) => {
                set((draft) => {
                  draft.connection.status = 'error';
                  draft.connection.lastError = error.message;
                });
              },
              onReconnect: () => {
                set((draft) => {
                  draft.connection.status = 'reconnecting';
                  draft.connection.reconnectionAttempts++;
                });
              },
              onMessage: (message: WebSocketMessage) => {
                handleWebSocketMessage(message, set, get);
              }
            });

          } catch (error) {
            set((draft) => {
              draft.connection.status = 'error';
              draft.connection.lastError = error instanceof Error ? error.message : 'Connection failed';
            });
            throw error;
          }
        },

        disconnect: () => {
          try {
            RealtimeWebSocketService.disconnect();
            set((draft) => {
              draft.connection.status = 'disconnected';
              draft.connectionInfo = null;
              draft.subscribedDocuments.clear();
            });
          } catch (error) {
            console.error('Error disconnecting WebSocket:', error);
          }
        },

        reconnect: () => {
          const { connection } = get();
          if (connection.status === 'disconnected' || connection.status === 'error') {
            // Trigger reconnection
            RealtimeWebSocketService.reconnect();
          }
        },

        // Channel Management
        subscribeToChannel: (channel: Channel) => {
          try {
            RealtimeWebSocketService.subscribeToChannel(channel);
            set((draft) => {
              draft.config.subscribedChannels.add(channel);
            });
          } catch (error) {
            console.error('Error subscribing to channel:', error);
          }
        },

        unsubscribeFromChannel: (channel: Channel) => {
          try {
            RealtimeWebSocketService.unsubscribeFromChannel(channel);
            set((draft) => {
              draft.config.subscribedChannels.delete(channel);
            });
          } catch (error) {
            console.error('Error unsubscribing from channel:', error);
          }
        },

        // Document Subscription Management
        subscribeToDocument: (documentId: string) => {
          set((draft) => {
            draft.subscribedDocuments.add(documentId);
          });

          // Send subscription message to server
          get().sendWebSocketMessage({
            type: 'subscribe',
            payload: {
              documentId,
              channels: [Channel.DOCUMENT_PROCESSING]
            }
          });
        },

        unsubscribeFromDocument: (documentId: string) => {
          set((draft) => {
            draft.subscribedDocuments.delete(documentId);
          });

          // Send unsubscription message to server
          get().sendWebSocketMessage({
            type: 'unsubscribe',
            payload: {
              documentId,
              channels: [Channel.DOCUMENT_PROCESSING]
            }
          });
        },

        // Document Status Updates
        updateDocumentStatus: (update: DocumentUpdateMessage) => {
          const { documentId } = update;

          set((draft) => {
            const existingDoc = draft.documents.get(documentId);

            if (existingDoc) {
              // Update existing document
              const updatedDoc = {
                ...existingDoc,
                overallProgress: update.payload.progress ?? existingDoc.overallProgress,
                currentStage: update.payload.currentStage ?? existingDoc.currentStage,
                status: update.payload.status ?? existingDoc.status,
                error: update.payload.error ?? existingDoc.error,
                metadata: {
                  ...existingDoc.metadata,
                  ...update.payload,
                  lastUpdate: new Date().toISOString()
                }
              };
              draft.documents.set(documentId, updatedDoc);
            } else {
              // Create new document entry if it doesn't exist
              const newDoc: DocumentProcessingState = {
                id: documentId,
                filename: update.payload.filename || 'Unknown',
                fileType: 'pdf', // Default, should be updated from payload
                overallProgress: update.payload.progress || 0,
                currentStage: update.payload.currentStage || {
                  id: 'unknown',
                  name: 'Unknown Stage',
                  description: '',
                  progress: 0,
                  status: 'pending'
                },
                stages: [],
                status: update.payload.status || 'processing',
                uploadProgress: 100,
                metadata: {
                  fileSize: 0,
                  uploadStartedAt: new Date().toISOString(),
                  processingStartedAt: new Date().toISOString(),
                  ...update.payload
                },
                retryCount: 0,
                canRetry: false,
                actions: {
                  pause: true,
                  resume: false,
                  cancel: true,
                  retry: false,
                  download: false
                }
              };
              draft.documents.set(documentId, newDoc);
            }
          });
        },

        // WebSocket Message Sending
        sendWebSocketMessage: (message: WebSocketMessage | { type: string; payload: Record<string, unknown> }) => {
          try {
            RealtimeWebSocketService.sendMessage(message);
          } catch (error) {
            console.error('Error sending WebSocket message:', error);
          }
        },

        // Utility Actions
        clearNotifications: () => {
          set((draft) => {
            // This would be implemented when we add notifications to the state
          });
        },

        updatePreferences: (preferences) => {
          // This would be implemented when we add preferences to the state
        },

        updateUI: (ui) => {
          // This would be implemented when we add UI state to the store
        }
      }))
    ),
    {
      name: 'realtime-store'
    }
  )
);

// WebSocket Message Handler
function handleWebSocketMessage(
  message: WebSocketMessage,
  set: (updater: (draft: RealtimeStore) => void) => void,
  get: () => RealtimeStore
) {
  const { type, payload } = message;

  switch (type) {
    case 'document_update':
      handleDocumentUpdate(payload as DocumentUpdateMessage['payload'], set);
      break;

    case 'queue_update':
      handleQueueUpdate(payload as QueueUpdateMessage['payload'], set);
      break;

    case 'system_metrics':
      handleSystemMetricsUpdate(payload as SystemMetricsMessage['payload'], set);
      break;

    case 'notification':
      handleNotification(payload as NotificationMessage['payload'], set);
      break;

    case 'connection_status':
      handleConnectionStatusUpdate(payload as ConnectionStatusMessage['payload'], set);
      break;

    case 'ping':
      // Respond with pong
      get().sendWebSocketMessage({ type: 'pong', payload: { timestamp: Date.now() } });
      break;

    case 'pong':
      // Update latency
      if (payload?.timestamp) {
        const latency = Date.now() - payload.timestamp;
        set((draft) => {
          draft.connection.latency = latency;
        });
      }
      break;

    default:
      console.log('Unhandled WebSocket message type:', type, payload);
  }
}

// Message Type Handlers
function handleDocumentUpdate(
  payload: DocumentUpdateMessage['payload'],
  set: (updater: (draft: RealtimeStore) => void) => void
) {
  set((draft) => {
    const { documentId, progress, currentStage, status, error } = payload;
    const existingDoc = draft.documents.get(documentId);

    if (existingDoc) {
      const updatedDoc = {
        ...existingDoc,
        overallProgress: progress ?? existingDoc.overallProgress,
        currentStage: currentStage ?? existingDoc.currentStage,
        status: status ?? existingDoc.status,
        error: error ?? existingDoc.error,
        metadata: {
          ...existingDoc.metadata,
          lastUpdate: new Date().toISOString()
        }
      };
      draft.documents.set(documentId, updatedDoc);
    }
  });
}

function handleQueueUpdate(
  payload: QueueUpdateMessage['payload'],
  set: (updater: (draft: RealtimeStore) => void) => void
) {
  set((draft) => {
    // Update system metrics from queue update
    if (payload.metrics) {
      draft.systemMetrics = {
        ...draft.systemMetrics,
        activeJobs: payload.metrics.throughput || 0,
        averageJobDuration: payload.metrics.averageProcessingTime || 0
      };
    }
  });
}

function handleSystemMetricsUpdate(
  payload: SystemMetricsMessage['payload'],
  set: (updater: (draft: RealtimeStore) => void) => void
) {
  set((draft) => {
    draft.systemMetrics = {
      ...draft.systemMetrics,
      ...payload
    };
  });
}

function handleNotification(
  payload: NotificationMessage['payload'],
  set: (updater: (draft: RealtimeStore) => void) => void
) {
  // This would handle notification updates
  // For now, just log the notification
  console.log('Notification received:', payload);
}

function handleConnectionStatusUpdate(
  payload: ConnectionStatusMessage['payload'],
  set: (updater: (draft: RealtimeStore) => void) => void
) {
  set((draft) => {
    if (payload.status === 'connected') {
      draft.connection.status = 'connected';
      draft.connection.lastError = undefined;
    } else if (payload.status === 'error') {
      draft.connection.status = 'error';
      draft.connection.lastError = payload.message;
    }
  });
}

// Selectors for optimized component re-renders
export const useConnectionStatus = () => useRealtimeStore((state) => state.connection);
export const useDocuments = () => useRealtimeStore((state) => Array.from(state.documents.values()));
export const useDocumentById = (id: string) => useRealtimeStore((state) => state.documents.get(id));
export const useSubscribedDocuments = () => useRealtimeStore((state) => Array.from(state.subscribedDocuments).map(id => state.documents.get(id)).filter(Boolean));
export const useSystemMetrics = () => useRealtimeStore((state) => state.systemMetrics);
export const useConfig = () => useRealtimeStore((state) => state.config);

// Actions hook
export const useRealtimeActions = () => useRealtimeStore((state) => ({
  connect: state.connect,
  disconnect: state.disconnect,
  reconnect: state.reconnect,
  subscribeToChannel: state.subscribeToChannel,
  unsubscribeFromChannel: state.unsubscribeFromChannel,
  subscribeToDocument: state.subscribeToDocument,
  unsubscribeFromDocument: state.unsubscribeFromDocument,
  updateDocumentStatus: state.updateDocumentStatus,
  sendWebSocketMessage: state.sendWebSocketMessage,
  clearNotifications: state.clearNotifications
}));

export default useRealtimeStore;