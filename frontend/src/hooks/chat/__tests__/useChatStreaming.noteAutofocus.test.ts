/**
 * parseCreatedNoteResult: the pure gate for agent auto-focus of a freshly
 * created note. The store's pin gate (agent opens ignored while pinned) is
 * covered by artifactPanelStore.test.ts.
 */
import { describe, expect, it } from 'vitest';

import { parseCreatedNoteResult } from '@/hooks/chat/useChatStreaming';

describe('parseCreatedNoteResult', () => {
  it('extracts note id and title from a success payload', () => {
    const result = JSON.stringify({
      status: 'success',
      note_id: 'note-1',
      title: 'Reading notes',
      project_name: 'RLHF survey',
      message: "Created note 'Reading notes' in project 'RLHF survey'.",
    });
    expect(parseCreatedNoteResult(result)).toEqual({
      noteId: 'note-1',
      title: 'Reading notes',
    });
  });

  it('omits the title when missing', () => {
    expect(
      parseCreatedNoteResult(JSON.stringify({ note_id: 'note-2' }))
    ).toEqual({ noteId: 'note-2' });
  });

  it('returns null for error payloads', () => {
    expect(
      parseCreatedNoteResult(
        JSON.stringify({ error: 'Project not found or access denied' })
      )
    ).toBeNull();
  });

  it('returns null when note_id is absent or not a string', () => {
    expect(parseCreatedNoteResult(JSON.stringify({ status: 'ok' }))).toBeNull();
    expect(parseCreatedNoteResult(JSON.stringify({ note_id: 7 }))).toBeNull();
  });

  it('returns null for non-JSON results', () => {
    expect(parseCreatedNoteResult('Created the note.')).toBeNull();
    expect(parseCreatedNoteResult('')).toBeNull();
  });
});
