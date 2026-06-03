import type { ThreadCreate } from '@/types/workspace';

interface BuildThreadCreateRequestParams {
  conversationId: string;
  title: string;
  projectId?: string;
}

/**
 * Build the thread creation payload for chat submit flows.
 *
 * The first message is persisted by the follow-up message send path
 * (local `createMessage` or cloud streaming), so it must not be
 * duplicated here via `initial_message`.
 */
export function buildThreadCreateRequest({
  conversationId,
  title,
  projectId,
}: BuildThreadCreateRequestParams): ThreadCreate {
  return {
    conversation_id: conversationId,
    title,
    ...(projectId ? { project_id: projectId } : {}),
  };
}
