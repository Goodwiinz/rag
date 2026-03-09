import type { Thread } from '@/types/workspace';

interface ThreadPreviewMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ThreadPreviewConversation {
  id: string;
  previewText?: string;
  messageCount?: number;
}

interface ThreadPreviewFetcherResult {
  messages: Array<{
    role: string;
    content: string;
  }>;
}

type FetchThreadPreview = (threadId: string) => Promise<ThreadPreviewFetcherResult>;

export async function hydrateThreadPreviews<T extends ThreadPreviewConversation>(
  conversations: T[],
  threads: Thread[],
  fetchThreadPreview: FetchThreadPreview
): Promise<T[]> {
  const previewableThreads = threads.filter((thread) => thread.message_count > 0);
  if (previewableThreads.length === 0) {
    return conversations;
  }

  const previews = await Promise.all(
    previewableThreads.map(async (thread) => {
      try {
        const response = await fetchThreadPreview(thread.id);
        const lastMessage = response.messages.at(-1);
        return [thread.id, lastMessage] as const;
      } catch {
        return [thread.id, null] as const;
      }
    })
  );

  const previewByThreadId = new Map(previews);
  const threadById = new Map(threads.map((thread) => [thread.id, thread]));

  return conversations.map((conversation) => {
    const thread = threadById.get(conversation.id);
    const preview = previewByThreadId.get(conversation.id);

    return {
      ...conversation,
      messageCount: thread?.message_count ?? conversation.messageCount,
      previewText: preview?.content || conversation.previewText,
    };
  });
}
