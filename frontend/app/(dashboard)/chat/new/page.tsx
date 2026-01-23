'use client';

import { redirect } from 'next/navigation';
import { useEffect } from 'react';

// This page handles /chat/new route
// Clears any active conversation and redirects to main chat

export default function NewChatPage() {
  useEffect(() => {
    // Clear any active conversation ID
    sessionStorage.removeItem('activeConversationId');
  }, []);

  // Redirect to main chat page for a fresh start
  redirect('/chat');
}
