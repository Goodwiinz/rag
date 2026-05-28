'use client';

import { Edit2, Pin, PinOff, StickyNote, Trash2 } from 'lucide-react';
import type { ProjectNote } from '@/services/projectService';

export interface NoteListProps {
  notes: ProjectNote[];
  selectedTag?: string;
  onTagChange?: (tag: string) => void;
  onEdit: (note: ProjectNote) => void;
  onDelete: (noteId: string) => void;
  onTogglePin: (noteId: string) => void;
}

export function NoteList({
  notes,
  selectedTag,
  onTagChange,
  onEdit,
  onDelete,
  onTogglePin,
}: NoteListProps) {
  const availableTags = Array.from(
    new Set(notes.flatMap((note) => note.tags || []))
  ).sort();

  const visibleNotes = selectedTag
    ? notes.filter((note) => (note.tags || []).includes(selectedTag))
    : notes;

  const sortedNotes = [...visibleNotes].sort((a, b) => {
    if (a.is_pinned === b.is_pinned) {
      return (
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
    }
    return a.is_pinned ? -1 : 1;
  });

  if (notes.length === 0) {
    return (
      <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
        <StickyNote className="h-12 w-12 text-foreground mx-auto mb-4" />
        <p className="text-muted-foreground font-mono">No notes yet</p>
        <p className="text-sm text-muted-foreground mt-2">
          Create notes to organize your research
        </p>
      </div>
    );
  }

  return (
    <div>
      {availableTags.length > 0 && onTagChange && (
        <div className="mb-4 flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-mono">
            Filter by tag:
          </span>
          <select
            value={selectedTag || ''}
            onChange={(e) => onTagChange(e.target.value)}
            className="px-3 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-muted-foreground focus:outline-none focus:border-sol"
          >
            <option value="">All</option>
            {availableTags.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="space-y-3">
        {sortedNotes.map((note) => (
          <div
            key={note.id}
            className={`p-4 bg-[#0a0a0a] border rounded-lg ${
              note.is_pinned ? 'border-helios/50' : 'border-[#1a1a1a]'
            }`}
          >
            <div className="flex items-start justify-between mb-2 gap-3">
              <div className="flex items-center gap-2 min-w-0">
                {note.is_pinned && (
                  <Pin className="h-4 w-4 text-helios shrink-0" />
                )}
                <h3 className="font-mono font-medium text-muted-foreground truncate">
                  {note.title}
                </h3>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => onTogglePin(note.id)}
                  className="p-1.5 text-muted-foreground hover:text-helios transition-colors"
                  title={note.is_pinned ? 'Unpin' : 'Pin'}
                >
                  {note.is_pinned ? (
                    <PinOff className="h-4 w-4" />
                  ) : (
                    <Pin className="h-4 w-4" />
                  )}
                </button>
                <button
                  onClick={() => onEdit(note)}
                  className="p-1.5 text-muted-foreground hover:text-sol transition-colors"
                  title="Edit note"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => onDelete(note.id)}
                  className="p-1.5 text-muted-foreground hover:text-red-400 transition-colors"
                  title="Delete note"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <p className="text-sm text-muted-foreground whitespace-pre-wrap line-clamp-4">
              {note.content_preview || note.content}
            </p>

            <div className="mt-3 flex items-center justify-between gap-2">
              <div className="flex flex-wrap gap-1">
                {(note.tags || []).map((tag) => (
                  <span
                    key={tag}
                    className="px-1.5 py-0.5 bg-[#1a1a1a] border border-[#333] rounded text-[11px] font-mono text-muted-foreground"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <p className="text-xs text-foreground font-mono">
                Updated {new Date(note.updated_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default NoteList;
