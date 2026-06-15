'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function NewChatPage() {
  const router = useRouter();
  useEffect(() => {
    // Carry an explicit "new chat" intent so the chat page lands on a blank
    // composer instead of restoring/auto-selecting the most recent thread.
    router.replace('/chat?new=1');
  }, [router]);
  return null;
}
