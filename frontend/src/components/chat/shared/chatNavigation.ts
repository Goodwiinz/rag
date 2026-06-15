export function getSelectedThreadUrl(threadId: string): string {
  return `/chat?thread=${encodeURIComponent(threadId)}`;
}

export function getNewChatUrl(): string {
  // `new=1` marks an intentional new chat so the session skips warm-start
  // restore and the auto-select-most-recent-thread fallback, landing on a
  // blank composer. Cleared on the next real navigation (?thread=… on send).
  return '/chat?new=1';
}
