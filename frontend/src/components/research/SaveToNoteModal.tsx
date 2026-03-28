'use client';

/**
 * SaveToNoteModal Component
 * Modal for saving a chat thread to a markdown note
 *
 * Features:
 * - Note title input (required)
 * - Include citations checkbox
 * - Terminal Observatory theme styling
 * - Loading state during submission
 * - Form validation
 */

import React, { useState } from 'react';
import { FileText, X, Loader2, Save } from 'lucide-react';

export interface SaveToNoteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (noteTitle: string, includeCitations: boolean) => Promise<void>;
}

export const SaveToNoteModal: React.FC<SaveToNoteModalProps> = ({
  isOpen,
  onClose,
  onSave,
}) => {
  const [noteTitle, setNoteTitle] = useState('');
  const [includeCitations, setIncludeCitations] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!noteTitle.trim()) {
      setError('Note title is required');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSave(noteTitle.trim(), includeCitations);
      // Reset form
      setNoteTitle('');
      setIncludeCitations(true);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save note');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      setNoteTitle('');
      setIncludeCitations(true);
      setError(null);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-[#D4A039]" />
            <h2 className="font-mono font-bold text-gray-200">Save Thread to Note</h2>
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
          {/* Note Title */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
              Note Title <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              placeholder="e.g., Research Discussion Summary"
              disabled={isSubmitting}
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-gray-200 font-mono text-sm placeholder:text-gray-600 focus:outline-none focus:border-[#D4A039]/50 focus:ring-1 focus:ring-[#D4A039]/30 disabled:opacity-50"
              required
            />
            <p className="text-xs text-gray-600 font-mono mt-1">
              This will be the filename of your markdown note
            </p>
          </div>

          {/* Include Citations Toggle */}
          <div className="flex items-center justify-between p-3 bg-[#1a1a1a] rounded">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-300 font-mono">Include Citations</span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                Add reference links to source documents in the note
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIncludeCitations(!includeCitations)}
              disabled={isSubmitting}
              className={`relative w-12 h-6 rounded-full transition-colors disabled:opacity-50 ${
                includeCitations
                  ? 'bg-[#D4A039]/30 border-[#D4A039]'
                  : 'bg-[#333] border-[#555]'
              } border`}
            >
              <span
                className={`absolute top-0.5 w-5 h-5 rounded-full transition-transform ${
                  includeCitations
                    ? 'translate-x-6 bg-[#D4A039]'
                    : 'translate-x-0.5 bg-gray-500'
                }`}
              />
            </button>
          </div>

          {/* Error Display */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded text-sm font-mono text-red-400">
              {error}
            </div>
          )}

          {/* Info Box */}
          <div className="p-3 bg-[#00d4ff]/10 border border-[#00d4ff]/30 rounded text-xs font-mono text-[#00d4ff]">
            The thread messages will be converted to a markdown note and saved to your project. You
            can access it from the project notes tab.
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
              disabled={isSubmitting || !noteTitle.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-[#D4A039]/10 text-[#D4A039] border border-[#D4A039]/30 rounded font-mono text-sm hover:bg-[#D4A039]/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Save Note
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SaveToNoteModal;
