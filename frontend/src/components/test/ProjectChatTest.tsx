/**
 * Test Component for Project-Chat Integration
 * Demonstrates usage of useProjectChat hook and verifies implementation
 *
 * Usage: Import in any page to test functionality
 */

'use client';

import React, { useEffect } from 'react';
import { useProjectChat } from '@/hooks/useProjectChat';

interface ProjectChatTestProps {
  projectId: string;
}

export function ProjectChatTest({ projectId }: ProjectChatTestProps) {
  const {
    threads,
    isLoading,
    error,
    startChat,
    linkThread,
    unlinkThread,
    saveToNote,
    refreshThreads,
    clearError,
  } = useProjectChat(projectId);

  // Auto-fetch threads on mount
  useEffect(() => {
    refreshThreads();
  }, [projectId, refreshThreads]);

  const handleStartChat = async () => {
    const result = await startChat({
      initial_message: 'Test message from project',
      thread_title: 'Test Thread',
    });

    if (result) {
      console.log('✅ Chat started:', result);
      alert(`Chat started! Thread ID: ${result.thread_id}`);
    }
  };

  const handleLinkThread = async () => {
    const threadId = prompt('Enter thread ID to link:');
    if (!threadId) return;

    const result = await linkThread({
      thread_id: threadId,
      context_note: 'Test link from ProjectChatTest',
    });

    if (result) {
      console.log('✅ Thread linked:', result);
      alert('Thread linked successfully!');
    }
  };

  const handleUnlinkThread = async (threadId: string) => {
    if (!confirm(`Unlink thread ${threadId}?`)) return;

    await unlinkThread(threadId);
    console.log('✅ Thread unlinked:', threadId);
    alert('Thread unlinked successfully!');
  };

  const handleSaveToNote = async (threadId: string) => {
    const noteTitle = prompt('Enter note title:', 'Chat Notes');
    if (!noteTitle) return;

    const result = await saveToNote({
      thread_id: threadId,
      note_title: noteTitle,
      include_citations: true,
    });

    if (result) {
      console.log('✅ Saved to note:', result);
      alert(`Note created! ID: ${result.id}`);
    }
  };

  return (
    <div className="p-4 border rounded-lg bg-gray-900 text-green-400 font-mono">
      <h2 className="text-xl mb-4">Project-Chat Test Console</h2>
      <p className="text-sm mb-4">Project ID: {projectId}</p>

      {/* Loading State */}
      {isLoading && (
        <p className="text-amber-400 mb-4">⏳ Loading...</p>
      )}

      {/* Error State */}
      {error && (
        <div className="mb-4 p-2 bg-red-900 text-red-200 rounded">
          <p>❌ Error: {error}</p>
          <button
            onClick={clearError}
            className="mt-2 px-2 py-1 bg-red-700 rounded text-xs"
          >
            Clear Error
          </button>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mb-4 space-x-2">
        <button
          onClick={handleStartChat}
          className="px-4 py-2 bg-green-700 rounded hover:bg-green-600"
        >
          Start Chat
        </button>
        <button
          onClick={handleLinkThread}
          className="px-4 py-2 bg-blue-700 rounded hover:bg-blue-600"
        >
          Link Thread
        </button>
        <button
          onClick={refreshThreads}
          className="px-4 py-2 bg-gray-700 rounded hover:bg-gray-600"
        >
          Refresh
        </button>
      </div>

      {/* Threads List */}
      <div>
        <h3 className="text-lg mb-2">Linked Threads ({threads.length})</h3>
        {threads.length === 0 ? (
          <p className="text-gray-500">No threads linked yet</p>
        ) : (
          <ul className="space-y-2">
            {threads.map((thread) => (
              <li
                key={thread.id}
                className="p-2 bg-gray-800 rounded border border-gray-700"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <p className="font-semibold">{thread.thread_title}</p>
                    <p className="text-xs text-gray-400">
                      Thread ID: {thread.thread_id}
                    </p>
                    <p className="text-xs text-gray-400">
                      Link Type: {thread.link_type} | Messages: {thread.message_count}
                    </p>
                    {thread.context_note && (
                      <p className="text-xs text-amber-400 mt-1">
                        Note: {thread.context_note}
                      </p>
                    )}
                  </div>
                  <div className="space-x-2">
                    <button
                      onClick={() => handleSaveToNote(thread.thread_id)}
                      className="px-2 py-1 bg-cyan-700 rounded text-xs hover:bg-cyan-600"
                    >
                      Save to Note
                    </button>
                    <button
                      onClick={() => handleUnlinkThread(thread.thread_id)}
                      className="px-2 py-1 bg-red-700 rounded text-xs hover:bg-red-600"
                    >
                      Unlink
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* State Inspector */}
      <details className="mt-4 text-xs">
        <summary className="cursor-pointer text-gray-400">Show State</summary>
        <pre className="mt-2 p-2 bg-black rounded overflow-auto max-h-60">
          {JSON.stringify({ threads, isLoading, error }, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export default ProjectChatTest;
