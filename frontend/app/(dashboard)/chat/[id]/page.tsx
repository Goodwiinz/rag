'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function ChatConversationPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    if (params.id) {
      router.replace(`/chat?thread=${params.id}`);
    }
  }, [params.id, router]);

  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-[var(--nous-sol)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p
          className="text-sm text-[var(--nous-fg-3)]"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          Loading conversation...
        </p>
      </div>
    </div>
  );
}
