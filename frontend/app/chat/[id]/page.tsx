'use client';

import { redirect } from 'next/navigation';
import { useParams } from 'next/navigation';
import { useEffect } from 'react';

// This page handles /chat/[id] routes
// For now, redirect to the main chat page
// The conversation ID can be used to load specific conversations

export default function ChatConversationPage() {
  const params = useParams();
  const conversationId = params.id as string;

  useEffect(() => {
    // Store the conversation ID for the main chat to pick up
    if (conversationId) {
      sessionStorage.setItem('activeConversationId', conversationId);
    }
  }, [conversationId]);

  // Redirect to main chat page
  redirect('/chat');
}
