// File upload constraints
export const UPLOAD_LIMITS = {
  MAX_FILE_SIZE_MB: 50,
  MAX_FILES_PER_UPLOAD: 10,
  SUPPORTED_FORMATS: ['pdf', 'txt', 'jpg', 'jpeg', 'png', 'mp3', 'mp4'],
  CHUNK_SIZE_BYTES: 1024 * 1024, // 1MB chunks for large files
} as const;

// UI configuration
export const UI_CONFIG = {
  DEBOUNCE_DELAY_MS: 300,
  AUTO_SAVE_INTERVAL_MS: 5000,
  WEBSOCKET_RETRY_DELAY_MS: 2000,
  MAX_WEBSOCKET_RETRIES: 5,
  RESULTS_PER_PAGE: 10,
  MAX_GRAPH_NODES: 500,
  QUERY_HISTORY_LIMIT: 50,
} as const;

// Performance thresholds
export const PERFORMANCE_THRESHOLDS = {
  MAX_ACCEPTABLE_LATENCY_MS: 2000,
  MIN_ANSWER_QUALITY_SCORE: 70,
  MIN_FAITHFULNESS_SCORE: 90,
  MAX_HALLUCINATION_SCORE: 10,
  UPLOAD_PROCESSING_TIMEOUT_MS: 300000, // 5 minutes
} as const;

// Color schemes for visualization
export const ENTITY_TYPE_COLORS = {
  person: '#4F46E5',
  organization: '#059669',
  location: '#DC2626',
  concept: '#7C3AED',
  date: '#EA580C',
  product: '#0891B2',
} as const;

// Status indicators
export const STATUS_COLORS = {
  queued: '#F59E0B',
  processing: '#3B82F6',
  indexed: '#10B981',
  failed: '#EF4444',
} as const;