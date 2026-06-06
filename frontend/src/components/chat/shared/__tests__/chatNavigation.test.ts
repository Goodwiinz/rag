import { describe, expect, it } from 'vitest';
import {
  getNewChatUrl,
  getSelectedThreadUrl,
} from '../chatNavigation';

describe('chatNavigation', () => {
  it('keeps live chat navigation on /chat with a thread query param', () => {
    expect(getSelectedThreadUrl('thread-123')).toBe('/chat?thread=thread-123');
  });

  it('marks a new chat with the new=1 intent so the session lands blank', () => {
    expect(getNewChatUrl()).toBe('/chat?new=1');
  });
});
