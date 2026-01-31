// Export all hooks from this directory
export { AuthProvider, useAuth } from './useAuth';
export type { AuthState } from '@/types/auth';

export { useDocumentProcessingStatus } from './useDocumentProcessingStatus';
export type {
  UseDocumentProcessingStatusParams,
  UseDocumentProcessingStatusReturn
} from './useDocumentProcessingStatus';

// Note: useDocuments requires type fixes - commented out for strict mode
// export { useDocuments } from './useDocuments';
export { useWebSocket } from './useWebSocket';

export { useChatPersistence } from './useChatPersistence';
export type {
  UIMessage,
  UIConversation,
} from './useChatPersistence';

export { useProjectChat } from './useProjectChat';

export { 
  useEvidenceMeter, 
  useEvidenceBreakdown,
  getConsensusText,
  getConsensusColor,
  getConsensusEmoji,
} from './useEvidenceMeter';