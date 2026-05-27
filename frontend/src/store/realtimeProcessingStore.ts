import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { subscribeWithSelector } from 'zustand/middleware';
import {
  RealtimeProcessingState,
  DocumentProcessingState,
  WebSocketConnectionState,
  NotificationItem,
  ProcessingStage,
} from '@/types/realtime-processing';

// Maximum number of documents in the processing queue
const MAX_QUEUE_DOCUMENTS = 100;
// Age threshold (ms) for trimming completed/failed documents
const QUEUE_TRIM_AGE_MS = 60 * 60 * 1000; // 1 hour

interface RealtimeProcessingActions {
  // Connection actions
  setConnectionStatus: (status: WebSocketConnectionState['status']) => void;
  updateConnectionState: (updates: Partial<WebSocketConnectionState>) => void;
  incrementReconnectionAttempts: () => void;
  resetConnectionState: () => void;

  // Queue actions
  addDocument: (document: DocumentProcessingState) => void;
  updateDocument: (
    documentId: string,
    updates: Partial<DocumentProcessingState>
  ) => void;
  removeDocument: (documentId: string) => void;
  updateDocuments: (
    documentUpdates: Array<{
      id: string;
      updates: Partial<DocumentProcessingState>;
    }>
  ) => void;
  setQueueSummary: (
    summary: RealtimeProcessingState['queue']['summary']
  ) => void;
  setQueueMetrics: (
    metrics: RealtimeProcessingState['queue']['metrics']
  ) => void;
  updateFilters: (
    filters: Partial<RealtimeProcessingState['queue']['filters']>
  ) => void;
  setPagination: (
    pagination: Partial<RealtimeProcessingState['queue']['pagination']>
  ) => void;

  // System metrics actions
  updateSystemMetrics: (
    metrics: Partial<RealtimeProcessingState['systemMetrics']>
  ) => void;

  // Notification actions
  addNotification: (notification: Omit<NotificationItem, 'id'>) => void;
  removeNotification: (notificationId: string) => void;
  clearNotifications: () => void;
  markNotificationAsRead: (notificationId: string) => void;

  // UI state actions
  toggleDocumentSelection: (documentId: string) => void;
  selectAllDocuments: () => void;
  clearDocumentSelection: () => void;
  toggleSidebar: () => void;
  setAutoScroll: (enabled: boolean) => void;
  setCompactView: (compact: boolean) => void;
  setTheme: (theme: RealtimeProcessingState['ui']['theme']) => void;

  // Preferences actions
  updatePreferences: (
    preferences: Partial<RealtimeProcessingState['preferences']>
  ) => void;

  // Bulk actions
  pauseSelectedDocuments: () => void;
  resumeSelectedDocuments: () => void;
  cancelSelectedDocuments: () => void;
  retrySelectedDocuments: () => void;

  // Computed values
  getSelectedDocuments: () => DocumentProcessingState[];
  getDocumentsByStatus: (
    status: DocumentProcessingState['status']
  ) => DocumentProcessingState[];
  getFilteredDocuments: () => DocumentProcessingState[];
  getUnreadNotificationsCount: () => number;
}

const initialState: RealtimeProcessingState = {
  connection: {
    status: 'disconnected',
    reconnectionAttempts: 0,
    maxReconnectionAttempts: 5,
    reconnectInterval: 2000,
    latency: 0,
  },
  queue: {
    documents: [],
    summary: {
      total: 0,
      queued: 0,
      uploading: 0,
      processing: 0,
      completed: 0,
      failed: 0,
      paused: 0,
      cancelled: 0,
    },
    metrics: {
      averageProcessingTime: 0,
      throughput: 0,
      successRate: 0,
      errorRate: 0,
    },
    filters: {
      fileTypes: [],
      statuses: [],
      searchTerm: '',
    },
    pagination: {
      page: 1,
      pageSize: 50,
      total: 0,
      hasMore: false,
    },
  },
  systemMetrics: {
    concurrentConnections: 0,
    memoryUsage: 0,
    cpuUsage: 0,
    diskSpace: 0,
    activeJobs: 0,
    queuedJobs: 0,
    completedJobs: 0,
    averageJobDuration: 0,
  },
  notifications: [],
  ui: {
    selectedDocuments: [],
    sidebarCollapsed: false,
    autoScrollEnabled: true,
    compactView: false,
    theme: 'auto',
  },
  preferences: {
    refreshInterval: 500,
    maxNotifications: 10,
    soundEnabled: true,
    desktopNotifications: true,
    autoRetryFailed: true,
    maxRetryAttempts: 3,
  },
};

export const useRealtimeProcessingStore = create<
  RealtimeProcessingState & RealtimeProcessingActions
>()(
  devtools(
    subscribeWithSelector(
      immer((set, get) => ({
        ...initialState,

        // Connection actions
        setConnectionStatus: (status) =>
          set((state) => {
            state.connection.status = status;
            if (status === 'connected') {
              state.connection.lastConnectedAt = new Date().toISOString();
              state.connection.reconnectionAttempts = 0;
              state.connection.lastError = undefined;
            }
          }),

        updateConnectionState: (updates) =>
          set((state) => {
            Object.assign(state.connection, updates);
          }),

        incrementReconnectionAttempts: () =>
          set((state) => {
            state.connection.reconnectionAttempts += 1;
          }),

        resetConnectionState: () =>
          set((state) => {
            state.connection = { ...initialState.connection };
          }),

        // Queue actions
        addDocument: (document) =>
          set((state) => {
            const existingIndex = state.queue.documents.findIndex(
              (d) => d.id === document.id
            );
            if (existingIndex >= 0) {
              state.queue.documents[existingIndex] = document;
            } else {
              state.queue.documents.unshift(document);
            }

            // Trim completed/failed documents older than 1 hour when queue exceeds cap
            if (state.queue.documents.length > MAX_QUEUE_DOCUMENTS) {
              const now = Date.now();
              state.queue.documents = state.queue.documents.filter((doc) => {
                if (doc.status !== 'completed' && doc.status !== 'failed')
                  return true;
                const completedAt = doc.metadata.completedAt
                  ? new Date(doc.metadata.completedAt).getTime()
                  : new Date(doc.metadata.uploadStartedAt).getTime();
                return now - completedAt < QUEUE_TRIM_AGE_MS;
              });
              // Remove from selection any evicted document ids
              const remainingIds = new Set(
                state.queue.documents.map((d) => d.id)
              );
              state.ui.selectedDocuments = state.ui.selectedDocuments.filter(
                (id) => remainingIds.has(id)
              );
            }

            state.queue.summary.total = state.queue.documents.length;
            state.queue.summary[document.status] =
              (state.queue.summary[document.status] || 0) + 1;
          }),

        updateDocument: (documentId, updates) =>
          set((state) => {
            const documentIndex = state.queue.documents.findIndex(
              (d) => d.id === documentId
            );
            if (documentIndex >= 0) {
              const document = state.queue.documents[documentIndex];
              const oldStatus = document.status;

              // Update summary counts
              if (updates.status && updates.status !== oldStatus) {
                state.queue.summary[oldStatus]--;
                state.queue.summary[updates.status]++;
              }

              Object.assign(document, updates);
            }
          }),

        removeDocument: (documentId) =>
          set((state) => {
            const documentIndex = state.queue.documents.findIndex(
              (d) => d.id === documentId
            );
            if (documentIndex >= 0) {
              const document = state.queue.documents[documentIndex];
              state.queue.summary[document.status]--;
              state.queue.documents.splice(documentIndex, 1);
              state.queue.summary.total = state.queue.documents.length;

              // Remove from selected documents if present
              state.ui.selectedDocuments = state.ui.selectedDocuments.filter(
                (id) => id !== documentId
              );
            }
          }),

        updateDocuments: (documentUpdates) =>
          set((state) => {
            documentUpdates.forEach(({ id, updates }) => {
              const documentIndex = state.queue.documents.findIndex(
                (d) => d.id === id
              );
              if (documentIndex >= 0) {
                const document = state.queue.documents[documentIndex];
                const oldStatus = document.status;

                if (updates.status && updates.status !== oldStatus) {
                  state.queue.summary[oldStatus]--;
                  state.queue.summary[updates.status]++;
                }

                Object.assign(document, updates);
              }
            });
          }),

        setQueueSummary: (summary) =>
          set((state) => {
            state.queue.summary = summary;
          }),

        setQueueMetrics: (metrics) =>
          set((state) => {
            state.queue.metrics = metrics;
          }),

        updateFilters: (filters) =>
          set((state) => {
            Object.assign(state.queue.filters, filters);
            // Reset to first page when filters change
            state.queue.pagination.page = 1;
          }),

        setPagination: (pagination) =>
          set((state) => {
            Object.assign(state.queue.pagination, pagination);
          }),

        // System metrics actions
        updateSystemMetrics: (metrics) =>
          set((state) => {
            Object.assign(state.systemMetrics, metrics);
          }),

        // Notification actions
        addNotification: (notification) =>
          set((state) => {
            const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            const newNotification = { ...notification, id };

            state.notifications.unshift(newNotification);

            // Limit number of notifications
            if (
              state.notifications.length > state.preferences.maxNotifications
            ) {
              state.notifications = state.notifications.slice(
                0,
                state.preferences.maxNotifications
              );
            }
          }),

        removeNotification: (notificationId) =>
          set((state) => {
            state.notifications = state.notifications.filter(
              (n) => n.id !== notificationId
            );
          }),

        clearNotifications: () =>
          set((state) => {
            state.notifications = [];
          }),

        markNotificationAsRead: (notificationId) =>
          set((state) => {
            const notification = state.notifications.find(
              (n) => n.id === notificationId
            );
            if (notification && !notification.autoHide) {
              // Add read status if needed
            }
          }),

        // UI state actions
        toggleDocumentSelection: (documentId) =>
          set((state) => {
            const index = state.ui.selectedDocuments.indexOf(documentId);
            if (index >= 0) {
              state.ui.selectedDocuments.splice(index, 1);
            } else {
              state.ui.selectedDocuments.push(documentId);
            }
          }),

        selectAllDocuments: () =>
          set((state) => {
            state.ui.selectedDocuments = state.queue.documents.map((d) => d.id);
          }),

        clearDocumentSelection: () =>
          set((state) => {
            state.ui.selectedDocuments = [];
          }),

        toggleSidebar: () =>
          set((state) => {
            state.ui.sidebarCollapsed = !state.ui.sidebarCollapsed;
          }),

        setAutoScroll: (enabled) =>
          set((state) => {
            state.ui.autoScrollEnabled = enabled;
          }),

        setCompactView: (compact) =>
          set((state) => {
            state.ui.compactView = compact;
          }),

        setTheme: (theme) =>
          set((state) => {
            state.ui.theme = theme;
          }),

        // Preferences actions
        updatePreferences: (preferences) =>
          set((state) => {
            Object.assign(state.preferences, preferences);
          }),

        // Bulk actions
        pauseSelectedDocuments: () => {
          const state = get();
          state.getSelectedDocuments().forEach((doc) => {
            if (doc.actions.pause) {
              get().updateDocument(doc.id, { status: 'paused' });
            }
          });
        },

        resumeSelectedDocuments: () => {
          const state = get();
          state.getSelectedDocuments().forEach((doc) => {
            if (doc.status === 'paused' && doc.actions.resume) {
              get().updateDocument(doc.id, { status: 'processing' });
            }
          });
        },

        cancelSelectedDocuments: () => {
          const state = get();
          state.getSelectedDocuments().forEach((doc) => {
            if (doc.actions.cancel) {
              get().updateDocument(doc.id, { status: 'cancelled' });
            }
          });
        },

        retrySelectedDocuments: () => {
          const state = get();
          state.getSelectedDocuments().forEach((doc) => {
            if (doc.status === 'failed' && doc.actions.retry) {
              get().updateDocument(doc.id, {
                status: 'processing',
                error: undefined,
                retryCount: doc.retryCount + 1,
              });
            }
          });
        },

        // Computed values
        getSelectedDocuments: () => {
          const state = get();
          return state.queue.documents.filter((doc) =>
            state.ui.selectedDocuments.includes(doc.id)
          );
        },

        getDocumentsByStatus: (status) => {
          const state = get();
          return state.queue.documents.filter((doc) => doc.status === status);
        },

        getFilteredDocuments: () => {
          const state = get();
          let filtered = state.queue.documents;

          // Apply filters
          if (state.queue.filters.fileTypes.length > 0) {
            filtered = filtered.filter((doc) =>
              state.queue.filters.fileTypes.includes(doc.fileType)
            );
          }

          if (state.queue.filters.statuses.length > 0) {
            filtered = filtered.filter((doc) =>
              state.queue.filters.statuses.includes(doc.status)
            );
          }

          if (state.queue.filters.searchTerm) {
            const searchTerm = state.queue.filters.searchTerm.toLowerCase();
            filtered = filtered.filter((doc) =>
              doc.filename.toLowerCase().includes(searchTerm)
            );
          }

          if (state.queue.filters.dateRange) {
            const { start, end } = state.queue.filters.dateRange;
            filtered = filtered.filter((doc) => {
              const uploadTime = new Date(doc.metadata.uploadStartedAt);
              return (
                uploadTime >= new Date(start) && uploadTime <= new Date(end)
              );
            });
          }

          // Apply pagination
          const { page, pageSize } = state.queue.pagination;
          const startIndex = (page - 1) * pageSize;
          const endIndex = startIndex + pageSize;

          return filtered.slice(startIndex, endIndex);
        },

        getUnreadNotificationsCount: () => {
          const state = get();
          return state.notifications.filter((n) => !n.autoHide).length;
        },
      }))
    ),
    {
      name: 'realtime-processing-store',
    }
  )
);

// Selectors for optimized re-renders
export const useConnectionStatus = () =>
  useRealtimeProcessingStore((state) => state.connection);
export const useProcessingQueue = () =>
  useRealtimeProcessingStore((state) => state.queue);
export const useSystemMetrics = () =>
  useRealtimeProcessingStore((state) => state.systemMetrics);
export const useNotifications = () =>
  useRealtimeProcessingStore((state) => state.notifications);
export const useUIState = () => useRealtimeProcessingStore((state) => state.ui);
export const usePreferences = () =>
  useRealtimeProcessingStore((state) => state.preferences);
export const useSelectedDocuments = () =>
  useRealtimeProcessingStore((state) => state.getSelectedDocuments());
export const useFilteredDocuments = () =>
  useRealtimeProcessingStore((state) => state.getFilteredDocuments());
