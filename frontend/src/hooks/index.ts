// Export all hooks from this directory
export { AuthProvider, useAuth } from './useAuth';
export type { AuthState } from '@/types/auth';

// Note: useDocuments requires type fixes - commented out for strict mode
// export { useDocuments } from './useDocuments';

export { useChatPersistence } from './useChatPersistence';
export type { UIMessage, UIConversation } from './useChatPersistence';

export { useProjectChat } from './useProjectChat';

export { useCitationsForThread } from './useCitationsForThread';
export type { CitationItem } from './useCitationsForThread';

export {
  useEvidenceMeter,
  useEvidenceBreakdown,
  getConsensusText,
  getConsensusColor,
  getConsensusEmoji,
} from './useEvidenceMeter';
