'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect } from 'react';

// This page handles /chat/[id] routes
// Sets the thread ID in session storage and redirects to main chat

export default function ChatConversationPage() {
  const params = useParams();
  const router = useRouter();
  const threadId = params.id as string;

  useEffect(() => {
    // Store the thread ID for the main chat to pick up, then redirect
    if (threadId) {
      console.log('[ChatConversationPage] Setting active thread:', threadId);
      // Set sessionStorage synchronously
      sessionStorage.setItem('activeThreadId', threadId);
      // Verify it was set
      const verified = sessionStorage.getItem('activeThreadId');
      console.log('[ChatConversationPage] Verified sessionStorage:', verified);
      // Use router.push with query param as backup
      router.push(`/chat?thread=${threadId}`);
    }
  }, [threadId, router]);

  // Show loading while redirecting
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[var(--phosphor-green)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-sm text-[var(--terminal-text-muted)]" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
          Loading conversation...
        </p>
      </div>
    </div>
  );
}
