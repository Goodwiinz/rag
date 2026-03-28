'use client';

/**
 * StartChatModal Component
 * Modal for starting a new chat thread from project context
 *
 * Features:
 * - Initial message input (required)
 * - Optional thread title
 * - Terminal Observatory theme styling
 * - Loading state during submission
 * - Form validation
 */

import React, { useState } from 'react';
import { MessageSquare, X, Loader2, Send } from 'lucide-react';

export interface StartChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartChat: (initialMessage: string, threadTitle?: string) => Promise<void>;
}

export const StartChatModal: React.FC<StartChatModalProps> = ({
  isOpen,
  onClose,
  onStartChat,
}) => {
  const [initialMessage, setInitialMessage] = useState('');
  const [threadTitle, setThreadTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!initialMessage.trim()) {
      setError('Initial message is required');
      return;
    }

    setIsSubmitting(true);
    try {
      await onStartChat(initialMessage.trim(), threadTitle.trim() || undefined);
      // Reset form
      setInitialMessage('');
      setThreadTitle('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start chat');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setInitialMessage('');
      setThreadTitle('');
      setError(null);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-[#D4A039]" />
            <h2 className="font-mono font-bold text-gray-200">Start New Chat</h2>
          </div>
          <button
            onClick={handleClose}
            disabled={isSubmitting}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Initial Message */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
              Initial Message <span className="text-red-400">*</span>
            </label>
            <textarea
              value={initialMessage}
              onChange={(e) => setInitialMessage(e.target.value)}
              placeholder="Enter your first message to start the conversation..."
              disabled={isSubmitting}
              className="w-full h-32 px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-gray-200 font-mono text-sm placeholder:text-gray-600 focus:outline-none focus:border-[#D4A039]/50 focus:ring-1 focus:ring-[#D4A039]/30 disabled:opacity-50 resize-none"
              required
            />
            <p className="text-xs text-gray-600 font-mono mt-1">
              This message will start the chat with project documents as context
            </p>
          </div>

          {/* Thread Title (Optional) */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
              Thread Title <span className="text-gray-600">(optional)</span>
            </label>
            <input
              type="text"
              value={threadTitle}
              onChange={(e) => setThreadTitle(e.target.value)}
              placeholder="e.g., Research Discussion - Methods Analysis"
              disabled={isSubmitting}
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-gray-200 font-mono text-sm placeholder:text-gray-600 focus:outline-none focus:border-[#D4A039]/50 focus:ring-1 focus:ring-[#D4A039]/30 disabled:opacity-50"
            />
            <p className="text-xs text-gray-600 font-mono mt-1">
              If not provided, a title will be generated automatically
            </p>
          </div>

          {/* Error Display */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded text-sm font-mono text-red-400">
              {error}
            </div>
          )}

          {/* Info Box */}
          <div className="p-3 bg-[#D4A039]/10 border border-[#D4A039]/30 rounded text-xs font-mono text-[#D4A039]">
            This chat will use all documents in this project as RAG context. You can ask questions
            and have natural conversations about your research materials.
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-4 border-t border-[#1a1a1a]">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !initialMessage.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-[#D4A039]/10 text-[#D4A039] border border-[#D4A039]/30 rounded font-mono text-sm hover:bg-[#D4A039]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting Chat...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Start Chat
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default StartChatModal;
