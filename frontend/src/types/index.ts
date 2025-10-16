// Export all types from a central location
export * from './api';
export * from './auth';
export * from './document';
export * from './search';
export * from './knowledge-graph';
export * from './evaluation';
export * from './ui';

// Export constants with explicit names to avoid conflicts
export {
  UPLOAD_LIMITS,
  UI_CONFIG,
  PERFORMANCE_THRESHOLDS,
  ENTITY_TYPE_COLORS,
  STATUS_COLORS
} from './constants';

// Utility Types
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type EntityById<T extends { id: string }> = Record<string, T>;

export type ProcessingStatus = import('./document').Document['processing_status'];
export type FileType = import('./document').Document['file_type'];
export type EntityType = import('./search').Entity['type'];
export type TabType = import('./ui').UIState['activeTab'];

export type DocumentListParams = {
  page?: number;
  page_size?: number;
  file_type?: FileType;
  status?: ProcessingStatus;
  search?: string;
};

export type SearchParams = {
  query: string;
  modalities?: ('text' | 'image' | 'audio' | 'video')[];
  document_ids?: string[];
  limit?: number;
  offset?: number;
};

export type EventHandler<T = void> = (event: T) => void;
export type AsyncEventHandler<T = void> = (event: T) => Promise<void>;

export interface UploadFormData {
  files: File[];
  metadata?: Record<string, string>;
}

export interface QueryFormData {
  query: string;
  filters?: import('./search').SearchRequest['filters'];
}