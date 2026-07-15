import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

type ChatMessageFixture = Partial<ChatPageMessage> &
  Pick<ChatPageMessage, 'role' | 'content'>;

/** Build complete chat-message fixtures without weakening the production
 * runtime identity contract for tests. */
export function makeChatPageMessage(
  fixture: ChatMessageFixture
): ChatPageMessage {
  const timestamp = fixture.timestamp ?? 1;
  const runtimeId =
    fixture.runtimeId ?? fixture.id ?? `test-${fixture.role}-${timestamp}`;
  const source =
    fixture.source ??
    (fixture.id ? ('canonical' as const) : ('optimistic' as const));

  return {
    ...fixture,
    runtimeId,
    source,
    timestamp,
  };
}
