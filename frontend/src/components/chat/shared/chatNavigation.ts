export function getSelectedThreadUrl(threadId: string): string {
  return `/chat?thread=${encodeURIComponent(threadId)}`;
}

export function getNewChatUrl(): string {
  return '/chat';
}
